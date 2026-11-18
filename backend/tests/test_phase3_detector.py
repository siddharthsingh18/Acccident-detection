import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from System.Functions.Detector.base import BaseDetector, DetectionBox
from System.Functions.Detector.factory import get_detector
from System.Functions.Detector.legacy import LegacyBoxFilesDetector
from System.Functions.Detector.motion import MotionFallbackDetector
from System.Functions.Detector.yolo import (
    COCO_VEHICLE_LABELS,
    TORCHVISION_VEHICLE_LABELS,
    ModernYoloDetector,
)
from boxes.registry import lookup_box_file


def test_vehicle_class_filtering():
    """Verify that only vehicle classes (car, motorcycle, bus, truck) are retained."""
    detector = ModernYoloDetector(confidence_threshold=0.30)
    detector._init_attempted = True
    detector._backend = "torchvision"

    # Mock torchvision model predictions with mixed classes:
    # 1: person, 2: bicycle, 3: car, 4: motorcycle, 6: bus, 8: truck, 10: traffic light
    mock_boxes = np.array([
        [10.0, 10.0, 50.0, 50.0],    # person (label 1) -> drop
        [20.0, 20.0, 60.0, 60.0],    # bicycle (label 2) -> drop
        [30.0, 30.0, 100.0, 100.0],  # car (label 3) -> keep
        [40.0, 40.0, 80.0, 80.0],    # motorcycle (label 4) -> keep
        [50.0, 50.0, 150.0, 150.0],  # bus (label 6) -> keep
        [60.0, 60.0, 200.0, 200.0],  # truck (label 8) -> keep
        [70.0, 70.0, 90.0, 90.0],    # traffic light (label 10) -> drop
    ])
    mock_scores = np.array([0.95, 0.90, 0.88, 0.85, 0.80, 0.75, 0.99])
    mock_labels = np.array([1, 2, 3, 4, 6, 8, 10])

    class MockTorchvisionNet:
        def __call__(self, tensors):
            import torch
            return [{
                "boxes": torch.from_numpy(mock_boxes),
                "scores": torch.from_numpy(mock_scores),
                "labels": torch.from_numpy(mock_labels),
            }]

    detector._net = MockTorchvisionNet()
    dummy_frame = np.zeros((360, 480, 3), dtype=np.uint8)
    boxes = detector.detect(dummy_frame)

    classes_detected = [b[0] for b in boxes]
    assert classes_detected == ["car", "motorcycle", "bus", "truck"]
    assert "person" not in classes_detected
    assert "bicycle" not in classes_detected
    assert "traffic light" not in classes_detected


def test_confidence_threshold_configuration(monkeypatch):
    """Verify that predictions below the confidence threshold are discarded."""
    monkeypatch.setenv("ARGUS_DETECTOR_CONFIDENCE", "0.60")
    detector = ModernYoloDetector()
    assert detector.conf_threshold == 0.60

    detector._init_attempted = True
    detector._backend = "torchvision"

    mock_boxes = np.array([
        [10.0, 10.0, 50.0, 50.0],  # car at 0.55 -> below threshold
        [60.0, 60.0, 100.0, 100.0], # car at 0.75 -> above threshold
    ])
    mock_scores = np.array([0.55, 0.75])
    mock_labels = np.array([3, 3])

    class MockNet:
        def __call__(self, tensors):
            import torch
            return [{
                "boxes": torch.from_numpy(mock_boxes),
                "scores": torch.from_numpy(mock_scores),
                "labels": torch.from_numpy(mock_labels),
            }]

    detector._net = MockNet()
    dummy_frame = np.zeros((360, 480, 3), dtype=np.uint8)
    boxes = detector.detect(dummy_frame)

    assert len(boxes) == 1
    assert boxes[0][5] == 0.75


def test_frame_stride_persistence():
    """Verify that frame stride skips heavy inference and persists cached boxes."""
    detector = ModernYoloDetector(frame_stride=3)
    assert detector.frame_stride == 3

    detector._init_attempted = True
    detector._backend = "torchvision"

    call_count = 0

    class MockCountingNet:
        def __call__(self, tensors):
            nonlocal call_count
            call_count += 1
            import torch
            return [{
                "boxes": torch.from_numpy(np.array([[10.0, 10.0, 50.0, 50.0]])),
                "scores": torch.from_numpy(np.array([0.90])),
                "labels": torch.from_numpy(np.array([3])),
            }]

    detector._net = MockCountingNet()
    dummy_frame = np.zeros((360, 480, 3), dtype=np.uint8)

    # Frame 0: should call net
    b0 = detector.detect(dummy_frame, frame_index=0)
    assert call_count == 1
    assert len(b0) == 1

    # Frame 1: stride skip -> should reuse b0 without calling net
    b1 = detector.detect(dummy_frame, frame_index=1)
    assert call_count == 1
    assert b1 == b0

    # Frame 2: stride skip -> should reuse b0 without calling net
    b2 = detector.detect(dummy_frame, frame_index=2)
    assert call_count == 1
    assert b2 == b0

    # Frame 3: stride hit -> should call net again
    b3 = detector.detect(dummy_frame, frame_index=3)
    assert call_count == 2
    assert len(b3) == 1


def test_graceful_fallback_when_weights_missing(monkeypatch, tmp_path):
    """Verify graceful degradation to MotionFallbackDetector when weights cannot be loaded."""
    monkeypatch.setattr("System.Functions.Detector.yolo.MODELS_DIR", tmp_path)

    # Patch torchvision import / initialization to simulate missing weights
    with patch("torchvision.models.detection.ssdlite320_mobilenet_v3_large", side_effect=RuntimeError("No weights")):
        detector = ModernYoloDetector(model_path=str(tmp_path / "nonexistent.onnx"))
        assert detector.is_available is False
        assert detector.is_low_quality is True
        assert detector.backend is None

        # detect() should gracefully fall back to MotionFallbackDetector without crashing
        dummy_frame = np.zeros((360, 480, 3), dtype=np.uint8)
        boxes = detector.detect(dummy_frame)
        assert isinstance(boxes, list)


def test_factory_auto_selection(monkeypatch):
    """Verify factory auto selection behaves correctly."""
    monkeypatch.setenv("ARGUS_DETECTOR", "auto")
    detector = get_detector()
    assert isinstance(detector, BaseDetector)
    # If weights are installed, auto returns ModernYoloDetector
    assert detector.name in ("yolo", "legacy")


def test_no_regression_on_clip_1528():
    """Verify that bundled clip 1528 resolves to registered box file with 100% legacy parity."""
    project_root = Path(__file__).resolve().parent.parent.parent
    clip_path = project_root / "videos" / "1528.mp4"
    assert clip_path.exists()

    box_file = lookup_box_file(clip_path)
    assert box_file is not None
    assert box_file.name == "1528.txt"

    # Legacy detector loading
    legacy = LegacyBoxFilesDetector()
    dummy_frame = np.zeros((360, 480, 3), dtype=np.uint8)
    boxes = legacy.detect(dummy_frame, video_path=str(clip_path), frame_index=0)

    assert len(boxes) > 0
    assert boxes[0][0] == "car"
