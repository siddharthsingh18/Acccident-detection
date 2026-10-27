import os
import sys
import sqlite3
import threading
import time
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from System.Database.DatabaseConnection import DatabaseConnection
from System.Data.CONSTANTS import CITY, DISTRICT, START_DATE, END_DATE, START_TIME, END_TIME


@pytest.fixture
def test_db(tmp_path):
    """Create an isolated test database with Argus schema."""
    db_file = tmp_path / "test_argus_integrity.db"
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
    c.execute("""
        CREATE TABLE SavedFrames (
            camera_id INTEGER,
            frame_id INTEGER
        );
    """)
    conn.commit()
    conn.close()
    return db_file


def test_sql_injection_defense(test_db):
    """Verify malicious SQL injection payloads are safely parameterized and stored literally."""
    db = DatabaseConnection(db_path=str(test_db))

    injection_payload = 'x"); DROP TABLE CrashFrames;--'
    db.insertCrashFramesVid(
        camera_id=901,
        starting_frame_id=10,
        from_no=1,
        city=injection_payload,
        district_no="District Injection"
    )

    # 1. Verify CrashFrames table still exists (not dropped)
    with db.connection() as conn:
        tables = conn.cursor().execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='CrashFrames';"
        ).fetchall()
        assert len(tables) == 1, "CrashFrames table should NOT have been dropped by injection!"

    # 2. Verify payload was stored literally
    crashes = db.selectCrashFrames()
    assert len(crashes) == 1
    stored_cam, stored_frame, stored_from, stored_city, stored_dist, _ = crashes[0]
    assert stored_city == injection_payload
    assert stored_cam == 901

    # 3. Verify parameterized search matching literal payload
    search_res = db.selectCrashFramesList({CITY: injection_payload})
    assert len(search_res) == 1
    assert search_res[0][2] == injection_payload


def test_wal_mode_and_busy_timeout(test_db):
    """Verify that WAL mode and busy timeout are configured on all connections."""
    db = DatabaseConnection(db_path=str(test_db))

    with db.connection() as conn:
        journal_mode = conn.cursor().execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal_mode.lower() == "wal", f"Expected WAL mode, got {journal_mode}"

        busy_timeout = conn.cursor().execute("PRAGMA busy_timeout;").fetchone()[0]
        assert busy_timeout >= 5000, f"Expected busy_timeout >= 5000, got {busy_timeout}"


def test_concurrent_readers_and_writers(test_db):
    """
    Stress test with simultaneous concurrent readers (simulating FastAPI backend)
    and concurrent writers (simulating Master / DatabaseThread).
    Asserts zero 'database is locked' errors occur under concurrent load.
    """
    db_path = str(test_db)
    errors = []
    num_writers = 5
    num_readers = 10
    ops_per_thread = 40

    def writer_worker(worker_id):
        try:
            db = DatabaseConnection(db_path=db_path)
            for i in range(ops_per_thread):
                cam_id = 1000 + worker_id
                frame_id = i * 30
                db.insertCrashFramesVid(cam_id, frame_id, 1, f"City-{worker_id}", f"District-{i}")
                db.insertSavedFramesVid(cam_id, frame_id)
                db.updateCrashFramesVid(cam_id, frame_id, min(i % 5 + 1, 5))
                time.sleep(0.005)
        except Exception as e:
            errors.append(f"Writer-{worker_id}: {type(e).__name__} - {str(e)}")

    def reader_worker(worker_id):
        try:
            db = DatabaseConnection(db_path=db_path)
            for _ in range(ops_per_thread):
                _ = db.selectCrashFrames()
                _ = db.selectCrashFramesLast10()
                _ = db.selectCrashFramesList({CITY: "City-0"})
                time.sleep(0.005)
        except Exception as e:
            errors.append(f"Reader-{worker_id}: {type(e).__name__} - {str(e)}")

    threads = []
    for w in range(num_writers):
        t = threading.Thread(target=writer_worker, args=(w,))
        threads.append(t)
    for r in range(num_readers):
        t = threading.Thread(target=reader_worker, args=(r,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Encountered concurrency errors: {errors}"

    # Verify final data written
    db = DatabaseConnection(db_path=db_path)
    with db.connection() as conn:
        count = conn.cursor().execute("SELECT count(*) FROM CrashFrames;").fetchone()[0]
        assert count == num_writers * ops_per_thread
