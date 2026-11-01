import csv
import json
from pathlib import Path
import pytest
import numpy as np

from argus_ml.preprocessing import (
    create_sliding_windows,
    preprocess_for_convae,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_WINDOW_STRIDE,
)
from argus_ml.scoring.convae import ConvAEScorer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_manifest_exists_and_schema():
    """Verify manifest.csv exists, is non-empty, and has all required fields."""
    manifest_csv = PROJECT_ROOT / "data" / "manifest.csv"
    manifest_jsonl = PROJECT_ROOT / "data" / "manifest.jsonl"
    if not manifest_csv.exists():
        from scripts.data.make_manifest import generate_manifest
        generate_manifest(manifest_csv, manifest_jsonl)

    assert manifest_csv.exists(), "data/manifest.csv not found"

    with open(manifest_csv, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) > 50, f"Expected > 50 rows in manifest, found {len(rows)}"
    required_fields = {
        "video_path",
        "label",
        "source",
        "camera_view",
        "license",
        "group_id",
        "split",
        "frames_count",
        "duration_s",
    }
    assert required_fields.issubset(set(reader.fieldnames or []))

    labels = {r["label"] for r in rows}
    assert "accident" in labels
    assert "normal" in labels

    splits = {r["split"] for r in rows}
    assert splits == {"train", "val", "test"}


def test_zero_group_leakage_across_splits():
    """
    CRITICAL TEST: Ensure zero group overlap between train, val, and test splits.
    Fails if any camera or video group leaks across splits.
    """
    manifest_csv = PROJECT_ROOT / "data" / "manifest.csv"
    with open(manifest_csv, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    train_groups = {r["group_id"] for r in rows if r["split"] == "train"}
    val_groups = {r["group_id"] for r in rows if r["split"] == "val"}
    test_groups = {r["group_id"] for r in rows if r["split"] == "test"}

    # Assert mutual disjointness
    train_val_leakage = train_groups.intersection(val_groups)
    train_test_leakage = train_groups.intersection(test_groups)
    val_test_leakage = val_groups.intersection(test_groups)

    assert len(train_val_leakage) == 0, f"Leakage detected between train and val: {train_val_leakage}"
    assert len(train_test_leakage) == 0, f"Leakage detected between train and test: {train_test_leakage}"
    assert len(val_test_leakage) == 0, f"Leakage detected between val and test: {val_test_leakage}"


def test_preprocessing_sliding_windows_and_convae_tensor():
    """Verify sliding windows and ConvAE tensor preprocessing pipeline."""
    # Create 60 dummy frames
    frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(60)]

    windows = create_sliding_windows(frames, window_size=30, stride=15)
    # (60 - 30) // 15 + 1 = 3 windows
    assert len(windows) == 3
    for w in windows:
        assert len(w) == 30

    tensor = preprocess_for_convae(windows[0], target_size=(227, 227), mode="gray")
    assert tensor.shape == (30, 227, 227)
    assert tensor.dtype == np.float32
    assert 0.0 <= tensor.min() <= tensor.max() <= 1.0


def test_dev_smoke_checkpoint_metadata_and_availability(monkeypatch):
    """
    Verify smoke_checkpoint.pth metadata marks dev_only: true,
    ConvAEScorer reports available=false when flag is off, and reports
    trained_on='DEV SMOKE TEST (not for real use)' when flag is on.
    """
    ckpt_dir = PROJECT_ROOT / "artifacts" / "checkpoints" / "convae"
    meta_file = ckpt_dir / "smoke_checkpoint.json"
    ckpt_file = ckpt_dir / "smoke_checkpoint.pth"

    assert meta_file.exists()
    assert ckpt_file.exists()

    with open(meta_file, "r") as f:
        meta = json.load(f)
    assert meta.get("dev_only") is True
    assert "DEV SMOKE TEST" in meta.get("trained_on", "")

    # Flag off -> available is False
    monkeypatch.setenv("ARGUS_ALLOW_DEV_CHECKPOINT", "false")
    scorer_off = ConvAEScorer(checkpoint_path=ckpt_file, allow_dev=False)
    assert scorer_off.available is False

    # Flag on -> available is True, tagged DEV SMOKE TEST
    monkeypatch.setenv("ARGUS_ALLOW_DEV_CHECKPOINT", "true")
    scorer_on = ConvAEScorer(checkpoint_path=ckpt_file, allow_dev=True)
    assert scorer_on.available is True
    assert "DEV SMOKE TEST" in scorer_on.trained_on
