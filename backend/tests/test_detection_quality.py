import pytest
import sqlite3
import tempfile
from pathlib import Path
from backend.app.models.schemas import FeedResponse, Incident, SampleItemResponse
from backend.app.services.database import apply_migrations, row_to_incident, get_db_connection
from System.Database.DatabaseConnection import DatabaseConnection


def test_schemas_detection_quality_defaults():
    # FeedResponse
    feed = FeedResponse(
        id="feed-1",
        camera_id=10,
        city="Cairo",
        district="District 1",
        status="done",
        progress={"frames_sent": 10, "total_frames": 10, "percent": 100},
        thumbnail_url="/thumb.jpg",
        created_at="2026-11-01T10:00:00Z",
        detection_quality="motion_fallback",
        detector_name="MotionFallbackDetector",
        vehicles_detected_count=0,
    )
    assert feed.detection_quality == "motion_fallback"
    assert feed.detector_name == "MotionFallbackDetector"
    assert feed.vehicles_detected_count == 0

    # Incident
    inc = Incident(
        id="1528_100",
        rowid=1,
        camera_id=1528,
        crash_time="2026-11-01 10:00:00",
        starting_frame_id=100,
        thumbnail_url="/thumb.jpg",
        video_url="/video.mp4",
        detection_quality="reference",
        detector_name="LegacyBoxFilesDetector",
    )
    assert inc.detection_quality == "reference"
    assert inc.detector_name == "LegacyBoxFilesDetector"

    # SampleItemResponse
    sample = SampleItemResponse(
        id="sample-1",
        name="sample1.mp4",
        relative_path="videos/sample1.mp4",
        size_bytes=1000,
        duration_s=10.0,
        resolution="640x360",
        fps=30,
        thumbnail_url="/thumb.jpg",
        video_url="/video.mp4",
        expected_label="normal",
        has_box_file=True,
        detection_quality="reference",
    )
    assert sample.has_box_file is True
    assert sample.detection_quality == "reference"


def test_row_to_incident_maps_quality_and_defaults_unknown():
    # Legacy row without detection_quality column
    legacy_row = {
        "rowid": 42,
        "camera_id": 1528,
        "frame_id": 50,
        "from_no": 5,
        "crash_time": "2026-11-01 10:00:00",
        "city": "Cairo",
        "district": "District 1",
    }
    inc_legacy = row_to_incident(legacy_row)
    assert inc_legacy.detection_quality == "unknown"
    assert inc_legacy.detector_name is None

    # Modern row with detection_quality and detector_name
    modern_row = {
        "rowid": 43,
        "camera_id": 1528,
        "frame_id": 50,
        "from_no": 5,
        "crash_time": "2026-11-01 10:00:00",
        "city": "Cairo",
        "district": "District 1",
        "detection_quality": "reference",
        "detector_name": "LegacyBoxFilesDetector",
    }
    inc_modern = row_to_incident(modern_row)
    assert inc_modern.detection_quality == "reference"
    assert inc_modern.detector_name == "LegacyBoxFilesDetector"


def test_database_migration_idempotent_and_inserts():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "test_argus.db"
        with sqlite3.connect(db_file) as conn:
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

        # Initialize schema and migrations
        apply_migrations(str(db_file))
        # Running a second time should be completely idempotent
        apply_migrations(str(db_file))

        # Inspect table schema to ensure columns and index exist
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(CrashFrames);")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            assert "detection_quality" in columns
            assert "detector_name" in columns

            # Insert via DatabaseConnection
            db_conn = DatabaseConnection(db_path=str(db_file))
            inc_id = db_conn.insertCrashFramesVid(
                camera_id=10,
                starting_frame_id=120,
                from_no=5,
                city="Cairo",
                district_no="District 1",
                detection_quality="motion_fallback",
                detector_name="MotionFallbackDetector",
                feed_id="feed-test-123",
                test=True,
            )
            assert inc_id > 0

            # Verify persisted values
            cursor.execute(
                "SELECT camera_id, frame_id, detection_quality, detector_name, feed_id, test FROM CrashFrames WHERE rowid = ?",
                (inc_id,),
            )
            row = cursor.fetchone()
            assert row[0] == 10
            assert row[1] == 120
            assert row[2] == "motion_fallback"
            assert row[3] == "MotionFallbackDetector"
            assert row[4] == "feed-test-123"
            assert row[5] == 1
