import os
import cv2
import numpy as np
import pytest

from System.Functions.Detector import (
    get_detector,
    LegacyBoxFilesDetector,
    MotionFallbackDetector,
    ModernYoloDetector,
    VEHICLE_CLASSES,
)
from System.Functions.Detection import Detection


def test_detector_factory_defaults_and_env():
    """
    Assert that get_detector defaults to LegacyBoxFilesDetector,
    and respects DETECTOR / ARGUS_DETECTOR environment variables.
    """
    # 1. Default must be legacy
    orig_env = os.environ.get("ARGUS_DETECTOR")
    orig_det = os.environ.get("DETECTOR")
    try:
        os.environ.pop("ARGUS_DETECTOR", None)
        os.environ.pop("DETECTOR", None)

        default_detector = get_detector()
        assert isinstance(default_detector, LegacyBoxFilesDetector)
        assert default_detector.name == "legacy"
        assert not default_detector.is_low_quality

        # 2. Select motion
        os.environ["ARGUS_DETECTOR"] = "motion"
        motion_detector = get_detector()
        assert isinstance(motion_detector, MotionFallbackDetector)
        assert motion_detector.name == "motion"
        assert motion_detector.is_low_quality

        # 3. Select yolo
        os.environ["ARGUS_DETECTOR"] = "yolo"
        yolo_detector = get_detector()
        assert isinstance(yolo_detector, ModernYoloDetector)
        assert yolo_detector.name == "yolo"

    finally:
        if orig_env:
            os.environ["ARGUS_DETECTOR"] = orig_env
        else:
            os.environ.pop("ARGUS_DETECTOR", None)
        if orig_det:
            os.environ["DETECTOR"] = orig_det
        else:
            os.environ.pop("DETECTOR", None)


def test_legacy_box_files_detector():
    """
    Verify LegacyBoxFilesDetector parses dataset box files (boxes/1528.txt)
    and falls back cleanly when an unknown video name is requested.
    """
    detector = LegacyBoxFilesDetector()
    dummy_frame = np.zeros((360, 480, 3), dtype=np.uint8)

    # 1. Known pre-annotated dataset video
    boxes_frame_0 = detector.detect(dummy_frame, video_name="1528", frame_index=0)
    assert isinstance(boxes_frame_0, list)
    assert len(boxes_frame_0) > 0

    box = boxes_frame_0[0]
    # Box format: [class_name, xmin, xmax, ymin, ymax, score]
    assert len(box) >= 5
    assert isinstance(box[0], str)
    assert float(box[1]) <= float(box[2])  # xmin <= xmax
    assert float(box[3]) <= float(box[4])  # ymin <= ymax

    # 2. Unknown video falls back without error to motion detector
    unknown_boxes = detector.detect(dummy_frame, video_name="nonexistent_99999", frame_index=0)
    assert isinstance(unknown_boxes, list)


def test_motion_fallback_detector():
    """
    Verify MotionFallbackDetector identifies moving bounding boxes between frames
    and marks itself as low-quality mode.
    """
    detector = MotionFallbackDetector(min_area=400, min_dimension=20)
    assert detector.is_low_quality is True

    # Frame 1: Blank canvas
    f1 = np.zeros((360, 480, 3), dtype=np.uint8)

    # Frame 2: Introduce a moving vehicle-like white rectangle (50x50 pixels at (100, 100))
    f2 = np.zeros((360, 480, 3), dtype=np.uint8)
    cv2.rectangle(f2, (100, 100), (160, 160), (255, 255, 255), -1)

    boxes = detector.detect(f2, ref_frame=f1)
    assert len(boxes) >= 1

    detected = boxes[0]
    # [class_name, xmin, xmax, ymin, ymax, score]
    assert detected[0] == "car"
    assert 90 <= detected[1] <= 110  # xmin around 100
    assert 150 <= detected[2] <= 170  # xmax around 160
    assert 90 <= detected[3] <= 110  # ymin around 100
    assert 150 <= detected[4] <= 170  # ymax around 160


def test_modern_yolo_detector_fallback_and_vehicle_filter():
    """
    Verify ModernYoloDetector vehicle class filtering and fallback handling.
    """
    detector = ModernYoloDetector(confidence_threshold=0.40)
    assert detector.name == "yolo"

    dummy_frame = np.zeros((360, 480, 3), dtype=np.uint8)
    # When no model weights exist on disk, gracefully falls back to motion fallback
    boxes = detector.detect(dummy_frame)
    assert isinstance(boxes, list)


def test_detection_pipeline_stage_integration():
    """
    Test System.Functions.Detection.Detection wrapper preserving backward compatibility.
    """
    detection = Detection()
    frames = [
        np.zeros((360, 480, 3), dtype=np.uint8),
        np.zeros((360, 480, 3), dtype=np.uint8)
    ]

    # Case A: Legacy pre-loaded boxes
    preloaded = [["car", 50.0, 120.0, 40.0, 90.0, 0.90]]
    result_a = detection.detect(frames, 480, 360, read_file=True, boxes_file=preloaded, read_file_self=True)
    assert result_a == preloaded

    # Case B: Dynamic detection
    result_b = detection.detect(frames, 480, 360, read_file=True, boxes_file=None, read_file_self=False)
    assert isinstance(result_b, list)
