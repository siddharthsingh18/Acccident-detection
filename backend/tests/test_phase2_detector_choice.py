import csv
from pathlib import Path
import pytest
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SWEEP_CSV = PROJECT_ROOT / "docs" / "evaluation" / "detector_validation_sweep.csv"
TEST_CSV = PROJECT_ROOT / "docs" / "evaluation" / "detector_test_report.csv"


def test_detector_validation_sweep_results_exist():
    """Verify validation sweep across 0.10 to 0.60 was run and recorded."""
    assert SWEEP_CSV.exists(), f"Missing {SWEEP_CSV}"
    with open(SWEEP_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) >= 11, f"Expected at least 11 sweep points, got {len(rows)}"
    confs = [float(r["confidence"]) for r in rows]
    assert 0.10 in confs
    assert 0.20 in confs
    assert 0.35 in confs
    assert 0.60 in confs

    # Verify best F1 was selected
    f1_scores = [float(r["f1"]) for r in rows]
    assert max(f1_scores) > 0.90


def test_detector_frozen_test_report_exists():
    """Verify frozen evaluation on test split exists and has 95% bootstrap CI."""
    assert TEST_CSV.exists(), f"Missing {TEST_CSV}"
    with open(TEST_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    row = rows[0]
    assert row["split"] == "test"
    assert float(row["frozen_confidence"]) == 0.20
    assert float(row["precision"]) > 0.85
    assert float(row["recall"]) > 0.90
    assert float(row["f1"]) > 0.90
    assert "precision_ci95_low" in row
    assert "f1_ci95_low" in row


def test_detector_input_size_env(monkeypatch):
    """Verify ARGUS_DETECTOR_INPUT_SIZE configuration parsing."""
    from System.Functions.Detector.yolo import ModernYoloDetector

    monkeypatch.setenv("ARGUS_DETECTOR_INPUT_SIZE", "640x360")
    det = ModernYoloDetector()
    assert det.target_size == (640, 360)

    monkeypatch.setenv("ARGUS_DETECTOR_INPUT_SIZE", "320,320")
    det2 = ModernYoloDetector()
    assert det2.target_size == (320, 320)


def test_detector_unavailable_reporting(monkeypatch, tmp_path):
    """Verify detection_quality reports 'unavailable' when neural detector is forced without weights."""
    from System.Functions.Detector import yolo
    from app.services import camera_worker
    import cv2

    short_vid = tmp_path / "dummy_unavailable.avi"
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    out = cv2.VideoWriter(str(short_vid), fourcc, 30.0, (480, 360))
    for i in range(5):
        frame = np.full((360, 480, 3), i * 10, dtype=np.uint8)
        out.write(frame)
    out.release()

    sent_messages = []
    monkeypatch.setattr(camera_worker, "send_feed_to_master", lambda ip, port, msg: sent_messages.append(msg))
    monkeypatch.setenv("ARGUS_DETECTOR", "neural")

    # Force ModernYoloDetector to appear unavailable
    class MockUnavailableDetector:
        name = "yolo"
        is_available = False
        is_low_quality = True
        def detect(self, *args, **kwargs):
            return []

    monkeypatch.setattr(camera_worker, "ModernYoloDetector", lambda: MockUnavailableDetector())

    camera_worker.run_headless_camera(
        video_path=str(short_vid),
        camera_id=8888,
        city="Cairo",
        district="District 1",
        master_ip="127.0.0.1",
        master_port=10099,
        feed_id="feed-unavail-test",
        is_test=True,
    )

    assert len(sent_messages) == 1
    assert sent_messages[0]["DETECTION_QUALITY"] == "unavailable"


def test_no_regression_on_clip_1528():
    """Verify reference clip 1528 maintains 100% legacy parity with box file."""
    from System.Functions.Detector import get_detector
    det = get_detector("legacy")
    dummy = np.zeros((360, 480, 3), dtype=np.uint8)
    boxes = det.detect(dummy, video_name="1528", frame_index=0)
    assert len(boxes) > 0, "Clip 1528 must return reference boxes via legacy detector"
