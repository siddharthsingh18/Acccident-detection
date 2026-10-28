from .base import BaseDetector, DetectionBox, VEHICLE_CLASSES
from .factory import get_detector
from .legacy import LegacyBoxFilesDetector
from .motion import MotionFallbackDetector
from .yolo import ModernYoloDetector

__all__ = [
    "BaseDetector",
    "DetectionBox",
    "VEHICLE_CLASSES",
    "get_detector",
    "LegacyBoxFilesDetector",
    "MotionFallbackDetector",
    "ModernYoloDetector",
]
