import cv2
import json
import numpy as np
import pytest
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings, PROJECT_ROOT
from backend.app.services.feed_manager import feed_manager
from boxes.registry import lookup_box_file, compute_video_hash, load_box_registry
from System.Functions.Detector.legacy import LegacyBoxFilesDetector


@pytest.fixture(autouse=True)
def reset_feed_state():
    feed_manager.reset()
    yield
    feed_manager.reset()


@pytest.fixture
def client():
    return TestClient(app)


def create_dummy_video(dest_path: Path, num_frames: int = 5, color: int = 0):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(dest_path), fourcc, 25.0, (64, 64))
    for _ in range(num_frames):
        frame = np.full((64, 64, 3), color, dtype=np.uint8)
        out.write(frame)
    out.release()


def test_box_registry_lookup_by_content_hash():
    """Verify that known bundled clips resolve strictly via their content hash."""
    clip_1528 = PROJECT_ROOT / "videos" / "1528.mp4"
    assert clip_1528.is_file(), "videos/1528.mp4 must exist in repo"

    box_file = lookup_box_file(clip_1528)
    assert box_file is not None
    assert box_file.name == "1528.txt"
    assert box_file.is_file()


def test_unrelated_video_with_camera_id_1528_does_not_load_boxes_1528(tmp_path):
    """
    CRITICAL REQUIREMENT:
    Uploading or processing an unrelated video with camera_id=1528 must NOT load boxes/1528.txt.
    """
    dummy_vid = tmp_path / "unrelated_surveillance.mp4"
    create_dummy_video(dummy_vid, num_frames=10, color=120)

    # 1. Content-addressed registry lookup must return None
    matched_box = lookup_box_file(dummy_vid)
    assert matched_box is None, "Unrelated video hash must not match boxes/1528.txt"

    # 2. Legacy detector must not load 1528.txt even if camera_id=1528 is supplied
    detector = LegacyBoxFilesDetector()
    dummy_frame = np.full((360, 480, 3), 120, dtype=np.uint8)

    # Passing camera_id=1528 and the unrelated video path
    boxes = detector.detect(
        dummy_frame,
        video_path=dummy_vid,
        camera_id=1528,
        frame_index=0
    )

    # boxes/1528.txt frame 0 contains 5 tracked bounding boxes for vehicles.
    # An unrelated video with no registered box file must not receive those boxes.
    assert len(boxes) == 0, f"Expected 0 boxes from unrelated video, got {len(boxes)}"


def test_upload_storage_structure_and_persistence(client, tmp_path):
    """
    Verify uploaded files are preserved in backend/uploads/<run_id>/original.<ext>
    with metadata.json, and identical filenames do not collide.
    """
    dummy_vid_1 = tmp_path / "dashcam.mp4"
    dummy_vid_2 = tmp_path / "dashcam_copy.mp4"
    create_dummy_video(dummy_vid_1, num_frames=5, color=50)
    create_dummy_video(dummy_vid_2, num_frames=5, color=150)

    # Upload video 1 with filename "dashcam.mp4"
    with open(dummy_vid_1, "rb") as f:
        res1 = client.post(
            "/api/feeds",
            files={"file": ("dashcam.mp4", f, "video/mp4")},
            data={"camera_id": 10, "city": "Cairo", "district": "District 1"}
        )
    assert res1.status_code == 201
    feed1 = res1.json()
    feed1_id = feed1["id"]

    # Verify structured folder backend/uploads/<run_id>/original.mp4
    upload1_dir = settings.UPLOADS_DIR / feed1_id
    assert upload1_dir.is_dir(), f"Upload dir {upload1_dir} must exist"
    original_1 = upload1_dir / "original.mp4"
    assert original_1.is_file(), f"Original file {original_1} must exist"

    # Verify metadata.json
    meta_file_1 = upload1_dir / "metadata.json"
    assert meta_file_1.is_file()
    with open(meta_file_1, "r", encoding="utf-8") as mf:
        meta_data = json.load(mf)
        assert meta_data["run_id"] == feed1_id
        assert meta_data["original_filename"] == "dashcam.mp4"
        assert meta_data["camera_id"] == 10

    # Upload video 2 with same filename "dashcam.mp4" to test collision isolation
    with open(dummy_vid_2, "rb") as f:
        res2 = client.post(
            "/api/feeds",
            files={"file": ("dashcam.mp4", f, "video/mp4")},
            data={"camera_id": 20, "city": "Alexandria", "district": "District 2"}
        )
    assert res2.status_code in (201, 409)  # 409 if feed 1 still active, 201 if completed
    if res2.status_code == 201:
        feed2 = res2.json()
        feed2_id = feed2["id"]
        assert feed2_id != feed1_id
        upload2_dir = settings.UPLOADS_DIR / feed2_id
        assert upload2_dir.is_dir()
        assert (upload2_dir / "original.mp4").is_file()

    # Verify video 1 is still on disk (not immediately deleted on completion)
    assert original_1.is_file(), "Uploaded video must persist after feed processing for replay"


def test_feed_rerun_endpoint_without_reuploading(client, tmp_path):
    """
    Verify POST /api/feeds/{id}/rerun replays an existing uploaded video without re-uploading bytes.
    """
    dummy_vid = tmp_path / "replay_test.mp4"
    create_dummy_video(dummy_vid, num_frames=5, color=90)

    # First upload
    with open(dummy_vid, "rb") as f:
        res = client.post(
            "/api/feeds",
            files={"file": ("replay_test.mp4", f, "video/mp4")},
            data={"camera_id": 55, "city": "Giza", "district": "Pyramids"}
        )
    assert res.status_code == 201
    feed = res.json()
    feed_id = feed["id"]

    # Wait or cancel feed so slot is available for re-run
    client.post(f"/api/feeds/{feed_id}/cancel")
    feed_manager.active_feed_id = None

    # Re-run the feed without uploading bytes
    rerun_res = client.post(
        f"/api/feeds/{feed_id}/rerun",
        json={"camera_id": 55, "city": "Giza", "district": "Pyramids", "is_test": True}
    )
    assert rerun_res.status_code == 201
    rerun_data = rerun_res.json()
    assert rerun_data["camera_id"] == 55
    assert rerun_data["city"] == "Giza"
    assert rerun_data["status"] in ("queued", "processing", "done")


def test_upload_retention_cleanup(tmp_path):
    """
    Verify upload retention cleanup:
    - Recent upload directories are kept.
    - Upload directories older than retention_days are pruned.
    """
    # Create mock old upload directory in settings.UPLOADS_DIR
    old_run_id = "test_old_run_9999"
    old_dir = settings.UPLOADS_DIR / old_run_id
    old_dir.mkdir(parents=True, exist_ok=True)
    old_file = old_dir / "original.mp4"
    create_dummy_video(old_file, num_frames=2)

    # Set mtime to 10 days ago
    ten_days_ago = time.time() - (10 * 86400)
    import os
    os.utime(old_dir, (ten_days_ago, ten_days_ago))
    os.utime(old_file, (ten_days_ago, ten_days_ago))

    # Run cleanup with retention_days=7
    stats = feed_manager.cleanup_uploads(retention_days=7)
    assert stats["cleaned_count"] >= 1
    assert not old_dir.exists(), f"Old upload dir {old_dir} should have been pruned by retention policy"


def test_bundled_clips_regression_against_baseline():
    """
    Verify regression baseline: all sample clips with box files match their registered box files.
    """
    registry = load_box_registry()
    entries = registry.get("entries", {})
    assert len(entries) > 0, "Box registry must have entries"

    # Clip 1528
    hash_1528 = compute_video_hash(PROJECT_ROOT / "videos" / "1528.mp4")
    assert hash_1528 in entries
    assert entries[hash_1528]["box_stem"] == "1528"
