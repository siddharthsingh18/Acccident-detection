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

