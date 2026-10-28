import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.database import apply_migrations, get_db_connection

@pytest.fixture
def client():
    # Ensure migrations are applied before testing
    apply_migrations()
    return TestClient(app)

def test_migration_runs_twice_safely(tmp_path):
    """
    Verify apply_migrations is fully idempotent and safe to run multiple times.
    """
    test_db = tmp_path / "test_migration.db"
    conn = sqlite3.connect(test_db)
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
    conn.execute("INSERT INTO CrashFrames VALUES (1, 10, 5, 'Cairo', 'District 1', '2026-10-28 10:00:00');")
    conn.commit()
    conn.close()

    # First migration run
    apply_migrations(str(test_db))

    conn = sqlite3.connect(test_db)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(CrashFrames);").fetchall()}
    assert "review_status" in cols
    assert "review_note" in cols
    assert "reviewed_at" in cols
    row = conn.execute("SELECT review_status, review_note, reviewed_at FROM CrashFrames WHERE camera_id = 1;").fetchone()
    assert row[0] is None
    conn.close()

    # Second migration run (must not error or destroy existing data)
    apply_migrations(str(test_db))

    conn = sqlite3.connect(test_db)
    cols2 = {row[1] for row in conn.execute("PRAGMA table_info(CrashFrames);").fetchall()}
    assert cols == cols2
    assert conn.execute("SELECT COUNT(*) FROM CrashFrames;").fetchone()[0] == 1
    conn.close()

def test_patch_incident_review_success(client):
    """
    Test reviewing an existing incident as confirmed with a review note.
    """
    # 1. Fetch an incident to review
    incidents_res = client.get("/api/incidents?limit=1")
    assert incidents_res.status_code == 200
    items = incidents_res.json()["items"]
    assert len(items) > 0
    incident_id = items[0]["id"]

    # 2. Confirm the incident
    payload = {
        "status": "confirmed",
        "note": "Verified multi-vehicle collision by operator #42."
    }
    review_res = client.patch(f"/api/incidents/{incident_id}/review", json=payload)
    assert review_res.status_code == 200
    data = review_res.json()
    assert data["id"] == incident_id
    assert data["review_status"] == "confirmed"
    assert data["review_note"] == payload["note"]
    assert data["reviewed_at"] is not None

    # 3. Verify single incident GET reflects the new review fields
    get_res = client.get(f"/api/incidents/{incident_id}")
    assert get_res.status_code == 200
    assert get_res.json()["review_status"] == "confirmed"
    assert get_res.json()["review_note"] == payload["note"]

    # 4. Change status to false_alarm
    fa_payload = {
        "status": "false_alarm",
        "note": "Sudden lane change without contact."
    }
    fa_res = client.patch(f"/api/incidents/{incident_id}/review", json=fa_payload)
    assert fa_res.status_code == 200
    assert fa_res.json()["review_status"] == "false_alarm"
    assert fa_res.json()["review_note"] == fa_payload["note"]

def test_patch_incident_review_validation_errors(client):
    """
    Ensure invalid review status and oversized notes are rejected.
    """
    # Invalid status
    res = client.patch("/api/incidents/1528_76/review", json={"status": "invalid_status"})
    assert res.status_code == 422

    # Oversized note (> 500 chars)
    long_note = "A" * 501
    res = client.patch("/api/incidents/1528_76/review", json={"status": "confirmed", "note": long_note})
    assert res.status_code == 422

def test_patch_incident_review_not_found(client):
    """
    Reviewing a non-existent incident returns 404.
    """
    res = client.patch("/api/incidents/99999_99999/review", json={"status": "confirmed", "note": "Test note"})
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"

def test_list_incidents_filter_by_review_status(client):
    """
    Test filtering incidents by review_status (unreviewed, confirmed, false_alarm).
    """
    # Grab an incident and confirm it
    items = client.get("/api/incidents?limit=2").json()["items"]
    assert len(items) >= 2
    inc1 = items[0]["id"]
    inc2 = items[1]["id"]

    client.patch(f"/api/incidents/{inc1}/review", json={"status": "confirmed", "note": "Confirmed test"})
    client.patch(f"/api/incidents/{inc2}/review", json={"status": "false_alarm", "note": "False alarm test"})

    # Filter confirmed
    confirmed_res = client.get("/api/incidents?review_status=confirmed")
    assert confirmed_res.status_code == 200
    confirmed_items = confirmed_res.json()["items"]
    assert all(item["review_status"] == "confirmed" for item in confirmed_items)

    # Filter false_alarm
    fa_res = client.get("/api/incidents?review_status=false_alarm")
    assert fa_res.status_code == 200
    fa_items = fa_res.json()["items"]
    assert all(item["review_status"] == "false_alarm" for item in fa_items)

    # Filter unreviewed
    unrev_res = client.get("/api/incidents?review_status=unreviewed")
    assert unrev_res.status_code == 200
    unrev_items = unrev_res.json()["items"]
    assert all(item["review_status"] is None for item in unrev_items)

def test_csv_export_includes_review_fields(client):
    """
    Verify CSV export includes Review Status, Review Note, and Reviewed At columns.
    """
    res = client.get("/api/incidents/export")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    csv_text = res.text
    header_line = csv_text.splitlines()[0]
    assert "Review Status" in header_line
    assert "Review Note" in header_line
    assert "Reviewed At" in header_line
