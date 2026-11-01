import json
from pathlib import Path
import pytest
import numpy as np
import torch

from scripts.train_convae import train_convae, get_file_hash, get_git_commit
from scripts.calibrate import calibrate_convae
from scripts.retrain_svm import retrain_vif_svm
from argus_ml.scoring.convae import ConvAEScorer
from argus_ml.scoring.base import ClipInput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_convae_smoke_training_and_metadata(tmp_path):
    """Verify ConvAE training generates valid state_dict checkpoint and complete metadata JSON."""
    manifest_path = PROJECT_ROOT / "data" / "manifest.csv"
    assert manifest_path.exists()

    config = {
        "name": "test_smoke",
        "epochs": 1,
        "batch_size": 2,
        "learning_rate": 0.001,
        "window_size": 30,
        "stride": 15,
        "patience": 1,
        "max_train_samples": 4,
        "max_val_samples": 2,
        "seed": 42,
    }

    ckpt_path, meta_path, metadata = train_convae(
        config=config,
        manifest_path=manifest_path,
        output_dir=tmp_path,
        device="cpu",
    )

    assert ckpt_path.exists()
    assert meta_path.exists()
    assert ckpt_path.stat().st_size > 100_000

    # Ground rule: torch.load with weights_only=True
    state_dict = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    assert isinstance(state_dict, dict)
    assert "spatial_encoder.conv1.weight" in state_dict

    with open(meta_path, "r", encoding="utf-8") as f:
        meta_loaded = json.load(f)

    assert meta_loaded["model_name"] == "convae"
    assert meta_loaded["checkpoint_file"] == ckpt_path.name
    assert "git_commit" in meta_loaded
    assert "manifest_hash" in meta_loaded
    assert "hardware" in meta_loaded
    assert "hyperparameters" in meta_loaded
    assert "metrics" in meta_loaded
    assert meta_loaded["metrics"]["best_val_loss"] > 0


def test_calibration_strictly_uses_val_split_and_computes_mappings(tmp_path):
    """Verify calibration evaluates strictly on val split and creates valid sidecar mapping."""
    manifest_path = PROJECT_ROOT / "data" / "manifest.csv"
    ckpt_path = PROJECT_ROOT / "artifacts" / "checkpoints" / "convae" / "best_model.pth"
    if not ckpt_path.exists():
        ckpt_path = PROJECT_ROOT / "artifacts" / "checkpoints" / "convae" / "smoke_checkpoint.pth"

    calib_out = tmp_path / "convae_calibration.json"

    result = calibrate_convae(
        manifest_path=manifest_path,
        checkpoint_path=ckpt_path,
        output_path=calib_out,
        target_far_per_hour=1.0,
        device="cpu",
    )

    assert calib_out.exists()
    assert result["scorer"] == "convae"
    assert result["tuning_split"] == "val"
    assert result["test_split_touched"] is False
    assert 0.0 <= result["threshold"] <= 1.0
    assert result["min_error"] < result["max_error"]
    assert "val_summary" in result
    assert result["val_summary"]["normal_clips"] == 19
    assert result["val_summary"]["accident_clips"] == 26


def test_retrained_svm_and_onnx_parity(tmp_path):
    """Verify SVM retraining produces valid metrics, exports ONNX, and passes parity verification."""
    manifest_path = PROJECT_ROOT / "data" / "manifest.csv"
    old_model_path = PROJECT_ROOT / "VIF" / "model-svm1.sav"
    cache_path = PROJECT_ROOT / "data" / "vif_features_cache.npz"
    output_onnx = tmp_path / "vif_svm_retrained.onnx"

    results = retrain_vif_svm(
        manifest_path=manifest_path,
        old_model_path=old_model_path,
        output_onnx_path=output_onnx,
        replace_current=False,
        cache_path=cache_path,
    )

    assert output_onnx.exists()
    assert results["parity_match_rate"] == 100.0
    assert "old_metrics" in results
    assert "new_metrics" in results
    assert results["new_metrics"]["recall"] >= 0.50
    assert results["new_metrics"]["f1"] >= 0.50


def test_convae_scorer_with_real_trained_checkpoint_and_calibration():
    """Verify ConvAEScorer integrates cleanly with the real checkpoint and calibration file."""
    ckpt_path = PROJECT_ROOT / "artifacts" / "checkpoints" / "convae" / "best_model.pth"
    calib_path = PROJECT_ROOT / "artifacts" / "calibration" / "convae_calibration.json"

    assert ckpt_path.exists()
    assert calib_path.exists()

    scorer = ConvAEScorer(
        checkpoint_path=ckpt_path,
        calibration_path=calib_path,
        allow_dev=False,
    )

    assert scorer.available is True
    assert scorer.calibrated is True
    assert scorer.trained_on != "DEV SMOKE TEST (not for real use)"
    assert scorer.calibration_date is not None

    # Score dummy sequence
    dummy_frames = [np.random.randint(0, 255, (360, 480, 3), dtype=np.uint8) for _ in range(30)]
    clip = ClipInput(frames=dummy_frames, camera_id="cam_test_p4")
    res = scorer.score(clip)

    assert isinstance(res.score, float)
    assert 0.0 <= res.score <= 1.0
    assert isinstance(res.fired, bool)
    assert res.calibrated is True
    assert res.latency_ms is not None
    assert res.latency_ms > 0
    assert "reconstruction_mse" in res.details

