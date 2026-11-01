#!/usr/bin/env python3
"""
Create a lightweight dev-only smoke checkpoint for ConvAE.
Trains for a few fast iterations on a tiny sample so the entire multi-model pipeline
and UI can be exercised end-to-end without waiting for a multi-hour training run.
Metadata explicitly tags 'dev_only: true' and trained_on='DEV SMOKE TEST (not for real use)'.
"""
import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import torch
import torch.nn as nn
import torch.optim as optim

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("make_dev_checkpoint")


def get_git_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT)
        return out.decode().strip()
    except Exception:
        return "unknown"


def make_dev_checkpoint(output_dir: Path, calibration_dir: Path, iterations: int = 5):
    output_dir.mkdir(parents=True, exist_ok=True)
    calibration_dir.mkdir(parents=True, exist_ok=True)

    from ConvAE import ConvLSTMED

    model_args = SimpleNamespace(mode="gray")
    model = ConvLSTMED(model_args)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    logger.info(f"Training ConvLSTMED dev smoke checkpoint for {iterations} iterations...")
    torch.manual_seed(42)

    # Train on synthetic mini-batch: (B=2, T=4, H=227, W=227)
    final_loss = 0.0
    for i in range(iterations):
        optimizer.zero_grad()
        dummy_input = torch.rand(2, 4, 227, 227)
        recon = model(dummy_input)
        loss = criterion(recon, dummy_input)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.item())
        logger.info(f"  Iteration {i+1}/{iterations} - loss: {final_loss:.6f}")

    ckpt_path = output_dir / "smoke_checkpoint.pth"
    meta_path = output_dir / "smoke_checkpoint.json"

    # Save state dict
    torch.save(model.state_dict(), ckpt_path)
    logger.info(f"Saved state_dict to {ckpt_path} ({ckpt_path.stat().st_size} bytes)")

    meta = {
        "dev_only": True,
        "model": "ConvLSTMED",
        "trained_on": "DEV SMOKE TEST (not for real use)",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": get_git_commit(),
        "final_loss": round(final_loss, 6),
        "iterations": iterations,
        "note": "Smoke checkpoint intended strictly for dev and pipeline validation. Scores are not meaningful.",
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info(f"Saved metadata to {meta_path}")

    # Create dev calibration sidecar
    calib_file = calibration_dir / "convae_calibration.json"
    calib_meta = {
        "threshold": 0.50,
        "min_error": 0.01,
        "max_error": 0.12,
        "calibration_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "method": "heuristic_dev_scale",
        "target_false_alarm_rate_per_hour": 1.0,
    }
    with open(calib_file, "w") as f:
        json.dump(calib_meta, f, indent=2)
    logger.info(f"Saved dev calibration to {calib_file}")

    return ckpt_path, meta_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create ConvAE dev smoke checkpoint")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "checkpoints" / "convae",
        help="Target checkpoint directory",
    )
    parser.add_argument(
        "--calibration-dir",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "calibration",
        help="Target calibration directory",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of smoke training iterations",
    )
    args = parser.parse_args()
    make_dev_checkpoint(args.output_dir, args.calibration_dir, args.iterations)
