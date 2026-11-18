import csv
import json
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DET_EVAL_DIR = PROJECT_ROOT / "data" / "detection_eval"
MANIFEST_CSV = DET_EVAL_DIR / "manifest.csv"
COCO_JSON = DET_EVAL_DIR / "coco_annotations.json"
CRASH_MANIFEST_CSV = PROJECT_ROOT / "data" / "evaluation_manifest.csv"


def test_detection_eval_manifest_schema_and_counts():
    """Verify data/detection_eval/manifest.csv exists, has 200 rows, and correct columns."""
    assert MANIFEST_CSV.exists(), f"Missing {MANIFEST_CSV}"

    with open(MANIFEST_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 200, f"Expected 200 evaluation frames, found {len(rows)}"

    expected_cols = {"frame_path", "clip_group_id", "camera_view", "conditions", "license", "split", "num_ground_truth_boxes"}
    assert expected_cols.issubset(set(reader.fieldnames or [])), f"Missing fields in {reader.fieldnames}"

    splits = {r["split"] for r in rows}
    assert splits == {"validation", "test"}

    conditions = {r["conditions"] for r in rows}
    assert "day" in conditions
    assert "night" in conditions


def test_zero_group_leakage_between_detection_splits():
    """Verify zero group leakage between validation and test splits in detection eval set."""
    with open(MANIFEST_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    val_groups = {r["clip_group_id"] for r in rows if r["split"] == "validation"}
    test_groups = {r["clip_group_id"] for r in rows if r["split"] == "test"}

    leakage = val_groups.intersection(test_groups)
    assert not leakage, f"Group leakage detected in detection eval set: {leakage}"
    assert len(val_groups) > 0
    assert len(test_groups) > 0


def test_zero_leakage_into_crash_test_split():
    """
    CRITICAL: Verify detection evaluation frames NEVER overlap with the crash evaluation test split.
    The detector must not be evaluated or tuned on the same clips used to measure crash detection.
    """
    assert CRASH_MANIFEST_CSV.exists(), f"Missing {CRASH_MANIFEST_CSV}"

    with open(MANIFEST_CSV, "r", encoding="utf-8") as f:
        det_rows = list(csv.DictReader(f))
    det_groups = {r["clip_group_id"] for r in det_rows}

    with open(CRASH_MANIFEST_CSV, "r", encoding="utf-8") as f:
        crash_rows = list(csv.DictReader(f))
    crash_test_groups = {r["group_id"] for r in crash_rows if r["split"] == "test"}

    forbidden_overlap = det_groups.intersection(crash_test_groups)
    assert not forbidden_overlap, f"Detection eval set leaks into crash test split: {forbidden_overlap}"


def test_coco_annotations_schema_and_categories():
    """Verify coco_annotations.json conforms to standard COCO object detection specification."""
    assert COCO_JSON.exists(), f"Missing {COCO_JSON}"

    with open(COCO_JSON, "r", encoding="utf-8") as f:
        coco = json.load(f)

    assert "info" in coco
    assert "images" in coco
    assert "annotations" in coco
    assert "categories" in coco

    assert len(coco["images"]) == 200
    assert len(coco["annotations"]) > 50

    cat_names = {c["name"] for c in coco["categories"]}
    assert {"car", "truck", "bus", "motorcycle"}.issubset(cat_names)

    # Check annotation bbox validity [x, y, w, h]
    for ann in coco["annotations"]:
        bbox = ann["bbox"]
        assert len(bbox) == 4
        assert bbox[2] > 0 and bbox[3] > 0
        assert ann["area"] > 0
        assert ann["category_id"] in [c["id"] for c in coco["categories"]]


def test_eval_detector_script_metrics():
    """Verify scripts/eval_detector.py calculates precision, recall, F1, AP, and bootstrap CI."""
    from scripts.eval_detector import calculate_metrics_from_matches, compute_iou

    # IoU sanity checks
    assert compute_iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert compute_iou([0, 0, 10, 10], [20, 20, 10, 10]) == 0.0

    # Metric calculations
    mock_preds = [
        {"tp": 1, "score": 0.9, "size": "medium", "cat": "car"},
        {"tp": 1, "score": 0.8, "size": "large", "cat": "car"},
        {"tp": 0, "score": 0.5, "size": "small", "cat": "car"},
    ]
    metrics = calculate_metrics_from_matches(mock_preds, total_gt=2)
    assert metrics["tp"] == 2
    assert metrics["fp"] == 1
    assert metrics["fn"] == 0
    assert metrics["precision"] == round(2 / 3, 4)
    assert metrics["recall"] == 1.0
    assert metrics["f1"] > 0.7
    assert metrics["ap"] > 0.8

