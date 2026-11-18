#!/usr/bin/env python3
"""
scripts/sweep_detector.py

Performs a rigorous confidence threshold sweep (0.10 to 0.60) on VALIDATION frames only.
Computes Precision, Recall, F1, AP@0.5, and FPS.
Picks the best confidence threshold on validation, freezes it, and evaluates ONCE on the frozen TEST split.
Saves results to:
  - docs/evaluation/detector_validation_sweep.csv
  - docs/evaluation/detector_test_report.csv
"""
import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.eval_detector import run_evaluation, print_report_table

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sweep_detector")

SWEEP_CSV = PROJECT_ROOT / "docs" / "evaluation" / "detector_validation_sweep.csv"
TEST_CSV = PROJECT_ROOT / "docs" / "evaluation" / "detector_test_report.csv"


def run_sweep():
    SWEEP_CSV.parent.mkdir(parents=True, exist_ok=True)
    conf_values = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]

    sweep_results = []
    print("\n" + "=" * 78)
    print(" ARGUS DETECTOR CONFIDENCE SWEEP (VALIDATION SPLIT ONLY)")
    print("=" * 78)
    print(f"{'Conf':<8} {'Precision':<10} {'Recall':<10} {'F1':<10} {'AP@0.5':<10} {'FPS':<8} {'TP':<6} {'FP':<6} {'FN':<6}")
    print("-" * 78)

    best_conf = 0.35
    best_f1 = -1.0

    for conf in conf_values:
        rep = run_evaluation(
            split="validation",
            detector_conf=conf,
            bootstrap_iterations=200
        )
        ov = rep["overall"]
        sweep_results.append({
            "confidence": conf,
            "precision": ov["precision"],
            "recall": ov["recall"],
            "f1": ov["f1"],
            "ap": ov["ap"],
            "fps": rep["fps"],
            "latency_ms": rep["latency_ms"],
            "tp": ov["tp"],
            "fp": ov["fp"],
            "fn": ov["fn"],
            "gt": ov["gt"],
        })

        print(f"{conf:<8.2f} {ov['precision']:<10.4f} {ov['recall']:<10.4f} {ov['f1']:<10.4f} {ov['ap']:<10.4f} {rep['fps']:<8.1f} {ov['tp']:<6} {ov['fp']:<6} {ov['fn']:<6}")

        if ov["f1"] > best_f1:
            best_f1 = ov["f1"]
            best_conf = conf

    # Write Validation Sweep CSV
    with open(SWEEP_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(sweep_results[0].keys()))
        writer.writeheader()
        writer.writerows(sweep_results)
    print(f"\n✓ Saved validation sweep results to: {SWEEP_CSV}")
    print(f"✓ Best validation F1: {best_f1:.4f} at confidence = {best_conf:.2f}")

    # Freeze threshold and evaluate ONCE on held-out TEST split
    print("\n" + "=" * 78)
    print(f" FROZEN EVALUATION ON HELD-OUT TEST SPLIT (CONFIDENCE = {best_conf:.2f})")
    print("=" * 78)
    test_rep = run_evaluation(
        split="test",
        detector_conf=best_conf,
        bootstrap_iterations=1000
    )
    print_report_table(test_rep)

    # Save Frozen Test Result CSV
    test_ov = test_rep["overall"]
    test_row = [{
        "split": "test",
        "frozen_confidence": best_conf,
        "detector_backend": test_rep["detector_backend"],
        "frames": test_rep["frames_evaluated"],
        "precision": test_ov["precision"],
        "precision_ci95_low": test_ov["precision_ci95"][0],
        "precision_ci95_high": test_ov["precision_ci95"][1],
        "recall": test_ov["recall"],
        "recall_ci95_low": test_ov["recall_ci95"][0],
        "recall_ci95_high": test_ov["recall_ci95"][1],
        "f1": test_ov["f1"],
        "f1_ci95_low": test_ov["f1_ci95"][0],
        "f1_ci95_high": test_ov["f1_ci95"][1],
        "ap": test_ov["ap"],
        "ap_ci95_low": test_ov["ap_ci95"][0],
        "ap_ci95_high": test_ov["ap_ci95"][1],
        "fps": test_rep["fps"],
        "latency_ms": test_rep["latency_ms"],
        "tp": test_ov["tp"],
        "fp": test_ov["fp"],
        "fn": test_ov["fn"],
        "gt": test_ov["gt"],
    }]

    with open(TEST_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(test_row[0].keys()))
        writer.writeheader()
        writer.writerows(test_row)
    print(f"✓ Saved frozen test evaluation report to: {TEST_CSV}")


if __name__ == "__main__":
    run_sweep()

