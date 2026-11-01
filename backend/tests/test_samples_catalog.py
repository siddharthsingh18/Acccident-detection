import io
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings, PROJECT_ROOT
from backend.app.services.feed_manager import feed_manager
from backend.app.services.sample_catalog import (
    resolve_expected_label,
    resolve_sample_path,
    get_video_metadata,
    make_stable_id
)

@pytest.fixture(autouse=True)
def cleanup_feed_manager():
    """Ensure feed manager is reset before and after each test."""
    feed_manager.reset()
    yield
    feed_manager.reset()

def test_get_samples_listing():
    """Verify GET /api/samples returns all discoverable videos with proper metadata."""
    client = TestClient(app)
    res = client.get("/api/samples")
    assert res.status_code == 200
    samples = res.json()
    assert isinstance(samples, list)
    assert len(samples) > 0

    # Verify schema fields on every item
    by_name = {}
    for s in samples:
        assert "id" in s
        assert "name" in s
        assert "relative_path" in s
        assert "size_bytes" in s
        assert "thumbnail_url" in s
        assert "expected_label" in s
        assert s["expected_label"] in ("accident", "normal", "unknown")
        assert s["size_bytes"] > 0
        by_name[s["name"]] = s

    # Verify verified entries from manifest
    assert "1528.mp4" in by_name
    s1528 = by_name["1528.mp4"]
    assert s1528["expected_label"] == "accident"
    assert s1528["duration_s"] is not None and s1528["duration_s"] > 0
    assert s1528["resolution"] is not None

    assert "1600.mp4" in by_name
    s1600 = by_name["1600.mp4"]
    assert s1600["expected_label"] == "normal"

    # Verify stable ID is reversible and URL-safe
    assert "--" in s1528["id"] or not "/" in s1528["id"]

def test_sample_thumbnail_endpoint():
    """Verify GET /api/samples/{id}/thumbnail returns valid JPEG image."""
    client = TestClient(app)
    # Find sample 1528
    list_res = client.get("/api/samples")
    samples = list_res.json()
    s1528 = next(s for s in samples if s["name"] == "1528.mp4")

    thumb_res = client.get(f"/api/samples/{s1528['id']}/thumbnail")
    assert thumb_res.status_code == 200
    assert thumb_res.headers["content-type"] == "image/jpeg"
    assert len(thumb_res.content) > 0

    # Also verify video stream endpoint
    video_res = client.get(f"/api/samples/{s1528['id']}/video")
    assert video_res.status_code == 200
    assert "video" in video_res.headers["content-type"]
    assert video_res.headers.get("accept-ranges") == "bytes"

def test_corrupt_file_skipped_without_crashing(tmp_path, monkeypatch):
    """Corrupt or non-video files must return None metadata with warning, never 500 error."""
    corrupt_file = tmp_path / "corrupt.mp4"
    corrupt_file.write_bytes(b"NOT A REAL VIDEO HEADER JUST GARBAGE BYTES")

    meta = get_video_metadata(corrupt_file, "corrupt.mp4")
    assert meta["duration_s"] is None
    assert meta["resolution"] is None
    assert meta["fps"] is None

def test_path_traversal_attempts_rejected():
    """Path traversal attacks using .., absolute paths, or escaping slashes must be blocked."""
    client = TestClient(app)

    # 1. In thumbnail endpoint
    bad_ids = [
        "..%2F..%2Fetc%2Fpasswd",
        "../../etc/passwd",
        "/etc/passwd",
        "videos/../../System/Database/Argus_DB.db",
        "videos--..__..__etc--passwd",
    ]
    for bad_id in bad_ids:
        res = client.get(f"/api/samples/{bad_id}/thumbnail")
        assert res.status_code in (400, 404)

    # 2. In from-sample feed endpoint
    for bad_id in bad_ids:
        res = client.post("/api/feeds/from-sample", json={"sample_id": bad_id})
        assert res.status_code in (400, 404)
        msg = res.json().get("message", "") or res.json().get("detail", "")
        if res.status_code == 400:
            assert "path traversal is forbidden" in msg.lower()

def test_unknown_sample_id_returns_404():
    """Non-existent sample IDs must return 404."""
    client = TestClient(app)
    res = client.get("/api/samples/completely_unknown_sample_12345.mp4/thumbnail")
    assert res.status_code == 404

    res_post = client.post("/api/feeds/from-sample", json={"sample_id": "completely_unknown_sample_12345.mp4"})
    assert res_post.status_code == 404

def test_post_feed_from_sample_success_and_busy_409():
    """POST /api/feeds/from-sample starts feed and returns 409 when a feed is actively running."""
    client = TestClient(app)

    # 1. Start sample feed
    res = client.post(
        "/api/feeds/from-sample",
        json={
            "sample_id": "videos--1528.mp4",
            "camera_id": 1528,
            "city": "Shibin El Kom",
            "district": "District 13"
        }
    )
    assert res.status_code == 201
    feed = res.json()
    assert feed["camera_id"] == 1528
    assert feed["city"] == "Shibin El Kom"
    assert feed["status"] in ("queued", "processing", "done")

    # 2. Attempting to start another feed immediately while one is active returns 409
    res_busy = client.post(
        "/api/feeds/from-sample",
        json={
            "sample_id": "videos--1600.mp4",
            "camera_id": 1600
        }
    )
    # If active, 409 Conflict
    if feed_manager.active_feed_id:
        assert res_busy.status_code == 409
        msg = res_busy.json().get("message", "") or res_busy.json().get("detail", "")
        assert "currently running" in msg.lower()

def test_label_resolution_order(tmp_path):
    """
    Verify label resolution priority:
    1. Manifest entry takes highest precedence.
    2. Directory dataset/Accidents -> accident.
    3. Directory dataset/No_Accidents -> normal.
    4. Otherwise unknown (no guessing by filename).
    """
    manifest = {
        "custom_clip.mp4": {"label": "accident", "notes": "Manifest override accident"},
        "special_normal.avi": {"label": "normal", "notes": "Manifest override normal"}
    }

    # 1. Manifest match
    p1 = tmp_path / "custom_clip.mp4"
    lbl, notes = resolve_expected_label(p1, "videos/custom_clip.mp4", manifest)
    assert lbl == "accident"
    assert notes == "Manifest override accident"

    # 2. Inferred from dataset/Accidents
    p2 = Path(PROJECT_ROOT / "dataset" / "Accidents" / "subvideos" / "1.avi")
    lbl, notes = resolve_expected_label(p2, "dataset/Accidents/subvideos/1.avi", manifest)
    assert lbl == "accident"
    assert "Accidents" in (notes or "")

    # 3. Inferred from dataset/No_Accidents
    p3 = Path(PROJECT_ROOT / "dataset" / "No_Accidents" / "subvideos" / "1.avi")
    lbl, notes = resolve_expected_label(p3, "dataset/No_Accidents/subvideos/1.avi", manifest)
    assert lbl == "normal"
    assert "No_Accidents" in (notes or "")

    # 4. Unknown clip without manifest (never guess by filename!)
    p4 = Path(PROJECT_ROOT / "videos" / "crash_accident_terrible.mp4")
    lbl, notes = resolve_expected_label(p4, "videos/crash_accident_terrible.mp4", manifest)
    assert lbl == "unknown"
    assert notes is None
