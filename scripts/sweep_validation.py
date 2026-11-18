#!/usr/bin/env python3
"""
scripts/sweep_validation.py

Phase 5 Validation Split Sweep.
Sweeps over:
  1. Detector choice: 'motion' vs 'yolo' (ModernYoloDetector SSDLite320)
  2. Phase 4 Geometry flags:
     - Baseline (all flags off)
     - CRASH_ADAPTIVE_BOX_FILTER (on vs off)
     - CRASH_DISTANCE_FACTOR (0.25 vs 0.35)
     - CRASH_SINGLE_VEHICLE (on vs off)
     - Combinations

Evaluates on the VALIDATION split ONLY (37 unbundled CCTV clips).
Computes Recall, Precision, F1, False Alarms, False Alarms per Camera-Hour, FPS, and Latency.
Selects the optimal operating configuration for the frozen test evaluation.
"""
import copy
import csv
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Tuple
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from System.Functions.Tracking import Tracking
from System.Functions.Crashing import Crashing
from System.Functions.Detector.yolo import ModernYoloDetector
from System.Functions.Detector.motion import MotionFallbackDetector
from VIF.vif import VIF
from argus_ml.preprocessing import load_video_frames

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sweep_val")


def load_val_clips(manifest_path: Path) -> List[Dict[str, Any]]:
    clips = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["split"].lower() != "val":
                continue
            vpath = PROJECT_ROOT / row["video_path"]
            if not vpath.exists():
                logger.warning(f"Clip not found: {vpath}")
                continue

            frames = load_video_frames(vpath, target_size=(480, 360))
            if not frames:
                continue

            # Ensure minimum 30 frames by padding if needed
            while len(frames) < 30:
                frames.append(frames[-1].copy())

            clips.append({
                "video_path": row["video_path"],
                "label": 1 if row["label"].lower() == "accident" else 0,
                "label_str": row["label"].lower(),
                "duration_s": float(row.get("duration_s", 1.0)),
                "group_id": row["group_id"],
                "frames": frames,
            })
    logger.info(f"Loaded {len(clips)} validation clips (accidents={sum(1 for c in clips if c['label']==1)}, normals={sum(1 for c in clips if c['label']==0)})")
    return clips


def evaluate_config(
    clips: List[Dict[str, Any]],
    detector_type: str,
    env_flags: Dict[str, str],
    vif: VIF,
    confidence: float = 0.35,
) -> Dict[str, Any]:
    # Set environment variables for this configuration
    for k, v in env_flags.items():
        os.environ[k] = v

    # Instantiate detector
    if detector_type == "motion":
        detector = MotionFallbackDetector()
        quality_str = "motion_fallback"
    else:
        detector = ModernYoloDetector(confidence_threshold=confidence)
        quality_str = "neural" if detector.is_available else "motion_fallback"

    tracking = Tracking()
    crashing = Crashing(vif)

    y_true = []
    y_pred = []
    latencies = []
    total_frames = 0
    t_start = time.perf_counter()

    for clip in clips:
        frames = clip["frames"]
        total_frames += len(frames)
        t0 = time.perf_counter()

        # Run detection on 30-frame window
        window = frames[:30]
        cur_boxes = detector.detect(
            window[0],
            ref_frame=window[min(5, len(window) - 1)],
            frame_width=480,
            frame_height=360,
        )

        trackers = tracking.track(window, cur_boxes, 480, 360)
        dims = crashing.crash(window, trackers, camera_id=101, starting_frame_id=1)
        decision = 1 if (dims and len(dims) > 0) else 0

        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt_ms)

        y_true.append(clip["label"])
        y_pred.append(decision)

    total_time = time.perf_counter() - t_start
    fps = total_frames / max(1e-6, total_time)

    y_t = np.array(y_true)
    y_p = np.array(y_pred)

    tp = int(np.sum((y_t == 1) & (y_p == 1)))
    fp = int(np.sum((y_t == 0) & (y_p == 1)))
    tn = int(np.sum((y_t == 0) & (y_p == 0)))
    fn = int(np.sum((y_t == 1) & (y_p == 0)))

    recall = tp / max(1, (tp + fn))
    prec = tp / max(1, (tp + fp))
    f1 = 2 * prec * recall / max(1e-6, (prec + recall))
    acc = (tp + tn) / max(1, len(y_true))

    # Normal camera duration in hours
    normal_duration_s = sum(c["duration_s"] for c in clips if c["label"] == 0)
    normal_hours = normal_duration_s / 3600.0
    far_per_hour = fp / max(1e-6, normal_hours)

    return {
        "detector": detector_type,
        "quality": quality_str,
        "confidence": confidence if detector_type != "motion" else 0.0,
        "flags": " ".join(f"{k}={v}" for k, v in env_flags.items() if v not in ("false", "0.25")),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "recall": round(recall, 4),
        "precision": round(prec, 4),
        "f1": round(f1, 4),
        "accuracy": round(acc, 4),
        "false_alarms": fp,
        "far_per_hour": round(far_per_hour, 1),
        "fps": round(fps, 1),
        "p50_latency_ms": round(float(np.percentile(latencies, 50)), 1),
    }


def main():
    manifest_path = PROJECT_ROOT / "data" / "evaluation_manifest.csv"
    if not manifest_path.exists():
        logger.error(f"Manifest not found: {manifest_path}")
        return 1

    clips = load_val_clips(manifest_path)
    if not clips:
        logger.error("No validation clips loaded")
        return 1

    vif = VIF()

    # Configurations to sweep
    flag_sets = [
        ("Baseline (dist=0.25)", {
            "CRASH_ADAPTIVE_BOX_FILTER": "false",
            "CRASH_DISTANCE_FACTOR": "0.25",
            "CRASH_SINGLE_VEHICLE": "false",
        }),
        ("Distance 0.33 Only", {
            "CRASH_ADAPTIVE_BOX_FILTER": "false",
            "CRASH_DISTANCE_FACTOR": "0.33",
            "CRASH_SINGLE_VEHICLE": "false",
        }),
        ("Distance 0.40 Only", {
            "CRASH_ADAPTIVE_BOX_FILTER": "false",
            "CRASH_DISTANCE_FACTOR": "0.40",
            "CRASH_SINGLE_VEHICLE": "false",
        }),
        ("Adaptive Box Only", {
            "CRASH_ADAPTIVE_BOX_FILTER": "true",
            "CRASH_ADAPTIVE_BOX_FRACTION": "0.04",
            "CRASH_DISTANCE_FACTOR": "0.25",
            "CRASH_SINGLE_VEHICLE": "false",
        }),
        ("Single Vehicle Only", {
            "CRASH_ADAPTIVE_BOX_FILTER": "false",
            "CRASH_DISTANCE_FACTOR": "0.25",
            "CRASH_SINGLE_VEHICLE": "true",
            "CRASH_SINGLE_DECEL_THRESHOLD": "0.60",
            "CRASH_SINGLE_HEADING_ANGLE": "45.0",
        }),
        ("Single Vehicle + Dist 0.33", {
            "CRASH_ADAPTIVE_BOX_FILTER": "false",
            "CRASH_DISTANCE_FACTOR": "0.33",
            "CRASH_SINGLE_VEHICLE": "true",
            "CRASH_SINGLE_DECEL_THRESHOLD": "0.60",
            "CRASH_SINGLE_HEADING_ANGLE": "45.0",
        }),
        ("Single Vehicle + Adaptive", {
            "CRASH_ADAPTIVE_BOX_FILTER": "true",
            "CRASH_ADAPTIVE_BOX_FRACTION": "0.04",
            "CRASH_DISTANCE_FACTOR": "0.25",
            "CRASH_SINGLE_VEHICLE": "true",
            "CRASH_SINGLE_DECEL_THRESHOLD": "0.60",
            "CRASH_SINGLE_HEADING_ANGLE": "45.0",
        }),
        ("All Flags Combined (dist=0.33)", {
            "CRASH_ADAPTIVE_BOX_FILTER": "true",
            "CRASH_ADAPTIVE_BOX_FRACTION": "0.04",
            "CRASH_DISTANCE_FACTOR": "0.33",
            "CRASH_SINGLE_VEHICLE": "true",
            "CRASH_SINGLE_DECEL_THRESHOLD": "0.60",
            "CRASH_SINGLE_HEADING_ANGLE": "45.0",
        }),
        ("All Flags Combined (dist=0.40)", {
            "CRASH_ADAPTIVE_BOX_FILTER": "true",
            "CRASH_ADAPTIVE_BOX_FRACTION": "0.04",
            "CRASH_DISTANCE_FACTOR": "0.40",
            "CRASH_SINGLE_VEHICLE": "true",
            "CRASH_SINGLE_DECEL_THRESHOLD": "0.60",
            "CRASH_SINGLE_HEADING_ANGLE": "45.0",
        }),
    ]

    print("\n" + "=" * 98)
    print("PHASE 4 VALIDATION SWEEP: DETECTOR & CRASH GEOMETRY CONFIGURATIONS")
    print("=" * 98)
    print(f"{'Config / Detector':<46} {'Quality':<14} {'Conf':<6} {'Recall':<8} {'Prec':<8} {'F1':<8} {'FA':<5} {'FAR/hr':<8} {'FPS':<6}")
    print("-" * 98)

    results = []

    # 1. Motion Fallback Detector on all configs
    for name, flags in flag_sets[:5]:
        res = evaluate_config(clips, "motion", flags, vif)
        res["name"] = f"Motion - {name}"
        results.append(res)
        print(f"{res['name']:<46} {res['quality']:<14} {'N/A':<6} {res['recall']:<8.3f} {res['precision']:<8.3f} {res['f1']:<8.3f} {res['false_alarms']:<5} {res['far_per_hour']:<8.1f} {res['fps']:<6.1f}")

    print("-" * 98)

    # 2. Modern Neural YOLO Detector with default confidence (0.35)
    for name, flags in flag_sets:
        res = evaluate_config(clips, "yolo", flags, vif, confidence=0.35)
        res["name"] = f"Neural(0.35) - {name}"
        results.append(res)
        print(f"{res['name']:<46} {res['quality']:<14} {'0.35':<6} {res['recall']:<8.3f} {res['precision']:<8.3f} {res['f1']:<8.3f} {res['false_alarms']:<5} {res['far_per_hour']:<8.1f} {res['fps']:<6.1f}")

    print("-" * 98)

    # 3. Modern Neural YOLO Detector with optimal validation confidence (0.20)
    for name, flags in flag_sets:
        res = evaluate_config(clips, "yolo", flags, vif, confidence=0.20)
        res["name"] = f"Neural(0.20) - {name}"
        results.append(res)
        print(f"{res['name']:<46} {res['quality']:<14} {'0.20':<6} {res['recall']:<8.3f} {res['precision']:<8.3f} {res['f1']:<8.3f} {res['false_alarms']:<5} {res['far_per_hour']:<8.1f} {res['fps']:<6.1f}")

    print("=" * 98)

    # Select configuration with best recall at target of at most 1 false alarm / hour (or 0 FA on validation)
    valid_candidates = [r for r in results if r["false_alarms"] == 0 or r["far_per_hour"] <= 1.0]
    if valid_candidates:
        best_candidate = max(valid_candidates, key=lambda r: (r["recall"], r["f1"]))
        print("\n>>> OPTIMAL OPERATING CONFIGURATION SELECTED (Validation Recall Max with FAR <= 1.0/hr):")
        print(f"    Name: {best_candidate['name']}")
        print(f"    Detector: {best_candidate['detector']} (Conf: {best_candidate['confidence']})")
        print(f"    Recall: {best_candidate['recall']:.4f} | Precision: {best_candidate['precision']:.4f} | F1: {best_candidate['f1']:.4f}")
        print(f"    False Alarms: {best_candidate['false_alarms']} (FAR/hr: {best_candidate['far_per_hour']:.1f})")
    else:
        best_candidate = results[0]

    # Save sweep results to CSV
    sweep_csv = PROJECT_ROOT / "docs" / "evaluation" / "validation_sweep.csv"
    sweep_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(sweep_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"Saved validation sweep results to {sweep_csv}")
    return 0

    logger.info(f"Saved validation sweep results to {sweep_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
