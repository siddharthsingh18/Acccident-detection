import json
import sqlite3
import pytest
from app.models.schemas import ModelScores, ScorerResult, Incident, Alert, FeedResponse


def test_get_models_status(client):
    """Verify GET /api/models/status returns valid schema and active scorers."""
    response = client.get("/api/models/status")
    assert response.status_code == 200
    data = response.json()

    assert "policy" in data
    assert data["policy"] in ("any", "all", "majority", "weighted")
    assert "degraded" in data
    assert isinstance(data["degraded"], bool)
    assert "scorers" in data
    assert len(data["scorers"]) >= 2

    scorer_names = {s["name"] for s in data["scorers"]}
    assert "vif_svm" in scorer_names
    assert "convae" in scorer_names

    for s in data["scorers"]:
        assert "available" in s
        assert "version" in s
        assert "trained_on" in s

    # When no trained weights are present in artifacts/, convae must report available=False
    convae_scorer = next(s for s in data["scorers"] if s["name"] == "convae")
    assert convae_scorer["available"] is False
    assert "checkpoint not found" in (convae_scorer["reason_unavailable"] or "").lower()
    assert data["degraded"] is True


def test_models_status_honors_crash_policy_env(client, monkeypatch):
    """Verify that CRASH_POLICY env var takes precedence and configures ensemble policy."""
    monkeypatch.setenv("CRASH_POLICY", "all")
    response = client.get("/api/models/status")
    assert response.status_code == 200
    assert response.json()["policy"] == "all"


def test_models_status_with_dev_checkpoint(client, monkeypatch, tmp_path):
    """Verify that ARGUS_ALLOW_DEV_CHECKPOINT=true allows a smoke checkpoint tagged DEV."""
    ckpt_dir = tmp_path / "artifacts" / "checkpoints" / "convae"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    smoke_dest = ckpt_dir / "smoke_checkpoint.pth"
    smoke_dest.write_text("dummy checkpoint")

    monkeypatch.setenv("CONVAE_CHECKPOINT_DIR", str(ckpt_dir))
    monkeypatch.setenv("ARGUS_ALLOW_DEV_CHECKPOINT", "true")
    response = client.get("/api/models/status")
    assert response.status_code == 200
    convae = next(s for s in response.json()["scorers"] if s["name"] == "convae")
    assert convae["available"] is True
    assert "DEV SMOKE TEST" in convae["trained_on"]


def test_incident_with_null_model_scores(client):
    """Verify incidents without model_scores default to null gracefully."""
    response = client.get("/api/incidents?limit=5")
    assert response.status_code == 200
    items = response.json()["items"]
    if items:
        # Legacy items should have model_scores as None
        for item in items:
            assert "model_scores" in item
            # Can be None or ModelScores
            if item["model_scores"] is not None:
                assert "policy" in item["model_scores"]
                assert "decision" in item["model_scores"]


def test_incident_with_populated_model_scores(client):
    """Verify incidents with model_scores JSON in DB are parsed and returned correctly."""
    from app.config import settings

    scores_dict = {
        "policy": "majority",
        "threshold": 0.60,
        "decision": True,
        "scorers": [
            {
                "name": "vif_svm",
                "score": 0.88,
                "fired": True,
                "calibrated": True,
                "available": True,
                "latency_ms": 14.2,
            },
            {
                "name": "convae",
                "score": 0.75,
                "fired": True,
                "calibrated": False,
                "available": True,
                "latency_ms": 31.0,
            },
            {
                "name": "resnet_onnx",
                "score": 0.42,
                "fired": False,
                "calibrated": False,
                "available": False,
                "latency_ms": None,
            },
        ],
    }

    conn = sqlite3.connect(settings.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO CrashFrames (
            camera_id, frame_id, from_no, city, district, crash_time, model_scores
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        7777,
        123,
        5,
        "Test City",
        "Test District",
        "2026-11-01 12:00:00",
        json.dumps(scores_dict),
    ))
    conn.commit()
    conn.close()

    res = client.get("/api/incidents/7777_123")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "7777_123"
    assert data["model_scores"] is not None
    assert data["model_scores"]["policy"] == "majority"
    assert data["model_scores"]["threshold"] == 0.60
    assert data["model_scores"]["decision"] is True
    assert len(data["model_scores"]["scorers"]) == 3
    assert data["model_scores"]["scorers"][0]["name"] == "vif_svm"
    assert data["model_scores"]["scorers"][0]["score"] == 0.88


def test_feed_response_degraded_and_active_scorers():
    """Verify FeedResponse schema includes degraded flag and active_scorers."""
    feed = FeedResponse(
        id="test-feed-id",
        camera_id=1506,
        city="Asyut",
        district="District 16",
        status="processing",
        detection_mode="legacy",
        degraded=False,
        active_scorers=["vif_svm"],
        progress={"frames_sent": 10, "total_frames": 100, "percent": 10.0},
        thumbnail_url="/api/feeds/test/thumbnail",
        created_at="2026-11-01T00:00:00Z",
    )
    assert feed.degraded is False
    assert feed.active_scorers == ["vif_svm"]


def test_csv_export_includes_model_scores(client):
    """Verify CSV export includes per-scorer score columns."""
    res = client.get("/api/incidents/export")
    assert res.status_code == 200
    assert "Ensemble Policy" in res.text
    assert "VIF_SVM Score" in res.text
    assert "ConvAE Score" in res.text
    assert "ResNet_ONNX Score" in res.text

