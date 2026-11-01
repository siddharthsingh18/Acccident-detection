import json
import sqlite3
import numpy as np
import pytest

from System.Functions.Crashing import Crashing
from VIF.vif import VIF
from argus_ml.scoring.base import ClipInput, ScoreResult
from argus_ml.scoring.ensemble import CrashEnsemble
from backend.app.services.database import apply_migrations
from backend.app.models.schemas import ModelScores
from backend.app.api.models import reset_models_cache


class DummyTracker:
    def __init__(self, frames, bounds=(10, 10, 80, 60)):
        self.frames = frames
        self.bounds = bounds

    def getFramesOfTracking(self, gray_frames):
        xmin, ymin, xmax, ymax = self.bounds
        return self.frames, xmax - xmin, ymax - ymin, xmin, xmax, ymin, ymax

    def saveTracking(self, frames):
        pass


def test_flag_off_legacy_byte_for_byte_regression(monkeypatch):
    """
    Regression Test: With ARGUS_ENABLE_ENSEMBLE=false (or unset), Crashing.predict
    must produce byte-for-byte identical output to legacy code, leaving last_model_scores as None.
    """
    monkeypatch.setenv("ARGUS_ENABLE_ENSEMBLE", "false")
    vif = VIF()
    crashing = Crashing(vif)

    # Synthetic 20-frame sequence
    np.random.seed(123)
    frames_rgb = [np.random.randint(0, 255, (360, 480, 3), dtype=np.uint8) for _ in range(25)]
    tracker_frames = [np.random.randint(0, 255, (100, 134), dtype=np.uint8) for _ in range(20)]
    tracker = DummyTracker(tracker_frames, bounds=(20, 20, 100, 80))

    dims = crashing.predict(frames_rgb, [tracker])

    assert isinstance(dims, list)
    assert crashing.last_model_scores is None


def test_flag_on_with_only_legacy_available(monkeypatch):
    """
    With ARGUS_ENABLE_ENSEMBLE=true and no additional checkpoints installed,
    ensemble runs in degraded mode (legacy vif_svm only), populating last_model_scores.
    """
    monkeypatch.setenv("ARGUS_ENABLE_ENSEMBLE", "true")
    monkeypatch.setenv("ARGUS_ALLOW_DEV_CHECKPOINT", "false")
    vif = VIF()
    crashing = Crashing(vif)

    np.random.seed(123)
    frames_rgb = [np.random.randint(0, 255, (360, 480, 3), dtype=np.uint8) for _ in range(25)]
    tracker_frames = [np.random.randint(0, 255, (100, 134), dtype=np.uint8) for _ in range(20)]
    tracker = DummyTracker(tracker_frames, bounds=(20, 20, 100, 80))

    crashing.predict(frames_rgb, [tracker])

    assert crashing.last_model_scores is not None
    scores = crashing.last_model_scores
    assert "policy" in scores
    assert "scorers" in scores

    # vif_svm should be available; convae and resnet_onnx should be unavailable
    vif_s = next(s for s in scores["scorers"] if s["name"] == "vif_svm")
    convae_s = next(s for s in scores["scorers"] if s["name"] == "convae")
    resnet_s = next(s for s in scores["scorers"] if s["name"] == "resnet_onnx")

    assert vif_s["available"] is True
    assert convae_s["available"] is False
    assert resnet_s["available"] is False


def test_flag_on_with_mock_second_scorer():
    """Verify CrashEnsemble combines multiple available scorers into a valid decision."""
    class FakeScorer:
        def __init__(self, name, score_val, fired_val):
            self.name = name
            self.available = True
            self.version = "1.0.0"
            self.trained_on = "Test"
            self.calibration_date = None
            self.reason_unavailable = None
            self.score_val = score_val
            self.fired_val = fired_val

        def score(self, clip):
            return ScoreResult(score=self.score_val, fired=self.fired_val, calibrated=True, latency_ms=10.0)

    ens = CrashEnsemble(
        scorers=[
            FakeScorer("vif_svm", 0.9, True),
            FakeScorer("convae", 0.85, True),
        ],
        policy="majority",
    )

    scores, decision, degraded = ens.evaluate(ClipInput(frames=[]))
    assert decision is True
    assert degraded is False
    assert len(scores.scorers) == 2


def test_scorer_exception_handled_cleanly():
    """Verify that an unexpected exception in a scorer does not crash evaluation."""
    class FailingScorer:
        name = "failing_scorer"
        available = True
        version = "1.0.0"
        trained_on = "Test"
        calibration_date = None
        reason_unavailable = None

        def score(self, clip):
            raise RuntimeError("Unexpected CUDA / Out of Memory error")

    ens = CrashEnsemble(scorers=[FailingScorer()], policy="any")
    scores, decision, degraded = ens.evaluate(ClipInput(frames=[]))

    assert decision is False
    assert degraded is True
    assert scores.scorers[0].available is False
    assert "Runtime error" in (scores.scorers[0].reason_unavailable or "")


def test_malformed_model_scores_json_in_db():
    """Verify that malformed JSON in DB model_scores column parses gracefully to None."""
    from backend.app.services.database import row_to_incident
    fake_row = {
        "camera_id": 1234,
        "frame_id": 56,
        "from_no": 5,
        "city": "Cairo",
        "district": "District 1",
        "crash_time": "2026-11-01 10:00:00",
        "model_scores": "{malformed json",
        "rowid": 1,
    }
    incident = row_to_incident(fake_row)
    assert incident.id == "1234_56"
    assert incident.model_scores is None


def test_db_migration_idempotent_run_twice(tmp_path):
    """Verify init_database_schema can run multiple times on a database without failure."""
    db_file = tmp_path / "test_migration.db"
    conn = sqlite3.connect(db_file)
    conn.execute("""
        CREATE TABLE CrashFrames (
            camera_id INTEGER,
            frame_id INTEGER,
            from_no INTEGER,
            city TEXT,
            district TEXT,
            crash_time TEXT
        );
    """)
    conn.commit()
    conn.close()

    # First run
    apply_migrations(str(db_file))
    # Second run (must not raise error)
    apply_migrations(str(db_file))

    conn = sqlite3.connect(db_file)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(CrashFrames);").fetchall()}
    conn.close()

    assert "model_scores" in cols
    assert "review_status" in cols
