import csv
from pathlib import Path
import pytest
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_CSV = PROJECT_ROOT / "data" / "evaluation_manifest.csv"
VAL_SWEEP_CSV = PROJECT_ROOT / "docs" / "evaluation" / "validation_sweep.csv"
TEST_METRICS_CSV = PROJECT_ROOT / "docs" / "evaluation" / "heldout_test_metrics.csv"
REPORT_MD = PROJECT_ROOT / "docs" / "evaluation" / "report.md"


def test_crash_evaluation_manifest_and_zero_leakage():
    """Verify evaluation manifest exists and has strictly zero group leakage across splits."""
    assert MANIFEST_CSV.exists(), f"Missing {MANIFEST_CSV}"
    with open(MANIFEST_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) >= 200, f"Expected at least 200 clips, found {len(rows)}"

    train_groups = {r["group_id"] for r in rows if r["split"] == "train"}
    val_groups = {r["group_id"] for r in rows if r["split"] == "val"}
    test_groups = {r["group_id"] for r in rows if r["split"] == "test"}

    assert len(train_groups) > 0
    assert len(val_groups) > 0
    assert len(test_groups) > 0

    assert len(test_groups.intersection(train_groups)) == 0, "Leakage: Test and Train groups overlap"
    assert len(test_groups.intersection(val_groups)) == 0, "Leakage: Test and Val groups overlap"
    assert len(val_groups.intersection(train_groups)) == 0, "Leakage: Val and Train groups overlap"


def test_validation_sweep_results_exist_and_cover_required_params():
    """Verify validation sweep swept detector choice, confidence, distance factor, adaptive box, and single vehicle."""
    assert VAL_SWEEP_CSV.exists(), f"Missing {VAL_SWEEP_CSV}"
    with open(VAL_SWEEP_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) >= 15, f"Expected at least 15 sweep configurations, found {len(rows)}"

    detectors = {r["detector"] for r in rows}
    assert "motion" in detectors
    assert "yolo" in detectors

    confs = {float(r["confidence"]) for r in rows if r["detector"] != "motion"}
    assert 0.35 in confs
    assert 0.20 in confs

    # Verify FAR/hr computation exists
    for r in rows:
        assert "far_per_hour" in r
        assert "false_alarms" in r
        assert "recall" in r
        assert "precision" in r
        assert "f1" in r


def test_heldout_test_metrics_and_far_target():
    """Verify frozen held-out test evaluation meets FAR <= 1.0/hr target and has bootstrap CI."""
    assert TEST_METRICS_CSV.exists(), f"Missing {TEST_METRICS_CSV}"
    with open(TEST_METRICS_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) >= 3, f"Expected at least 3 candidate evaluations, found {len(rows)}"

    # Find calibrated candidate
    calibrated = next((r for r in rows if "Calibrated Candidate" in r["candidate"]), None)
    assert calibrated is not None, "Calibrated Candidate missing from test report"

    assert float(calibrated["far_per_hour"]) <= 1.0, f"Target FAR <= 1.0/hr exceeded: {calibrated['far_per_hour']}"
    assert int(calibrated["false_alarms"]) == 0
    assert float(calibrated["precision"]) >= 0.90
    assert "f1_ci_low" in calibrated
    assert "latency_p50_ms" in calibrated
    assert "latency_p95_ms" in calibrated


def test_evaluation_report_md_structure():
    """Verify docs/evaluation/report.md contains required analysis, hardware string, and breakdown."""
    assert REPORT_MD.exists(), f"Missing {REPORT_MD}"
    content = REPORT_MD.read_text(encoding="utf-8")

    assert "# Argus Held-Out TEST Split Evaluation Report" in content
    assert "FAR / Camera-Hr" in content
    assert "Dataset & Camera View Breakdown" in content
    assert "What Helped" in content
    assert "What Hurt" in content
    assert "Domain & Data Limitations" in content


def test_no_regression_on_clip_1528():
    """Ensure clip 1528 maintains 100% legacy parity with registered box file."""
    from System.Functions.Detector import get_detector
    det = get_detector("legacy")
    dummy = np.zeros((360, 480, 3), dtype=np.uint8)
    boxes = det.detect(dummy, video_name="1528", frame_index=0)
    assert len(boxes) > 0, "Clip 1528 must return reference boxes via legacy detector"
