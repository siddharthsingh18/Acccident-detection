import json
from pathlib import Path
import numpy as np
import pytest

from argus_ml.scoring.base import CrashScorer, ClipInput, ScoreResult
from argus_ml.scoring.vif_svm import VifSvmScorer
from argus_ml.scoring.convae import ConvAEScorer
from argus_ml.scoring.onnx_classifier import OnnxClassifierScorer
from argus_ml.scoring.ensemble import CrashEnsemble, EnsemblePolicy


class MockScorer:
    """Mock implementation of CrashScorer for unit testing."""
    def __init__(self, name: str, available: bool = True, score_val: float = 0.8, fired_val: bool = True):
        self.name = name
        self.available = available
        self.score_val = score_val
        self.fired_val = fired_val
        self.version = "1.0.0"
        self.trained_on = "Synthetic Test Data"
        self.calibration_date = "2026-11-01"
        self.reason_unavailable = None if available else "Mock offline"

    def score(self, clip: ClipInput) -> ScoreResult:
        if not self.available:
            return ScoreResult(
                score=0.0,
                fired=False,
                calibrated=False,
                latency_ms=None,
                reason_unavailable=self.reason_unavailable,
            )
        return ScoreResult(
            score=self.score_val,
            fired=self.fired_val,
            calibrated=True,
            latency_ms=12.5,
        )


def test_crash_scorer_protocol_conformance():
    """Verify that MockScorer and VifSvmScorer satisfy the runtime CrashScorer Protocol."""
    mock = MockScorer(name="test_scorer")
    assert isinstance(mock, CrashScorer)

    vif_scorer = VifSvmScorer(use_onnx=False)
    assert isinstance(vif_scorer, CrashScorer)
    assert vif_scorer.name == "vif_svm"


def test_vif_svm_scorer_execution_and_parity(tmp_path):
    """
    Verify VifSvmScorer runs on a synthetic frame sequence and produces consistent
    predictions between legacy scikit-learn and exported ONNX runtime.
    """
    # Create synthetic clip (20 frames of size 100x134)
    np.random.seed(42)
    frames = [np.random.randint(0, 255, (100, 134), dtype=np.uint8) for _ in range(20)]
    clip = ClipInput(frames=frames, camera_id=1528)

    # Scikit-learn scorer
    svm_scorer = VifSvmScorer(use_onnx=False)
    assert svm_scorer.available is True
    res_skl = svm_scorer.score(clip)

    assert isinstance(res_skl, ScoreResult)
    assert 0.0 <= res_skl.score <= 1.0
    assert isinstance(res_skl.fired, bool)
    assert res_skl.calibrated is True
    assert res_skl.latency_ms is not None

    # ONNX export and test parity
    onnx_path = tmp_path / "vif_svm.onnx"
    from scripts.export_vif_svm_onnx import export_vif_svm
    project_root = Path(__file__).resolve().parent.parent.parent
    vif_sav = project_root / "VIF" / "model-svm1.sav"
    export_ok = export_vif_svm(vif_sav, onnx_path)
    assert export_ok is True

    onnx_scorer = VifSvmScorer(model_path=onnx_path, use_onnx=True)
    assert onnx_scorer.available is True
    res_onnx = onnx_scorer.score(clip)

    # Parity check: predictions must agree
    assert res_skl.fired == res_onnx.fired
    assert abs(res_skl.score - res_onnx.score) < 0.15


def test_convae_scorer_availability_and_dev_checkpoint(tmp_path, monkeypatch):
    """Verify ConvAEScorer is unavailable without weights, and accepts dev smoke checkpoint."""
    # 1. No checkpoint -> unavailable
    scorer_empty = ConvAEScorer(checkpoint_path=tmp_path / "nonexistent.pth", allow_dev=False)
    assert scorer_empty.available is False
    assert "not found" in (scorer_empty.reason_unavailable or "").lower()

    # 2. Dev smoke checkpoint allowed
    smoke_file = tmp_path / "smoke_checkpoint.pth"
    # Create minimal state dict for ConvLSTMED
    from types import SimpleNamespace
    import torch
    from ConvAE import ConvLSTMED
    dummy_model = ConvLSTMED(SimpleNamespace(mode="gray"))
    torch.save(dummy_model.state_dict(), smoke_file)

    scorer_dev = ConvAEScorer(checkpoint_path=smoke_file, allow_dev=True)
    assert scorer_dev.available is True
    assert "DEV SMOKE TEST" in scorer_dev.trained_on

    # Test scoring with dev checkpoint
    synthetic_frames = [np.zeros((128, 128, 3), dtype=np.uint8) for _ in range(15)]
    res = scorer_dev.score(ClipInput(frames=synthetic_frames))
    assert isinstance(res, ScoreResult)
    assert 0.0 <= res.score <= 1.0


def test_onnx_classifier_scorer_unmounted_and_sidecar(tmp_path):
    """Verify OnnxClassifierScorer reports unavailable when file is missing, parses sidecar."""
    missing_scorer = OnnxClassifierScorer(model_path=tmp_path / "missing.onnx")
    assert missing_scorer.available is False
    assert "not mounted" in (missing_scorer.reason_unavailable or "").lower()


def test_ensemble_policies_all_scenarios():
    """
    Test CrashEnsemble under all policies ('any', 'all', 'majority', 'weighted')
    with zero, one, partial, and all scorers available.
    """
    dummy_clip = ClipInput(frames=[])

    # Case A: Zero scorers available
    s1_off = MockScorer(name="s1", available=False)
    s2_off = MockScorer(name="s2", available=False)
    ens_zero = CrashEnsemble(scorers=[s1_off, s2_off], policy="majority")
    scores, decision, degraded = ens_zero.evaluate(dummy_clip)
    assert decision is False
    assert degraded is True

    # Case B: Policy 'any'
    s_fired = MockScorer(name="s1", available=True, score_val=0.9, fired_val=True)
    s_nofire = MockScorer(name="s2", available=True, score_val=0.2, fired_val=False)
    ens_any = CrashEnsemble(scorers=[s_fired, s_nofire], policy="any")
    scores, decision, degraded = ens_any.evaluate(dummy_clip)
    assert decision is True
    assert degraded is False

    # Case C: Policy 'all'
    ens_all = CrashEnsemble(scorers=[s_fired, s_nofire], policy="all")
    scores, decision, degraded = ens_all.evaluate(dummy_clip)
    assert decision is False
    assert degraded is False

    # Case D: Policy 'majority' (2 out of 3 agree)
    s3_fired = MockScorer(name="s3", available=True, score_val=0.85, fired_val=True)
    ens_maj = CrashEnsemble(scorers=[s_fired, s_nofire, s3_fired], policy="majority")
    scores, decision, degraded = ens_maj.evaluate(dummy_clip)
    assert decision is True
    assert degraded is False

    # Case E: Policy 'weighted'
    # weights: s_fired=0.2, s_nofire=0.8. Total weighted score: (0.9*0.2 + 0.2*0.8) / 1.0 = 0.34 < 0.6
    ens_weighted = CrashEnsemble(
        scorers=[s_fired, s_nofire],
        policy="weighted",
        threshold=0.60,
        weights={"s1": 0.2, "s2": 0.8},
    )
    scores, decision, degraded = ens_weighted.evaluate(dummy_clip)
    assert decision is False
    assert degraded is False

    # Case F: Degraded mode (one scorer unavailable)
    ens_degraded = CrashEnsemble(scorers=[s_fired, s1_off], policy="any")
    scores, decision, degraded = ens_degraded.evaluate(dummy_clip)
    assert degraded is True
    assert decision is True  # s_fired is available and fired
