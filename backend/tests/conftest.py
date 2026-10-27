import asyncio
import os
import sqlite3
import tempfile
import cv2
import numpy as np
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def temp_environment(tmp_path):
    """Setup temporary database, media, and video directories for isolated testing."""
    db_file = tmp_path / "test_argus.db"
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE CrashFrames (
            camera_id INTEGER,
            frame_id INTEGER,
            from_no INTEGER,
            city TEXT,
            district TEXT,
            crash_time TEXT
        );
    """)
    # Insert sample incidents
    sample_data = [
        (1528, 76, 5, "Shibin El Kom", "District 13", "2021-01-07 09:39:31"),
        (1528, 106, 5, "Shibin El Kom", "District 13", "2021-01-07 09:39:32"),
        (1566, 151, 5, "Hurghada", "District 16", "2021-01-07 10:05:42"),
        (1521, 121, 5, "Qena", "District 2", "2021-01-07 10:12:43"),
        (1559, 91, 5, "Cairo", "District 7", "2021-01-07 10:34:32"),
    ]
    c.executemany("INSERT INTO CrashFrames VALUES (?, ?, ?, ?, ?, ?);", sample_data)
    conn.commit()
    conn.close()

    # Create temporary directories
    saved_crash_dir = tmp_path / "saved_crash_vid"
    saved_crash_dir.mkdir(parents=True, exist_ok=True)

    saved_frames_dir = tmp_path / "saved_frames_vid"
    saved_frames_dir.mkdir(parents=True, exist_ok=True)

    thumbnails_dir = tmp_path / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)

    video_cache_dir = tmp_path / "videos"
    video_cache_dir.mkdir(parents=True, exist_ok=True)

    # Create fallback image
    fallback_img = tmp_path / "notfound.png"
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imwrite(str(fallback_img), dummy_img)

    # Create short 1-second sample AVI video (1528) 76.avi
    sample_avi = saved_crash_dir / "(1528) 76.avi"
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(str(sample_avi), fourcc, 30.0, (480, 360))
    for i in range(95):  # at least 90 frames for frame 89 extraction
        frame = np.full((360, 480, 3), (i * 2) % 255, dtype=np.uint8)
        cv2.putText(frame, f"Crash {i}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        out.write(frame)
    out.release()

    # Patch settings
    orig_db = settings.DATABASE_PATH
    orig_crash_dir = settings.SAVED_CRASH_VID_DIR
    orig_frames_dir = settings.SAVED_FRAMES_VID_DIR
    orig_thumb_dir = settings.THUMBNAILS_DIR
    orig_cache_dir = settings.VIDEO_CACHE_DIR
    orig_fallback = settings.FALLBACK_IMAGE_PATH
    orig_alert_port = settings.ZMQ_ALERT_PORT

    settings.DATABASE_PATH = db_file
    settings.SAVED_CRASH_VID_DIR = saved_crash_dir
    settings.SAVED_FRAMES_VID_DIR = saved_frames_dir
    settings.THUMBNAILS_DIR = thumbnails_dir
    settings.VIDEO_CACHE_DIR = video_cache_dir
    settings.FALLBACK_IMAGE_PATH = fallback_img
    settings.ZMQ_ALERT_PORT = 10019

    yield {
        "db_file": db_file,
        "sample_avi": sample_avi,
        "thumbnails_dir": thumbnails_dir,
        "video_cache_dir": video_cache_dir,
    }

    # Restore settings
    settings.DATABASE_PATH = orig_db
    settings.SAVED_CRASH_VID_DIR = orig_crash_dir
    settings.SAVED_FRAMES_VID_DIR = orig_frames_dir
    settings.THUMBNAILS_DIR = orig_thumb_dir
    settings.VIDEO_CACHE_DIR = orig_cache_dir
    settings.FALLBACK_IMAGE_PATH = orig_fallback
    settings.ZMQ_ALERT_PORT = orig_alert_port

@pytest.fixture
def client(temp_environment):
    """FastAPI TestClient fixture with temporary test database."""
    with TestClient(app) as test_client:
        yield test_client
