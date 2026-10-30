import os
import subprocess
import sys
import time
from pathlib import Path
import pytest
from backend.app.services.database import apply_migrations, get_db_connection

def test_get_settings_default(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "alert_sound_enabled" in data
    assert "siren_volume" in data
    assert data["siren_volume"] == 80
    assert "clip_retention_days" in data
    assert data["clip_retention_days"] == 30
    assert "min_alert_confidence" in data
    assert data["min_alert_confidence"] == 0.5
    assert "confidence_note" in data

def test_update_settings_persistence(client):
    payload = {
        "alert_sound_enabled": True,
        "siren_volume": 65,
        "clip_retention_days": 45,
        "min_alert_confidence": 0.75,
    }
    put_res = client.put("/api/settings", json=payload)
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["alert_sound_enabled"] is True
    assert data["siren_volume"] == 65
    assert data["clip_retention_days"] == 45
    assert data["min_alert_confidence"] == 0.75
    assert data["updated_at"] is not None

    # Verify subsequent GET returns the updated configuration
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["alert_sound_enabled"] is True
    assert get_data["siren_volume"] == 65
    assert get_data["clip_retention_days"] == 45
    assert get_data["min_alert_confidence"] == 0.75

def test_update_settings_validation_errors(client):
    # Invalid volume (< 0)
    res = client.put("/api/settings", json={
        "alert_sound_enabled": True,
        "siren_volume": -10,
        "clip_retention_days": 30,
        "min_alert_confidence": 0.5,
    })
    assert res.status_code == 422

    # Invalid volume (> 100)
    res = client.put("/api/settings", json={
        "alert_sound_enabled": True,
        "siren_volume": 120,
        "clip_retention_days": 30,
        "min_alert_confidence": 0.5,
    })
    assert res.status_code == 422

    # Invalid retention days (< 1)
    res = client.put("/api/settings", json={
        "alert_sound_enabled": True,
        "siren_volume": 80,
        "clip_retention_days": 0,
        "min_alert_confidence": 0.5,
    })
    assert res.status_code == 422

    # Invalid retention days (> 365)
    res = client.put("/api/settings", json={
        "alert_sound_enabled": True,
        "siren_volume": 80,
        "clip_retention_days": 400,
        "min_alert_confidence": 0.5,
    })
    assert res.status_code == 422

    # Invalid confidence threshold (> 1.0)
    res = client.put("/api/settings", json={
        "alert_sound_enabled": True,
        "siren_volume": 80,
        "clip_retention_days": 30,
        "min_alert_confidence": 1.5,
    })
    assert res.status_code == 422

def test_dry_run_and_apply_clip_cleanup(tmp_path):
    # Create test clip files
    clip_dir = tmp_path / "clips"
    clip_dir.mkdir()

    old_clip = clip_dir / "old_crash.mp4"
    old_clip.write_text("old video bytes")

    new_clip = clip_dir / "new_crash.mp4"
    new_clip.write_text("new video bytes")

    # Set old clip mtime to 45 days ago
    past_time = time.time() - (45 * 86400)
    os.utime(old_clip, (past_time, past_time))

    script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "cleanup_clips.py"

    # 1. Run dry-run mode (default, no --apply)
    cmd_dry = [
        sys.executable,
        str(script_path),
        "--days", "30",
        "--dir", str(clip_dir),
    ]
    proc_dry = subprocess.run(cmd_dry, capture_output=True, text=True, check=True)
    assert "[WOULD DELETE]" in proc_dry.stdout
    assert "old_crash.mp4" in proc_dry.stdout
    # Verify BOTH files still exist on disk
    assert old_clip.exists(), "Dry run must NOT delete files!"
    assert new_clip.exists()

    # 2. Run with --apply
    cmd_apply = [
        sys.executable,
        str(script_path),
        "--days", "30",
        "--dir", str(clip_dir),
        "--apply",
    ]
    proc_apply = subprocess.run(cmd_apply, capture_output=True, text=True, check=True)
    assert "[DELETED]" in proc_apply.stdout
    assert "old_crash.mp4" in proc_apply.stdout

    # Verify old file is deleted, new file is preserved
    assert not old_clip.exists(), "Applied cleanup should delete expired file!"
    assert new_clip.exists(), "Newer file within retention window must be preserved!"
