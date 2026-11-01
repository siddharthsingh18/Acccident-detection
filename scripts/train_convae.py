#!/usr/bin/env python3
"""
scripts/train_convae.py

Unsupervised training of ConvLSTMED Spatio-Temporal AutoEncoder on normal CCTV traffic clips.
- Normal-only training: learns nominal traffic representations from normal clips in 'train' split.
- Early stopping on validation reconstruction loss (evaluating normal clips in 'val' split).
- Saves state_dict checkpoints (torch.load with weights_only=True compatible) plus metadata JSON.
- Provides estimation mode to report expected training time on current hardware.
"""

import argparse
import csv
import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("train_convae")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    from ConvAE import ConvLSTMED
    from argus_ml.preprocessing import (
        load_video_frames,
        create_sliding_windows,
        preprocess_for_convae,
        DEFAULT_CONVAE_SIZE,
    )
    TORCH_AVAILABLE = True
except ImportError as e:
    TORCH_AVAILABLE = False
    logger.warning(f"PyTorch or ConvAE modules not available: {e}")


def get_git_commit() -> str:
    """Retrieve current git commit hash, or 'unknown'."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(PROJECT_ROOT), stderr=subprocess.DEVNULL
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def get_file_hash(path: Path) -> str:
    """Compute sha256 hash of a file."""
    if not path.exists():
        return "not_found"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()[:16]


def get_hardware_description(device: str) -> str:
    """Describe system hardware and target device."""
    system = platform.system()
    machine = platform.machine()
    cpu_info = ""
    if system == "Darwin":
        try:
            cpu_info = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
        except Exception:
            cpu_info = machine
    elif system == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        cpu_info = line.split(":", 1)[1].strip()
                        break
        except Exception:
            cpu_info = machine
    else:
        cpu_info = machine

    return f"{cpu_info} ({system} {machine}), device={device}"


class ConvAEVideoDataset(Dataset):
    """
    Sliding window dataset extracted from normal video clips.
    Each item is a float32 tensor of shape (window_size, 227, 227) with values in [0.0, 1.0].
    """
    def __init__(
        self,
        video_paths: List[Path],
        window_size: int = 30,
        stride: int = 15,
        target_size: Tuple[int, int] = DEFAULT_CONVAE_SIZE,
    ):
        self.window_size = window_size
        self.stride = stride
        self.target_size = target_size
        self.windows: List[np.ndarray] = []

        logger.info(f"Loading and preprocessing {len(video_paths)} video clips...")
        for p in video_paths:
            if not p.exists():
                logger.warning(f"Video file not found, skipping: {p}")
                continue
            try:
                frames = load_video_frames(p, target_size=None)
                if not frames or len(frames) < 10:
                    continue
                # Split into sliding windows (padding 29-frame subvideos to 30)
                raw_windows = create_sliding_windows(
                    frames, window_size=window_size, stride=stride, pad_to_window=True
                )
                for w in raw_windows:
                    if len(w) == window_size:
                        tensor_w = preprocess_for_convae(w, target_size=target_size, mode="gray")
                        self.windows.append(tensor_w)
            except Exception as e:
                logger.warning(f"Failed to process video {p}: {e}")

        logger.info(f"Generated {len(self.windows)} windows of shape ({window_size}, {target_size[0]}, {target_size[1]})")

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, idx: int) -> torch.Tensor:
        arr = self.windows[idx]  # (T, 227, 227)
        return torch.from_numpy(arr)


def load_manifest_clips(
    manifest_path: Path,
    split: str = "train",
    label: str = "normal",
    camera_view: str = "cctv",
    max_samples: Optional[int] = None,
) -> List[Path]:
    """Extract matching video clip paths from manifest CSV."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    paths = []
    with open(manifest_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("split") == split and row.get("label") == label:
                if camera_view and row.get("camera_view") != camera_view:
                    continue
                vpath = PROJECT_ROOT / row["video_path"]
                if vpath.exists():
                    paths.append(vpath)
                    if max_samples and len(paths) >= max_samples:
                        break

    return paths


def estimate_training_time(
    model: nn.Module,
    device: str,
    num_windows: int,
    batch_size: int,
    epochs: int,
) -> Dict[str, Any]:
    """Benchmark single batch throughput to estimate total training duration."""
    dummy_batch = torch.randn(min(batch_size, 4), 30, 227, 227, device=device)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    # Warmup
    optimizer.zero_grad()
    out = model(dummy_batch)
    loss = criterion(out, dummy_batch)
    loss.backward()
    optimizer.step()
    if device == "mps":
        torch.mps.synchronize()

    # Time 5 sample iterations
    t0 = time.perf_counter()
    iters = 5
    for _ in range(iters):
        optimizer.zero_grad()
        out = model(dummy_batch)
        loss = criterion(out, dummy_batch)
        loss.backward()
        optimizer.step()
    if device == "mps":
        torch.mps.synchronize()
    elapsed = time.perf_counter() - t0
    sec_per_batch = elapsed / iters
    windows_per_sec = dummy_batch.size(0) / sec_per_batch

    total_batches_per_epoch = max(1, num_windows // batch_size)
    sec_per_epoch = total_batches_per_epoch * sec_per_batch
    total_est_seconds = sec_per_epoch * epochs

    return {
        "sec_per_batch": round(sec_per_batch, 3),
        "windows_per_sec": round(windows_per_sec, 2),
        "total_windows": num_windows,
        "batches_per_epoch": total_batches_per_epoch,
        "sec_per_epoch": round(sec_per_epoch, 1),
        "est_total_seconds": round(total_est_seconds, 1),
        "est_total_minutes": round(total_est_seconds / 60.0, 2),
    }


def train_convae(
    config: Dict[str, Any],
    manifest_path: Path,
    output_dir: Path,
    device: Optional[str] = None,
    estimate_only: bool = False,
) -> Tuple[Optional[Path], Optional[Path], Dict[str, Any]]:
    """
    Execute training loop with early stopping on validation loss.
    Returns (checkpoint_path, metadata_path, metrics).
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch is required for ConvAE training")

    seed = int(config.get("seed", 42))
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Auto-detect device
    if not device:
        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

    logger.info(f"Training on device: {device}")

    # Load clip paths
    train_paths = load_manifest_clips(
        manifest_path,
        split="train",
        label="normal",
        camera_view="cctv",
        max_samples=config.get("max_train_samples"),
    )
    val_paths = load_manifest_clips(
        manifest_path,
        split="val",
        label="normal",
        camera_view="cctv",
        max_samples=config.get("max_val_samples"),
    )

    if not train_paths:
        raise RuntimeError(f"No normal training clips found in {manifest_path}")

    # Build datasets
    window_size = int(config.get("window_size", 30))
    stride = int(config.get("stride", 15))
    batch_size = int(config.get("batch_size", 4))
    epochs = int(config.get("epochs", 5))
    patience = int(config.get("patience", 3))
    lr = float(config.get("learning_rate", 0.001))
    weight_decay = float(config.get("weight_decay", 1e-5))

    train_dataset = ConvAEVideoDataset(train_paths, window_size=window_size, stride=stride)
    val_dataset = ConvAEVideoDataset(val_paths, window_size=window_size, stride=stride) if val_paths else None

    if len(train_dataset) == 0:
        raise RuntimeError("No sliding windows generated from training clips")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = (
        DataLoader(val_dataset, batch_size=batch_size, shuffle=False, drop_last=False)
        if val_dataset and len(val_dataset) > 0
        else None
    )

    # Initialize model
    model = ConvLSTMED(SimpleNamespace(mode="gray")).to(device)

    # Estimate training time
    estimation = estimate_training_time(
        model=model,
        device=device,
        num_windows=len(train_dataset),
        batch_size=batch_size,
        epochs=epochs,
    )
    logger.info(
        f"ESTIMATED TRAINING TIME: {estimation['est_total_minutes']} min "
        f"({estimation['sec_per_epoch']}s/epoch, {estimation['windows_per_sec']} windows/s, {len(train_dataset)} windows)"
    )

    if estimate_only:
        print("\n=== ConvAE Training Time Estimate ===")
        print(f"Device:            {device}")
        print(f"Hardware:          {get_hardware_description(device)}")
        print(f"Windows Count:     {len(train_dataset)}")
        print(f"Batch Size:        {batch_size}")
        print(f"Epochs:            {epochs}")
        print(f"Throughput:        {estimation['windows_per_sec']} windows/s")
        print(f"Est Time / Epoch:  {estimation['sec_per_epoch']} seconds")
        print(f"Est Total Time:    {estimation['est_total_minutes']} minutes ({estimation['est_total_seconds']} s)")
        print("=====================================\n")
        return None, None, {"estimation": estimation}

    # Loss and optimizer
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    output_dir.mkdir(parents=True, exist_ok=True)
    best_checkpoint_path = output_dir / "best_model.pth"
    metadata_path = output_dir / "best_model.json"

    best_val_loss = float("inf")
    patience_counter = 0
    best_epoch = 0
    history = []

    logger.info(f"Starting ConvAE training for {epochs} epochs (patience={patience})...")
    start_train_time = time.perf_counter()

    for epoch in range(1, epochs + 1):
        epoch_start = time.perf_counter()
        model.train()
        train_loss_sum = 0.0
        train_batches = 0

        for batch in train_loader:
            batch = batch.to(device)
            optimizer.zero_grad()
            recon = model(batch)
            loss = criterion(recon, batch)
            loss.backward()
            optimizer.step()

            train_loss_sum += float(loss.item())
            train_batches += 1

        train_loss = train_loss_sum / max(1, train_batches)

        # Validation phase
        val_loss = train_loss  # fallback if no val set
        if val_loader:
            model.eval()
            val_loss_sum = 0.0
            val_batches = 0
            with torch.no_grad():
                for batch in val_loader:
                    batch = batch.to(device)
                    recon = model(batch)
                    vloss = criterion(recon, batch)
                    val_loss_sum += float(vloss.item())
                    val_batches += 1
            val_loss = val_loss_sum / max(1, val_batches)

        epoch_duration = time.perf_counter() - epoch_start
        history.append({
            "epoch": epoch,
            "train_loss": round(train_loss, 6),
            "val_loss": round(val_loss, 6),
            "duration_s": round(epoch_duration, 2),
        })

        logger.info(
            f"Epoch {epoch:02d}/{epochs:02d} | Train MSE: {train_loss:.6f} | Val MSE: {val_loss:.6f} | Time: {epoch_duration:.1f}s"
        )

        # Early stopping check
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            patience_counter = 0

            # Ground rule: PyTorch state_dict only
            torch.save(model.state_dict(), best_checkpoint_path)
            logger.info(f"[*] Saved new best model checkpoint to {best_checkpoint_path} (val_loss={best_val_loss:.6f})")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                logger.info(f"Early stopping triggered at epoch {epoch} (no improvement for {patience} epochs)")
                break

    total_train_duration = time.perf_counter() - start_train_time
    logger.info(f"Training completed in {total_train_duration:.1f}s. Best Epoch: {best_epoch} with Val Loss: {best_val_loss:.6f}")

    # Write metadata JSON
    metadata = {
        "model_name": "convae",
        "checkpoint_file": best_checkpoint_path.name,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "manifest_path": str(manifest_path.relative_to(PROJECT_ROOT) if manifest_path.is_relative_to(PROJECT_ROOT) else manifest_path),
        "manifest_hash": get_file_hash(manifest_path),
        "hardware": get_hardware_description(device),
        "hyperparameters": {
            "config_name": config.get("name", "custom"),
            "epochs": epochs,
            "best_epoch": best_epoch,
            "batch_size": batch_size,
            "learning_rate": lr,
            "weight_decay": weight_decay,
            "window_size": window_size,
            "stride": stride,
            "seed": seed,
            "device": device,
        },
        "dataset_stats": {
            "train_clips": len(train_paths),
            "train_windows": len(train_dataset),
            "val_clips": len(val_paths),
            "val_windows": len(val_dataset) if val_dataset else 0,
        },
        "metrics": {
            "best_val_loss": round(best_val_loss, 6),
            "final_train_loss": round(train_loss, 6),
            "total_duration_s": round(total_train_duration, 2),
        },
        "history": history,
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved checkpoint metadata to {metadata_path}")

    return best_checkpoint_path, metadata_path, metadata


def main():
    parser = argparse.ArgumentParser(description="Train ConvAE anomaly model on normal CCTV clips")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "configs" / "convae_smoke.json", help="Path to config JSON")
    parser.add_argument("--smoke", action="store_true", help="Use default smoke config (fast CPU/MPS run)")
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data" / "manifest.csv", help="Path to manifest CSV")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "artifacts" / "checkpoints" / "convae", help="Output directory")
    parser.add_argument("--device", type=str, default=None, choices=["cpu", "mps", "cuda"], help="Computation device")
    parser.add_argument("--estimate-only", action="store_true", help="Print throughput and time estimate, then exit")
    parser.add_argument("--epochs", type=int, default=None, help="Override epochs from config")
    args = parser.parse_args()

    config_path = PROJECT_ROOT / "configs" / "convae_smoke.json" if args.smoke else args.config
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if args.epochs is not None:
        config["epochs"] = args.epochs

    train_convae(
        config=config,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        device=args.device,
        estimate_only=args.estimate_only,
    )


if __name__ == "__main__":
    main()
