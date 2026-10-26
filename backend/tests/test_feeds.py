import os
import time
from pathlib import Path
import cv2
import numpy as np
import pytest

@pytest.fixture(autouse=True)
def reset_feeds():
    from app.services.feed_manager import feed_manager
    feed_manager.reset()
    yield
    feed_manager.reset()

def generate_test_mp4(filepath: Path, num_frames=35, fps=25):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(filepath), fourcc, fps, (480, 360))
    for i in range(num_frames):
        frame = np.zeros((360, 480, 3), dtype=np.uint8)
        cv2.circle(frame, (50 + i * 5, 180), 30, (0, 255, 0), -1)
        writer.write(frame)
    writer.release()
    return filepath

def test_feed_upload_and_processing(client, tmp_path):
    video_path = generate_test_mp4(tmp_path / "test_camera.mp4", num_frames=35)

    with open(video_path, "rb") as f:
        response = client.post(
            "/api/feeds",
            data={
                "camera_id": 9901,
                "city": "Alexandria",
                "district": "District 2"
            },
            files={"file": ("test_camera.mp4", f, "video/mp4")}
        )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    feed_id = data["id"]
    assert data["camera_id"] == 9901
    assert data["city"] == "Alexandria"
    assert data["status"] in ("queued", "processing", "done")
    assert "thumbnail_url" in data

    # 1. Test thumbnail endpoint
    thumb_resp = client.get(f"/api/feeds/{feed_id}/thumbnail")
    assert thumb_resp.status_code == 200
    assert thumb_resp.headers["content-type"] == "image/jpeg"
    assert len(thumb_resp.content) > 100

    # 2. Test status endpoint
    status_resp = client.get(f"/api/feeds/{feed_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["id"] == feed_id
    assert "progress" in status_data
    assert "frames_sent" in status_data["progress"]

def test_feed_cancel(client, tmp_path):
    video_path = generate_test_mp4(tmp_path / "long_camera.mp4", num_frames=90, fps=15)

    with open(video_path, "rb") as f:
        response = client.post(
            "/api/feeds",
            data={
                "camera_id": 9902,
                "city": "Gizah",
                "district": "District 5"
            },
            files={"file": ("long_camera.mp4", f, "video/mp4")}
        )

    assert response.status_code == 201
    feed_id = response.json()["id"]

    # Cancel the feed
    cancel_resp = client.post(f"/api/feeds/{feed_id}/cancel")
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["id"] == feed_id
    assert cancel_data["status"] in ("cancelled", "done")

    # Check status reflects cancellation
    st_resp = client.get(f"/api/feeds/{feed_id}")
    assert st_resp.status_code == 200
    assert st_resp.json()["status"] in ("cancelled", "done")

def test_feed_validation_invalid_format(client, tmp_path):
    bad_file = tmp_path / "not_a_video.mp4"
    bad_file.write_text("This is not a real video content.")

    with open(bad_file, "rb") as f:
        response = client.post(
            "/api/feeds",
            data={"camera_id": 9903, "city": "Cairo", "district": "District 1"},
            files={"file": ("not_a_video.mp4", f, "video/mp4")}
        )

    assert response.status_code == 400
    data = response.json()
    assert "code" in data
    assert "corrupted" in data["message"].lower() or "stream" in data["message"].lower()

def test_feed_validation_disallowed_extension(client, tmp_path):
    bad_ext = tmp_path / "script.exe"
    bad_ext.write_bytes(b"MZ\x90\x00")

    with open(bad_ext, "rb") as f:
        response = client.post(
            "/api/feeds",
            data={"camera_id": 9904, "city": "Cairo", "district": "District 1"},
            files={"file": ("script.exe", f, "application/octet-stream")}
        )

    assert response.status_code == 400
    data = response.json()
    assert "Unsupported file format" in data["message"]

def test_feed_not_found(client):
    response = client.get("/api/feeds/non-existent-feed-id")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "NOT_FOUND"

def test_incidents_csv_export(client):
    response = client.get("/api/incidents/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment; filename=argus_incidents.csv" in response.headers.get("content-disposition", "")
    lines = response.text.strip().split("\n")
    assert len(lines) >= 1
    assert "Incident ID,Camera ID,Starting Frame,Crash Time,City,District,Status,Thumbnail URL,Video URL" in lines[0]
