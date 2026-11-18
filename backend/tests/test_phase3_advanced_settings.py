import io
import json
from pathlib import Path
import pytest
import numpy as np
import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def generate_short_mp4(filepath: Path, num_frames=10, fps=25):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(filepath), fourcc, fps, (480, 360))
    for i in range(num_frames):
        frame = np.full((360, 480, 3), i * 15, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return filepath


def test_post_feeds_bounds_validation(client, tmp_path):
    """Verify POST /api/feeds rejects invalid parameter bounds with HTTP 422."""
    vid = generate_short_mp4(tmp_path / "valid.mp4")

    # 1. Invalid confidence < 0.05
    with open(vid, "rb") as f:
        resp = client.post(
            "/api/feeds",
            data={"camera_id": 101, "city": "Cairo", "district": "District 1", "detector_confidence": 0.02},
            files={"file": ("valid.mp4", f, "video/mp4")}
        )
    assert resp.status_code == 422
    assert "detector_confidence" in resp.text

    # 2. Invalid confidence > 0.95
    with open(vid, "rb") as f:
        resp = client.post(
            "/api/feeds",
            data={"camera_id": 101, "city": "Cairo", "district": "District 1", "detector_confidence": 0.99},
            files={"file": ("valid.mp4", f, "video/mp4")}
        )
    assert resp.status_code == 422

    # 3. Invalid distance_factor < 0.10
    with open(vid, "rb") as f:
        resp = client.post(
            "/api/feeds",
            data={"camera_id": 101, "city": "Cairo", "district": "District 1", "distance_factor": 0.05},
            files={"file": ("valid.mp4", f, "video/mp4")}
        )
    assert resp.status_code == 422

    # 4. Invalid frame_stride > 10
    with open(vid, "rb") as f:
        resp = client.post(
            "/api/feeds",
            data={"camera_id": 101, "city": "Cairo", "district": "District 1", "frame_stride": 15},
            files={"file": ("valid.mp4", f, "video/mp4")}
        )
    assert resp.status_code == 422


def test_post_feeds_persists_effective_config_and_isolation(client, tmp_path):
    """Verify valid overrides are accepted, stored in effective config, and isolated between runs."""
    from app.services.feed_manager import feed_manager

    vid_a = generate_short_mp4(tmp_path / "vid_a.mp4")

    # Run A with confidence 0.20 and single_vehicle=True
    with open(vid_a, "rb") as f:
        resp_a = client.post(
            "/api/feeds",
            data={
                "camera_id": 1001,
                "city": "Alexandria",
                "district": "District 1",
                "detector_confidence": 0.20,
                "single_vehicle_mode": "true",
                "distance_factor": 0.40,
                "frame_stride": 2,
                "is_test": "true",
            },
            files={"file": ("vid_a.mp4", f, "video/mp4")}
        )
    assert resp_a.status_code == 201
    data_a = resp_a.json()
    run_a_id = data_a["id"]
    cfg_a = data_a["detector_config"]
    assert cfg_a["detector_confidence"] == 0.20
    assert cfg_a["single_vehicle_mode"] is True
    assert cfg_a["distance_factor"] == 0.40
    assert cfg_a["frame_stride"] == 2

    # Run B with default settings or different overrides (confidence 0.50)
    # Ensure Run A's overrides did not mutate global state
    vid_b = generate_short_mp4(tmp_path / "vid_b.mp4")
    # Cancel Run A to allow Run B
    client.post(f"/api/feeds/{run_a_id}/cancel")

    with open(vid_b, "rb") as f:
        resp_b = client.post(
            "/api/feeds",
            data={
                "camera_id": 1002,
                "city": "Cairo",
                "district": "District 2",
                "detector_confidence": 0.50,
                "single_vehicle_mode": "false",
            },
            files={"file": ("vid_b.mp4", f, "video/mp4")}
        )
    assert resp_b.status_code == 201
    data_b = resp_b.json()
    run_b_id = data_b["id"]
    cfg_b = data_b["detector_config"]
    assert cfg_b["detector_confidence"] == 0.50
    assert cfg_b["single_vehicle_mode"] is False

    # Check isolation: Run A's stored config in feed_manager must remain 0.20
    item_a = feed_manager.feeds[run_a_id]
    assert item_a.detector_config["detector_confidence"] == 0.20
    assert item_a.detector_config["single_vehicle_mode"] is True

    # Test comparison endpoint
    comp_resp = client.get(f"/api/feeds/{run_a_id}/compare/{run_b_id}")
    assert comp_resp.status_code == 200
    comp_data = comp_resp.json()
    assert comp_data["run_a_id"] == run_a_id
    assert comp_data["run_b_id"] == run_b_id
    diffs = comp_data["differences"]["config_diff"]
    assert "detector_confidence" in diffs
    assert diffs["detector_confidence"]["run_a"] == 0.20
    assert diffs["detector_confidence"]["run_b"] == 0.50

    # Cleanup
    client.post(f"/api/feeds/{run_b_id}/cancel")


def test_rerun_feed_with_overrides(client, tmp_path):
    """Verify rerun_feed reuses stored upload with overridden parameters and preserves test tag."""
    from app.services.feed_manager import feed_manager

    vid = generate_short_mp4(tmp_path / "orig.mp4")
    with open(vid, "rb") as f:
        resp = client.post(
            "/api/feeds",
            data={"camera_id": 2001, "city": "Giza", "district": "District 3", "is_test": "true", "detector_confidence": 0.35},
            files={"file": ("orig.mp4", f, "video/mp4")}
        )
    assert resp.status_code == 201
    orig_id = resp.json()["id"]

    # Cancel original
    client.post(f"/api/feeds/{orig_id}/cancel")

    # Re-run with new confidence 0.15 and distance_factor 0.33
    rerun_resp = client.post(
        f"/api/feeds/{orig_id}/rerun",
        json={
            "detector_confidence": 0.15,
            "distance_factor": 0.33,
            "single_vehicle_mode": True,
            "is_test": True,
        }
    )
    assert rerun_resp.status_code == 201
    rerun_data = rerun_resp.json()
    rerun_id = rerun_data["id"]
    rerun_cfg = rerun_data["detector_config"]

    assert rerun_cfg["detector_confidence"] == 0.15
    assert rerun_cfg["distance_factor"] == 0.33
    assert rerun_cfg["single_vehicle_mode"] is True

    # Clean up
    client.post(f"/api/feeds/{rerun_id}/cancel")
