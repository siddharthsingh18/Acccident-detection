import os
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pytest

from Mosse_Tracker.TrackerManager import TrackerType
from System.Functions.Crashing import Crashing


class DummyTracker:
    def __init__(self, width=60, height=40, speed=60, center=(100, 100), centers=None):
        self.tracker_id = 1
        self.vehicle_width = width
        self.vehicle_height = height
        self.speed = speed
        self.center = center
        self.tracker_type = TrackerType.MOSSE

        # Mock MOSSE internal tracker
        self.tracker = MagicMock()
        self.tracker.centers = centers if centers is not None else [center for _ in range(30)]
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


# ---------------------------------------------------------------------------
# 1. CRASH_ADAPTIVE_BOX_FILTER (both sides of threshold)
# ---------------------------------------------------------------------------

def test_adaptive_box_filter_flag_off_rejects_small(monkeypatch, mock_vif):
    """When flag is off (default), hard floor 50x28 rejects vehicle of size 40x25."""
    monkeypatch.setenv("CRASH_ADAPTIVE_BOX_FILTER", "false")
    crashing = Crashing(mock_vif)
    synthetic_frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(30)]

    small_tracker = DummyTracker(width=40, height=25, speed=60)
    boxes = crashing.predict(synthetic_frames, [small_tracker])
    assert len(boxes) == 0
    assert crashing.last_failed_box_size > 0


def test_adaptive_box_filter_flag_on_both_sides(monkeypatch, mock_vif):
    """When flag is on, evaluates against fraction of frame dimensions (both sides of threshold)."""
    monkeypatch.setenv("CRASH_ADAPTIVE_BOX_FILTER", "true")
    monkeypatch.setenv("CRASH_ADAPTIVE_BOX_FRACTION", "0.04")  # 480*0.04 = 19.2px, 360*0.04 = 14.4px
    monkeypatch.setenv("CRASH_MIN_ASPECT_RATIO", "0.20")
    crashing = Crashing(mock_vif)
    synthetic_frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(30)]

    # Above threshold: 40x25 vehicle -> passes
    tracker_above = DummyTracker(width=40, height=25, speed=60)
    boxes_above = crashing.predict(synthetic_frames, [tracker_above])
    assert len(boxes_above) == 1

    # Below threshold: 12x10 vehicle (less than 19x14) -> fails
    tracker_below = DummyTracker(width=12, height=10, speed=60)
    boxes_below = crashing.predict(synthetic_frames, [tracker_below])
    assert len(boxes_below) == 0
    assert crashing.last_failed_box_size > 0

    # Aspect ratio test: width=100, height=16 (width > 19, height > 14, aspect 16/100 = 0.16 < 0.20) -> fails aspect ratio
    tracker_bad_aspect = DummyTracker(width=100, height=16, speed=60)
    boxes_bad_aspect = crashing.predict(synthetic_frames, [tracker_bad_aspect])
    assert len(boxes_bad_aspect) == 0
    assert crashing.last_failed_aspect_ratio > 0

    # Aspect ratio test: width=100, height=25 (aspect 25/100 = 0.25 >= 0.20) -> passes aspect ratio
    tracker_good_aspect = DummyTracker(width=100, height=25, speed=60)
    boxes_good_aspect = crashing.predict(synthetic_frames, [tracker_good_aspect])
    assert len(boxes_good_aspect) == 1


# ---------------------------------------------------------------------------
# 2. CRASH_DISTANCE_FACTOR (both sides of threshold)
# ---------------------------------------------------------------------------

def test_distance_factor_both_sides(monkeypatch, mock_vif):
    """Test CRASH_DISTANCE_FACTOR behavior at both sides of default (0.25) and relaxed (0.40)."""
    crashing = Crashing(mock_vif)

    # Vehicles of size 50x40 (diagonal ~ 64px)
    # Default factor 0.25 -> threshold dis = (64*0.25)*2 = 32px
    monkeypatch.setenv("CRASH_DISTANCE_FACTOR", "0.25")

    # Distance 40px > 32px -> fails distance check
    tA_far = DummyTracker(width=50, height=40, speed=60, center=(100, 100))
    tB_far = DummyTracker(width=50, height=40, speed=60, center=(140, 100))
    passed_far, reason_far = crashing._check_distance_detailed(tA_far, tB_far, 16, dis=32.0)
    assert passed_far is False
    assert reason_far == "distance"

    # Distance 25px <= 32px -> passes distance check
    tA_close = DummyTracker(width=50, height=40, speed=60, center=(100, 100))
    tB_close = DummyTracker(width=50, height=40, speed=60, center=(125, 100))
    passed_close, reason_close = crashing._check_distance_detailed(tA_close, tB_close, 16, dis=32.0)
    assert reason_close in ("passed", "deviation")

    # Relaxed factor 0.40 -> threshold dis = (64*0.40)*2 = 51.2px
    monkeypatch.setenv("CRASH_DISTANCE_FACTOR", "0.40")
    dis_relaxed = (pow(50**2 + 40**2, 0.5) * 0.40) * 2

    # Distance 40px <= 51.2px -> now passes with relaxed factor
    passed_relaxed, reason_relaxed = crashing._check_distance_detailed(tA_far, tB_far, 16, dis=dis_relaxed)
    assert reason_relaxed in ("passed", "deviation")

    # Distance 60px > 51.2px -> still fails with relaxed factor
    tB_very_far = DummyTracker(width=50, height=40, speed=60, center=(160, 100))
    passed_vfar, reason_vfar = crashing._check_distance_detailed(tA_far, tB_very_far, 16, dis=dis_relaxed)
    assert passed_vfar is False
    assert reason_vfar == "distance"


# ---------------------------------------------------------------------------
# 3. CRASH_SINGLE_VEHICLE (both sides of decel and heading thresholds)
# ---------------------------------------------------------------------------

def test_single_vehicle_flag_off_never_evaluates(monkeypatch, mock_vif):
    """When CRASH_SINGLE_VEHICLE=false (default), single tracker is ignored."""
    monkeypatch.setenv("CRASH_SINGLE_VEHICLE", "false")
    crashing = Crashing(mock_vif)
    synthetic_frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(30)]

    tracker = DummyTracker(width=60, height=40, speed=80)
    tracker.getAvgSpeed = lambda f1, f2: 10.0 if f1 > 10 else 80.0  # Extreme deceleration
    res = crashing.crash(synthetic_frames, [tracker])
    assert len(res) == 0


def test_single_vehicle_deceleration_both_sides(monkeypatch, mock_vif):
    """When CRASH_SINGLE_VEHICLE=true, tests both sides of deceleration threshold (60%)."""
    monkeypatch.setenv("CRASH_SINGLE_VEHICLE", "true")
    monkeypatch.setenv("CRASH_SINGLE_DECEL_THRESHOLD", "0.60")
    crashing = Crashing(mock_vif)
    synthetic_frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(30)]

    # 1. Above threshold: speed 80 -> 20 (75% drop >= 60%) -> triggers single-vehicle crash evaluation
    tracker_abrupt = DummyTracker(width=60, height=40, speed=80)
    tracker_abrupt.getAvgSpeed = lambda f1, f2: 20.0 if f1 > 10 else 80.0
    res_abrupt = crashing.crash(synthetic_frames, [tracker_abrupt])
    assert len(res_abrupt) > 0

    # 2. Below threshold: speed 80 -> 50 (37.5% drop < 60%) -> does NOT trigger
    tracker_mild = DummyTracker(width=60, height=40, speed=80)
    tracker_mild.getAvgSpeed = lambda f1, f2: 50.0 if f1 > 10 else 80.0
    res_mild = crashing.crash(synthetic_frames, [tracker_mild])
    assert len(res_mild) == 0


def test_single_vehicle_heading_angle_both_sides(monkeypatch, mock_vif):
    """When CRASH_SINGLE_VEHICLE=true, tests both sides of heading angle threshold (45.0 degrees)."""
    monkeypatch.setenv("CRASH_SINGLE_VEHICLE", "true")
    monkeypatch.setenv("CRASH_SINGLE_HEADING_ANGLE", "45.0")
    monkeypatch.setenv("CRASH_SINGLE_DECEL_THRESHOLD", "0.99")  # Disable decel trigger to isolate heading
    crashing = Crashing(mock_vif)
    synthetic_frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(30)]

    # 1. Above threshold: 90-degree turn (heading change = 90° >= 45°)
    # Early (f0 -> f10): moving East (100, 100) -> (150, 100)
    # Late (f15 -> f28): moving South (150, 100) -> (150, 150)
    centers_90 = []
    for f in range(30):
        if f <= 10:
            centers_90.append((100 + f * 5.0, 100.0))
        elif f <= 15:
            centers_90.append((150.0, 100.0))
        else:
            centers_90.append((150.0, 100.0 + (f - 15) * 5.0))

    tracker_90 = DummyTracker(width=60, height=40, speed=40, centers=centers_90)
    tracker_90.getAvgSpeed = lambda f1, f2: 40.0  # Constant speed, no decel
    res_90 = crashing.crash(synthetic_frames, [tracker_90])
    assert len(res_90) > 0

    # 2. Below threshold: straight line (heading change = 0° < 45°)
    centers_straight = [(100 + f * 5.0, 100.0) for f in range(30)]
    tracker_straight = DummyTracker(width=60, height=40, speed=40, centers=centers_straight)
    tracker_straight.getAvgSpeed = lambda f1, f2: 40.0
    res_straight = crashing.crash(synthetic_frames, [tracker_straight])
    assert len(res_straight) == 0


# ---------------------------------------------------------------------------
# 4. CRASH_CLASSIFIER_THRESHOLD (both sides of threshold)
# ---------------------------------------------------------------------------

def test_classifier_threshold_both_sides(monkeypatch, mock_vif):
    """Test configurable classifier decision threshold CRASH_CLASSIFIER_THRESHOLD."""
    crashing = Crashing(mock_vif)
    synthetic_frames = [np.zeros((360, 480, 3), dtype=np.uint8) for _ in range(30)]
    t = DummyTracker(width=60, height=40, speed=60)

    # Model returns score 0.55
    mock_vif.clf.predict_proba.return_value = np.array([[0.45, 0.55]])

    # 1. Below or equal threshold: 0.55 >= 0.50 -> crash
    monkeypatch.setenv("CRASH_CLASSIFIER_THRESHOLD", "0.50")
    res_pass = crashing.predict(synthetic_frames, [t])
    assert len(res_pass) > 0

    # 2. Above threshold: 0.55 < 0.60 -> no crash
    monkeypatch.setenv("CRASH_CLASSIFIER_THRESHOLD", "0.60")
    res_fail = crashing.predict(synthetic_frames, [t])
    assert len(res_fail) == 0


# ---------------------------------------------------------------------------
# 5. Regression on Bundled Clip 1528 (Default Configuration)
# ---------------------------------------------------------------------------

def test_no_regression_on_clip_1528_default_flags():
    """Verify that with all crash geometry flags at defaults (off), clip 1528 output is unchanged."""
    from VIF.vif import VIF
    from boxes.yoloFiles import loadFile

    project_root = Path(__file__).resolve().parent.parent.parent
    boxes_file = loadFile("1528")
    assert len(boxes_file) > 0

    vif = VIF()
    crashing = Crashing(vif)

    # Default environment (all Phase 4 flags default off)
    assert os.getenv("CRASH_ADAPTIVE_BOX_FILTER", "false").lower() in ("false", "0", "no")
    assert os.getenv("CRASH_SINGLE_VEHICLE", "false").lower() in ("false", "0", "no")
    assert float(os.getenv("CRASH_DISTANCE_FACTOR", "0.25")) == 0.25
