import pytest
import sqlite3
import numpy as np
import cv2
from pathlib import Path
from app.services.database import get_write_connection, query_incidents, query_recent_incidents, tag_incident_test
from app.services.feed_manager import feed_manager, FeedItem

def test_incident_test_tagging_and_filtering(client):
    """Verify test-run incidents are tagged test=1 and hidden by default unless include_test=True."""
    # Insert a temporary test incident
    with get_write_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO CrashFrames (camera_id, frame_id, from_no, city, district, crash_time, feed_id, test)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (9991, 100, 5, "TestCity", "TestDistrict", "2026-11-01 12:00:00", "feed-test-123", 1)
        )
        conn.commit()

    try:
        # Default query hides test incidents
        items, _, _ = query_incidents(camera_id=9991, include_test=False)
        assert len(items) == 0

        # With include_test=True, the incident is returned
        items_all, _, _ = query_incidents(camera_id=9991, include_test=True)
        assert len(items_all) == 1
        assert items_all[0].camera_id == 9991
        assert items_all[0].feed_id == "feed-test-123"
        assert items_all[0].test == 1

        # Query via HTTP API default
        res_default = client.get("/api/incidents?camera_id=9991")
        assert res_default.status_code == 200
        assert res_default.json()["count"] == 0

        # Query via HTTP API with include_test=true
        res_include = client.get("/api/incidents?camera_id=9991&include_test=true")
        assert res_include.status_code == 200
        assert res_include.json()["count"] == 1
        assert res_include.json()["items"][0]["camera_id"] == 9991

        # Query via HTTP API with feed_id filter
        res_feed = client.get("/api/incidents?feed_id=feed-test-123&include_test=true")
        assert res_feed.status_code == 200
        assert res_feed.json()["count"] == 1

        # CSV export with include_test
        res_csv_default = client.get("/api/incidents/export?camera_id=9991")
        assert res_csv_default.status_code == 200
        assert "TestCity" not in res_csv_default.text

        res_csv_test = client.get("/api/incidents/export?camera_id=9991&include_test=true")
        assert res_csv_test.status_code == 200
        assert "TestCity" in res_csv_test.text

    finally:
        # Clean up inserted test row
        with get_write_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM CrashFrames WHERE camera_id = 9991")
            conn.commit()


def test_feed_manager_record_incident_and_response():
    """Verify FeedItem response exposes detected_incidents and anomalies_detected."""
    feed_item = FeedItem(
        feed_id="test-feed-xyz",
        camera_id=1528,
        city="Cairo",
        district="District 1",
        video_path=Path("/tmp/fake.mp4"),
        thumbnail_path=None,
        is_test=True
    )
    feed_manager.feeds["test-feed-xyz"] = feed_item

    try:
        assert feed_item.detected_incidents == []
        assert feed_item.anomalies_detected == 0

        feed_manager.record_incident("test-feed-xyz", "1528_76")
        assert feed_item.detected_incidents == ["1528_76"]
        assert feed_item.anomalies_detected == 1

        # Duplicate recording is idempotent
        feed_manager.record_incident("test-feed-xyz", "1528_76")
        assert feed_item.detected_incidents == ["1528_76"]
        assert feed_item.anomalies_detected == 1

        # Response serialization includes fields
        resp = feed_item.to_response()
        assert resp.detected_incidents == ["1528_76"]
        assert resp.anomalies_detected == 1

    finally:
        feed_manager.feeds.pop("test-feed-xyz", None)


def test_camera_worker_short_clip_padding(tmp_path, capsys):
    """Verify camera_worker pads videos with fewer than 30 frames to 30 frames and executes cleanly."""
    from app.services.camera_worker import run_headless_camera

    # Create a 10-frame test video
    short_vid = tmp_path / "short_clip.avi"
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(str(short_vid), fourcc, 30.0, (480, 360))
    for i in range(10):
        frame = np.full((360, 480, 3), i * 20, dtype=np.uint8)
        out.write(frame)
    out.release()

    # Run camera worker on port where no master is listening (send will gracefully time out/skip)
    run_headless_camera(
        video_path=str(short_vid),
        camera_id=9999,
        city="Cairo",
        district="District 1",
        master_ip="127.0.0.1",
        master_port=10099,
        feed_id="feed-short-clip",
        is_test=True,
    )

    captured = capsys.readouterr().out
    assert "STATUS:DONE" in captured
    assert "PROGRESS:10:10" in captured

