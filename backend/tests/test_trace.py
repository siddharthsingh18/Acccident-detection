import os
from pathlib import Path
import pytest
from argus_ml.trace import (
    is_trace_enabled,
    get_trace_dir,
    sanitize_run_id,
    record_batch_trace,
    read_run_trace,
    summarize_run_trace,
)


def test_is_trace_enabled_flag(monkeypatch):
    monkeypatch.delenv("ARGUS_TRACE", raising=False)
    assert not is_trace_enabled()

    monkeypatch.setenv("ARGUS_TRACE", "true")
    assert is_trace_enabled()

    monkeypatch.setenv("ARGUS_TRACE", "1")
    assert is_trace_enabled()

    monkeypatch.setenv("ARGUS_TRACE", "false")
    assert not is_trace_enabled()


def test_sanitize_run_id():
    assert sanitize_run_id("test_clip") == "test_clip"
    assert sanitize_run_id("../../etc/passwd") == "passwd"
    assert sanitize_run_id("dir/nested/file") == "file"
    assert sanitize_run_id("") == "default"


def test_record_and_read_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("ARGUS_TRACE", "true")
    monkeypatch.setenv("ARGUS_TRACE_DIR", str(tmp_path))

    record_1 = {
        "run_id": "clip_abc",
        "batch_index": 1,
        "starting_frame_id": 1,
        "num_detections": 3,
        "num_trackers": 3,
        "pairs_evaluated": 3,
        "failed_speed": 1,
        "failed_distance": 2,
        "failed_deviation": 0,
        "candidates_passed_geometry": 0,
        "failed_box_size": 0,
        "failed_aspect_ratio": 0,
        "classifier_score": 0.42,
        "decision": False,
        "primary_reason": "TOO_FAR",
    }
    record_2 = {
        "run_id": "clip_abc",
        "batch_index": 2,
        "starting_frame_id": 16,
        "num_detections": 3,
        "num_trackers": 3,
        "pairs_evaluated": 3,
        "failed_speed": 0,
        "failed_distance": 0,
        "failed_deviation": 0,
        "candidates_passed_geometry": 1,
        "failed_box_size": 0,
        "failed_aspect_ratio": 0,
        "classifier_score": 0.88,
        "decision": True,
        "primary_reason": "CRASH_DETECTED",
    }

    record_batch_trace("clip_abc", record_1)
    record_batch_trace("clip_abc", record_2)

    records = read_run_trace("clip_abc")
    assert len(records) == 2
    assert records[0]["run_id"] == "clip_abc"
    assert records[0]["classifier_score"] == 0.42
    assert records[1]["decision"] is True


def test_summarize_run_trace():
    records = [
        {
            "run_id": "test_clip",
            "batch_index": 1,
            "num_trackers": 4,
            "pairs_evaluated": 6,
            "failed_speed": 2,
            "failed_distance": 4,
            "failed_deviation": 0,
            "failed_box_size": 0,
            "failed_aspect_ratio": 0,
            "classifier_score": 0.35,
            "decision": False,
        },
        {
            "run_id": "test_clip",
            "batch_index": 2,
            "num_trackers": 5,
            "pairs_evaluated": 10,
            "failed_speed": 3,
            "failed_distance": 7,
            "failed_deviation": 0,
            "failed_box_size": 0,
            "failed_aspect_ratio": 0,
            "classifier_score": 0.49,
            "decision": False,
        },
    ]

    summary = summarize_run_trace(records)
    assert summary["total_batches"] == 2
    assert summary["max_trackers"] == 5
    assert summary["total_pairs_evaluated"] == 16
    assert summary["dominant_filter"] == "TOO_FAR"
    assert summary["max_classifier_score"] == 0.49
    assert summary["alert_count"] == 0
    assert summary["primary_cause"] == "CLASSIFIER_LOW_SCORE"


def test_summarize_run_trace_low_quality_detection():
    """Verify summarize_run_trace returns LOW_QUALITY_DETECTION when detection is degraded."""
    degraded_records = [
        {
            "run_id": "upload_degraded",
            "batch_index": 1,
            "num_trackers": 0,
            "pairs_evaluated": 0,
            "detection_quality": "motion_fallback",
            "decision": False,
        }
    ]
    summary = summarize_run_trace(degraded_records, detection_quality="motion_fallback")
    assert summary["primary_cause"] == "LOW_QUALITY_DETECTION"
    assert summary["detection_quality"] == "motion_fallback"

    # Also test empty records with motion_fallback
    summary_empty = summarize_run_trace([], detection_quality="motion_fallback")
    assert summary_empty["primary_cause"] == "LOW_QUALITY_DETECTION"


def test_summarize_run_trace_filtered_box_size():
    """Verify summarize_run_trace assigns FILTERED_BOX_SIZE when bounding boxes are rejected."""
    box_records = [
        {
            "run_id": "test_box",
            "batch_index": 1,
            "num_trackers": 2,
            "pairs_evaluated": 1,
            "failed_box_size": 2,
            "decision": False,
        }
    ]
    summary = summarize_run_trace(box_records)
    assert summary["primary_cause"] == "FILTERED_BOX_SIZE"


def test_get_run_trace_endpoint_fallback_and_attributes(client, tmp_path):
    """Verify GET /api/feeds/trace/{run_id} does not crash when feed has no trace file,
    correctly reading progress.frames_sent and returning summary without AttributeError."""
    from app.services.feed_manager import feed_manager, FeedItem

    # 1. Non-existent feed and no trace file
    resp = client.get("/api/feeds/trace/nonexistent_feed_123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_trace"] is False
    assert data["summary"] is None

    # 2. Feed exists in feed_manager with progress, but no trace records
    feed_id = "test_feed_no_trace"
    feed_item = FeedItem(
        feed_id=feed_id,
        camera_id=101,
        city="Cairo",
        district="District 1",
        video_path=tmp_path / "dummy.mp4",
        thumbnail_path=tmp_path / "dummy.jpg",
    )
    feed_item.status = "done"
    feed_item.total_frames = 90
    feed_item.frames_sent = 90
    feed_item.detection_quality = "neural"
    feed_item.detector_name = "SSDLite320"
    feed_item.vehicles_detected_count = 3
    feed_manager.feeds[feed_id] = feed_item

    try:
        resp = client.get(f"/api/feeds/trace/{feed_id}")
        assert resp.status_code == 200
        trace_data = resp.json()
        assert trace_data["has_trace"] is True
        summary = trace_data["summary"]
        assert summary is not None
        assert summary["total_batches"] == 3
        assert summary["batches_processed"] == 3
        assert summary["max_trackers"] == 3
        assert summary["detector_used"] == "SSDLite320"
        assert summary["detection_quality"] == "neural"
        assert summary["primary_cause"] == "NO_TRACE"

        # 3. Feed exists with degraded detection quality
        feed_id_deg = "test_feed_degraded"
        feed_item_deg = FeedItem(
            feed_id=feed_id_deg,
            camera_id=102,
            city="Cairo",
            district="District 2",
            video_path=tmp_path / "dummy_deg.mp4",
            thumbnail_path=tmp_path / "dummy_deg.jpg",
        )
        feed_item_deg.status = "done"
        feed_item_deg.total_frames = 30
        feed_item_deg.frames_sent = 30
        feed_item_deg.detection_quality = "motion_fallback"
        feed_item_deg.detector_name = "motion"
        feed_item_deg.vehicles_detected_count = 1
        feed_manager.feeds[feed_id_deg] = feed_item_deg

        resp_deg = client.get(f"/api/feeds/trace/{feed_id_deg}")
        assert resp_deg.status_code == 200
        summary_deg = resp_deg.json()["summary"]
        assert summary_deg["primary_cause"] == "LOW_QUALITY_DETECTION"
        assert summary_deg["detection_quality"] == "motion_fallback"

    finally:
        feed_manager.feeds.pop(feed_id, None)
        feed_manager.feeds.pop("test_feed_degraded", None)


