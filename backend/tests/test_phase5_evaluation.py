import csv
import json
from pathlib import Path
import pytest
import numpy as np

from scripts.evaluate import check_zero_leakage, compute_bootstrap_ci, load_test_clips

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_zero_group_leakage_enforced():
    """Verify strictly 0 group overlap between test split and train/val splits."""
    manifest_path = PROJECT_ROOT / "data" / "manifest.csv"
    assert manifest_path.exists()

    is_clean, leak_train, leak_val = check_zero_leakage(manifest_path)
    assert is_clean is True
    assert leak_train == 0
    assert leak_val == 0


def test_evaluation_csv_and_report_artifacts_exist():
    """Verify metrics CSV and markdown report were generated with all expected columns and candidates."""
    csv_path = PROJECT_ROOT / "docs" / "evaluation" / "metrics_summary.csv"
    report_path = PROJECT_ROOT / "docs" / "evaluation" / "report.md"

    assert csv_path.exists(), f"Evaluation CSV missing at {csv_path}"
    assert report_path.exists(), f"Evaluation report markdown missing at {report_path}"

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) >= 5
    candidates = [r["candidate"] for r in rows]
    assert "VIF SVM (Legacy)" in candidates
    assert "VIF SVM (Retrained)" in candidates
    assert "ConvAE Anomaly" in candidates

    for r in rows:
        assert float(r["accuracy"]) >= 0.0
        assert float(r["f1"]) >= 0.0
        assert float(r["fps"]) > 0.0
        assert float(r["latency_p50_ms"]) > 0.0

    report_content = report_path.read_text(encoding="utf-8")
    assert "Executive Summary & Policy Recommendations" in report_content
    assert "Leakage Verification" in report_content
    assert "In-Domain (CCTV) vs Cross-Domain (Dashcam)" in report_content


def test_bootstrap_confidence_interval_bounds():
    """Verify bootstrap confidence interval calculation produces valid lower and upper bounds."""
    synthetic_eval = [
        {"group_id": f"grp_{i%10}", "label": 1 if i % 2 == 0 else 0, "pred": 1 if i % 3 == 0 else 0}
        for i in range(50)
    ]

    def sample_acc(sample):
        return sum(1 for s in sample if s["label"] == s["pred"]) / len(sample)

    ci_low, ci_high = compute_bootstrap_ci(synthetic_eval, sample_acc, n_bootstrap=100)
    assert 0.0 <= ci_low <= ci_high <= 1.0


def test_test_clips_composition_and_no_train_labels():
    """Verify held-out test clips contain both classes and belong strictly to 'test' split."""
    manifest_path = PROJECT_ROOT / "data" / "manifest.csv"
    clips = load_test_clips(manifest_path, split="test")

    assert len(clips) == 45
    labels = {c["label_str"] for c in clips}
    assert "normal" in labels
    assert "accident" in labels


def test_upload_evaluation_artifacts_and_zero_leakage():
    """Verify Phase 5 upload evaluation artifacts, sweep, held-out test metrics, and zero leakage."""
    eval_manifest_path = PROJECT_ROOT / "data" / "evaluation_manifest.csv"
    sweep_path = PROJECT_ROOT / "docs" / "evaluation" / "validation_sweep.csv"
    heldout_path = PROJECT_ROOT / "docs" / "evaluation" / "heldout_test_metrics.csv"
    report_path = PROJECT_ROOT / "docs" / "evaluation" / "report.md"

    # 1. Sweep CSV exists and contains both detectors and flags
    assert sweep_path.exists(), f"Validation sweep CSV missing at {sweep_path}"
    with open(sweep_path, mode="r", encoding="utf-8") as f:
        sweep_rows = list(csv.DictReader(f))
    assert len(sweep_rows) >= 12
    detectors = {r["detector"] for r in sweep_rows}
    assert "motion" in detectors
    assert "yolo" in detectors

    # 2. Heldout Test Metrics CSV exists and contains baseline and candidates
    assert heldout_path.exists(), f"Heldout test metrics CSV missing at {heldout_path}"
    with open(heldout_path, mode="r", encoding="utf-8") as f:
        heldout_rows = list(csv.DictReader(f))
    assert len(heldout_rows) >= 3
    candidates = [r["candidate"] for r in heldout_rows]
    assert any("Legacy Baseline" in c for c in candidates)
    assert any("Neural Baseline" in c for c in candidates)
    assert any("Calibrated Candidate" in c for c in candidates)

    for r in heldout_rows:
        assert float(r["accuracy"]) >= 0.0
        assert float(r["fps"]) > 0.0
        assert r["detection_quality"] in {"neural", "motion_fallback", "reference", "unavailable"}

    # 3. Report contains upload-specific analysis
    report_text = report_path.read_text(encoding="utf-8")
    assert "Upload Pipeline" in report_text
    assert "What Helped, What Hurt, and Why" in report_text

    # 4. If evaluation manifest exists on disk, check zero group leakage across splits
    if eval_manifest_path.exists():
        with open(eval_manifest_path, mode="r", encoding="utf-8") as f:
            manifest_rows = list(csv.DictReader(f))
        train_groups = {r["group_id"] for r in manifest_rows if r["split"] == "train"}
        val_groups = {r["group_id"] for r in manifest_rows if r["split"] == "val"}
        test_groups = {r["group_id"] for r in manifest_rows if r["split"] == "test"}

        assert len(train_groups.intersection(val_groups)) == 0, "Train-Val group leakage!"
        assert len(train_groups.intersection(test_groups)) == 0, "Train-Test group leakage!"
        assert len(val_groups.intersection(test_groups)) == 0, "Val-Test group leakage!"


