import os
import numpy as np
import pytest
from unittest.mock import MagicMock

from System.Functions.Crashing import Crashing
from Mosse_Tracker.TrackerManager import TrackerType


class DummyTracker:
    def __init__(self, width=60, height=40, speed=60, center=(100, 100)):
        self.tracker_id = 1
        self.vehicle_width = width
        self.vehicle_height = height
        self.speed = speed
        self.center = center
        self.tracker_type = TrackerType.MOSSE

        # Mock MOSSE internal tracker
        self.tracker = MagicMock()
        self.tracker.centers = [center for _ in range(30)]
        self.tracker.dx = [2.0 for _ in range(30)]
        self.tracker.dy = [0.0 for _ in range(30)]
        self.tracker.area = float(width * height)

        self.estimationFutureCenter = [center for _ in range(35)]
        self.history = [center for _ in range(30)]
        self.avg_speed = [speed for _ in range(35)]

    def isAboveSpeedLimit(self, f1, f2):
        return self.speed > 50

    def getAvgSpeed(self, f1, f2):
        return float(self.speed)

    def getFramesOfTracking(self, gray_frames, last_no_of_frames=30):
        # Return synthetic crop
        crops = [np.zeros((self.vehicle_height, self.vehicle_width), dtype=np.uint8) for _ in range(30)]
        xmin = int(self.center[0] - self.vehicle_width / 2)
        xmax = int(self.center[0] + self.vehicle_width / 2)
        ymin = int(self.center[1] - self.vehicle_height / 2)
        ymax = int(self.center[1] + self.vehicle_height / 2)
        return crops, self.vehicle_width, self.vehicle_height, xmin, xmax, ymin, ymax

    def saveTracking(self, frames):
        pass


@pytest.fixture
def mock_vif():
    vif = MagicMock()
    vif.process.return_value = np.zeros(304)
    vif.clf = MagicMock()
    vif.clf.predict.return_value = np.array([1.0])
    vif.clf.predict_proba.return_value = np.array([[0.45, 0.55]])
    return vif


def test_adaptive_box_filter_flag(monkeypatch, mock_vif):
    """Test boundary behavior of CRASH_ADAPTIVE_BOX_FILTER on smaller vehicle bounding boxes."""
    crashing = Crashing(mock_vif)
    synthetic_frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(30)]

    # Small vehicle: width=40, height=25 (less than 50x28)
    small_tracker = DummyTracker(width=40, height=25, speed=60)

    # 1. Default (flag off): hard floor 50x28 rejects vehicle
    monkeypatch.setenv("CRASH_ADAPTIVE_BOX_FILTER", "false")
    boxes = crashing.predict(synthetic_frames, [small_tracker])
    assert len(boxes) == 0
    assert crashing.last_failed_box_size > 0

    # 2. Flag on: adaptive 4% threshold (480*0.04 = 19px, 360*0.04 = 14px) accepts 40x25 vehicle
    monkeypatch.setenv("CRASH_ADAPTIVE_BOX_FILTER", "true")
    monkeypatch.setenv("CRASH_ADAPTIVE_BOX_FRACTION", "0.04")
    monkeypatch.setenv("CRASH_MIN_ASPECT_RATIO", "0.20")
    crashing.last_failed_box_size = 0
    boxes_adaptive = crashing.predict(synthetic_frames, [small_tracker])
    assert len(boxes_adaptive) == 1
    assert crashing.last_failed_box_size == 0


def test_distance_factor_flag(monkeypatch, mock_vif):
    """Test configurable distance multiplier CRASH_DISTANCE_FACTOR (default 0.25 vs 0.40)."""
    crashing = Crashing(mock_vif)

    # Trackers positioned 40px apart
    tA = DummyTracker(width=50, height=40, speed=60, center=(100, 100))
    tB = DummyTracker(width=50, height=40, speed=60, center=(140, 100))
    # Diagonal size ~ 64px
    # With factor 0.25: dis = (64 * 0.25) + (64 * 0.25) = 32px. Distance is 40 > 32 (FAILS)
    # With factor 0.40: dis = (64 * 0.40) + (64 * 0.40) = 51.2px. Distance is 40 < 51.2 (PASSES)

    monkeypatch.setenv("CRASH_DISTANCE_FACTOR", "0.25")
    passed_default, reason_default = crashing._check_distance_detailed(tA, tB, 16, dis=32.0)
    assert passed_default is False
    assert reason_default == "distance"

    monkeypatch.setenv("CRASH_DISTANCE_FACTOR", "0.40")
    # Dis is recalculated with 0.40 factor
    dis_expanded = (pow(50**2 + 40**2, 0.5) * 0.40) * 2
    # At frame 16 with actual distance 40 < dis_expanded (~51.2), geometry proceeds to deviation check
    passed_relaxed, reason_relaxed = crashing._check_distance_detailed(tA, tB, 16, dis=dis_expanded)
    assert reason_relaxed in ("passed", "deviation")


def test_single_vehicle_flag(monkeypatch, mock_vif):
    """Test CRASH_SINGLE_VEHICLE evaluates single tracker upon abrupt deceleration."""
    crashing = Crashing(mock_vif)
    synthetic_frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(30)]

    # Tracker that abruptly stops: speed 70 -> 10
    stopping_tracker = DummyTracker(width=60, height=40, speed=70)
    def mock_get_avg_speed(f1, f2):
        if f1 == 0:
            return 75.0
        return 15.0  # Decelerated by 80%
    stopping_tracker.getAvgSpeed = mock_get_avg_speed

    # 1. Default (flag off): single tracker is never evaluated
    monkeypatch.setenv("CRASH_SINGLE_VEHICLE", "false")
    res_off = crashing.crash(synthetic_frames, [stopping_tracker])
    assert len(res_off) == 0

    # 2. Flag on: single tracker with abrupt stop evaluates
    monkeypatch.setenv("CRASH_SINGLE_VEHICLE", "true")
    res_on = crashing.crash(synthetic_frames, [stopping_tracker])
    assert len(res_on) > 0


def test_classifier_threshold_flag(monkeypatch, mock_vif):
    """Test configurable classifier decision threshold CRASH_CLASSIFIER_THRESHOLD."""
    crashing = Crashing(mock_vif)
    synthetic_frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(30)]
    t = DummyTracker(width=60, height=40, speed=60)

    # Model returns proba 0.55
    mock_vif.clf.predict_proba.return_value = np.array([[0.45, 0.55]])

    # 1. Threshold 0.50 (default): 0.55 >= 0.50 -> crash
    monkeypatch.setenv("CRASH_CLASSIFIER_THRESHOLD", "0.50")
    res_pass = crashing.predict(synthetic_frames, [t])
    assert len(res_pass) > 0

    # 2. Threshold 0.60: 0.55 < 0.60 -> no crash
    monkeypatch.setenv("CRASH_CLASSIFIER_THRESHOLD", "0.60")
    res_fail = crashing.predict(synthetic_frames, [t])
    assert len(res_fail) == 0
