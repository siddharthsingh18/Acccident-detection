#!/usr/bin/env python3
"""
scripts/calibrate.py

Calibrate ConvAE anomaly detection threshold and [0.0, 1.0] score mapping on the VALIDATION split.
- Strictly evaluates on the 'val' split. Rejects and asserts that 'test' split is never loaded.
- Solves for threshold satisfying target False Alarm Rate (FAR per camera-hour).
- Computes Platt scaling (logistic regression) and min-max normalization parameters.
- Writes calibration sidecar to artifacts/calibration/convae_calibration.json.
"""

import argparse
import csv
import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from typing import Dict, List, Tuple, Any

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("calibrate_convae")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import torch
    from ConvAE import ConvLSTMED
    from argus_ml.preprocessing import (
        load_video_frames,
        create_sliding_windows,
        preprocess_for_convae,
    )
    from sklearn.linear_model import LogisticRegression
    TORCH_AVAILABLE = True
except ImportError as e:
    TORCH_AVAILABLE = False
    logger.warning(f"Required ML modules not available: {e}")


def get_file_hash(path: Path) -> str:
    """Compute sha256 hash of a file."""
    if not path.exists():
        return "not_found"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()[:16]


def evaluate_clip_recon_error(
    model: torch.nn.Module,
    video_path: Path,
    device: str,
    window_size: int = 30,
    stride: int = 15,
) -> float:
    """
    Run video through ConvAE and return mean reconstruction MSE error.
    """
    frames = load_video_frames(video_path, target_size=None)
    if not frames or len(frames) < 10:
        return 0.0

    windows = create_sliding_windows(frames, window_size=window_size, stride=stride, pad_to_window=True)
    if not windows:
        return 0.0

    errors = []
    for w in windows:
        tensor_w = preprocess_for_convae(w, target_size=(227, 227), mode="gray")  # (T, 227, 227)
        inp = torch.from_numpy(tensor_w).unsqueeze(0).to(device)  # (1, T, 227, 227)
        with torch.no_grad():
            recon = model(inp)
            mse = float(torch.mean((inp - recon) ** 2).item())
            errors.append(mse)

    return float(np.mean(errors)) if errors else 0.0


def calibrate_convae(
    manifest_path: Path,
    checkpoint_path: Path,
    output_path: Path,
    target_far_per_hour: float = 1.0,
    device: str = "cpu",
) -> Dict[str, Any]:
    """
    Calibrate ConvAE threshold and score normalization using 'val' split data.
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch and scikit-learn are required for calibration")

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found at: {checkpoint_path}")

    logger.info(f"Loading checkpoint from {checkpoint_path}...")
    state = torch.load(checkpoint_path, map_location=device, weights_only=True)
    state_dict = state.get("state_dict", state) if isinstance(state, dict) else state

    model = ConvLSTMED(SimpleNamespace(mode="gray"))
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    logger.info(f"Reading validation clips from manifest: {manifest_path}...")
    val_records = []
    with open(manifest_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # STRICT REQUIREMENT: Never touch the test split!
            split = row.get("split", "").strip().lower()
            if split == "test":
                continue
            if split == "val" and row.get("camera_view") == "cctv":
                vpath = PROJECT_ROOT / row["video_path"]
                if vpath.exists():
                    val_records.append({
                        "path": vpath,
                        "label": row["label"].strip().lower(),
                        "duration_s": float(row.get("duration_s", 1.0)),
                    })

    if not val_records:
        raise RuntimeError("No validation CCTV clips found in manifest!")

    normal_records = [r for r in val_records if r["label"] == "normal"]
    accident_records = [r for r in val_records if r["label"] == "accident"]

    logger.info(f"Validation dataset: {len(normal_records)} normal clips, {len(accident_records)} accident clips")

    # Score normal clips
    normal_errors = []
    normal_duration_s = 0.0
    for r in normal_records:
        mse = evaluate_clip_recon_error(model, r["path"], device=device)
        normal_errors.append(mse)
        normal_duration_s += r["duration_s"]

    # Score accident clips
    accident_errors = []
    for r in accident_records:
        mse = evaluate_clip_recon_error(model, r["path"], device=device)
        accident_errors.append(mse)

    normal_camera_hours = normal_duration_s / 3600.0
    logger.info(f"Total normal surveillance duration: {normal_duration_s:.1f}s ({normal_camera_hours:.4f} camera-hours)")

    # Find raw threshold for target FAR
    # Sort normal errors
    sorted_normal = sorted(normal_errors)
    raw_threshold = None
    achieved_far = 0.0

    # Search for threshold that gives <= target_far_per_hour
    # Candidate thresholds from normal errors
    for cand in sorted_normal:
        false_alarms = sum(1 for e in normal_errors if e >= cand)
        far = false_alarms / max(1e-6, normal_camera_hours)
        if far <= target_far_per_hour:
            raw_threshold = cand
            achieved_far = far
            break

    # If even the max normal error exceeds target_far (due to short duration),
    # pick 105% of maximum normal error to guarantee 0 false alarms on val
    if raw_threshold is None:
        raw_threshold = float(np.max(sorted_normal) * 1.05) if sorted_normal else 0.05
        achieved_far = 0.0
        logger.info(f"Selected zero-FAR threshold on validation set: {raw_threshold:.6f}")
    else:
        logger.info(f"Found threshold {raw_threshold:.6f} achieving FAR {achieved_far:.2f}/camera-hour")

    # Normalization bounds: min_error and max_error
    min_error = float(np.percentile(normal_errors, 5)) if normal_errors else 0.01
    max_error = float(np.percentile(accident_errors, 95)) if accident_errors else (float(np.max(normal_errors)) * 1.5)
    if max_error <= min_error:
        max_error = min_error + 0.10

    # Map raw threshold to [0.0, 1.0]
    norm_threshold = float(np.clip((raw_threshold - min_error) / (max_error - min_error), 0.0, 1.0))

    # Platt scaling (Logistic Regression on validation errors)
    platt_a = 1.0
    platt_b = 0.0
    try:
        X_val = np.array(normal_errors + accident_errors).reshape(-1, 1)
        y_val = np.array([0] * len(normal_errors) + [1] * len(accident_errors))
        if len(np.unique(y_val)) > 1:
            clf = LogisticRegression(random_state=42)
            clf.fit(X_val, y_val)
            platt_a = float(clf.coef_[0][0])
            platt_b = float(clf.intercept_[0])
            logger.info(f"Platt scaling parameters: coef={platt_a:.4f}, intercept={platt_b:.4f}")
    except Exception as e:
        logger.warning(f"Could not fit Platt scaling: {e}")

    # Compute validation performance metrics at calibrated threshold
    val_tp = sum(1 for e in accident_errors if e >= raw_threshold)
    val_fn = sum(1 for e in accident_errors if e < raw_threshold)
    val_fp = sum(1 for e in normal_errors if e >= raw_threshold)
    val_tn = sum(1 for e in normal_errors if e < raw_threshold)

    val_accuracy = (val_tp + val_tn) / max(1, len(val_records))
    val_precision = val_tp / max(1, (val_tp + val_fp))
    val_recall = val_tp / max(1, (val_tp + val_fn))
    val_f1 = (2 * val_precision * val_recall) / max(1e-6, (val_precision + val_recall))

    logger.info(
        f"Validation Results: Acc={val_accuracy*100:.1f}%, Recall={val_recall*100:.1f}%, "
        f"Precision={val_precision*100:.1f}%, F1={val_f1:.3f} (FP={val_fp}, FN={val_fn})"
    )

    calibration_payload = {
        "scorer": "convae",
        "calibration_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "checkpoint_file": checkpoint_path.name,
        "checkpoint_hash": get_file_hash(checkpoint_path),
        "tuning_split": "val",
        "test_split_touched": False,
        "target_far_per_hour": target_far_per_hour,
        "achieved_far_per_hour": round(achieved_far, 2),
        "normal_camera_hours": round(normal_camera_hours, 4),
        "raw_threshold": round(raw_threshold, 6),
        "threshold": round(norm_threshold, 4),
        "min_error": round(min_error, 6),
        "max_error": round(max_error, 6),
        "platt_a": round(platt_a, 4),
        "platt_b": round(platt_b, 4),
        "val_summary": {
            "normal_clips": len(normal_records),
            "accident_clips": len(accident_records),
            "val_accuracy": round(val_accuracy, 4),
            "val_precision": round(val_precision, 4),
            "val_recall": round(val_recall, 4),
            "val_f1": round(val_f1, 4),
            "tp": val_tp,
            "fp": val_fp,
            "tn": val_tn,
            "fn": val_fn,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(calibration_payload, f, indent=2)

    logger.info(f"Calibration saved successfully to {output_path}")
    return calibration_payload


def main():
    parser = argparse.ArgumentParser(description="Calibrate ConvAE on validation split")
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data" / "manifest.csv", help="Path to manifest CSV")
    parser.add_argument("--checkpoint", type=Path, default=None, help="Path to checkpoint .pth")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "artifacts" / "calibration" / "convae_calibration.json", help="Path to output calibration JSON")
    parser.add_argument("--target-far", type=float, default=1.0, help="Target false alarm rate per camera-hour")
    parser.add_argument("--device", type=str, default=None, choices=["cpu", "mps", "cuda"], help="Computation device")
    args = parser.parse_args()

    # Auto-resolve checkpoint if not provided
    ckpt = args.checkpoint
    if not ckpt:
        candidates = [
            PROJECT_ROOT / "artifacts" / "checkpoints" / "convae" / "best_model.pth",
            PROJECT_ROOT / "artifacts" / "checkpoints" / "convae" / "smoke_checkpoint.pth",
        ]
        for c in candidates:
            if c.exists():
                ckpt = c
                break

    if not ckpt or not ckpt.exists():
        logger.error("No valid checkpoint found to calibrate.")
        sys.exit(1)

    device = args.device
    if not device:
        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

    calibrate_convae(
        manifest_path=args.manifest,
        checkpoint_path=ckpt,
        output_path=args.output,
        target_far_per_hour=args.target_far,
        device=device,
    )


if __name__ == "__main__":
    main()

