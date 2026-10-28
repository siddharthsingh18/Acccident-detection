import os
from typing import Optional
from System.Functions.Detector.base import BaseDetector
from System.Functions.Detector.legacy import LegacyBoxFilesDetector
from System.Functions.Detector.motion import MotionFallbackDetector
from System.Functions.Detector.yolo import ModernYoloDetector


def get_detector(name: Optional[str] = None) -> BaseDetector:
    """
    Factory function to retrieve the configured vehicle detector.
    Selected via configuration or environment variable (ARGUS_DETECTOR or DETECTOR).
    Options:
      - 'legacy' (DEFAULT): Reads pre-annotated dataset box files.
      - 'yolo': Modern neural vehicle detector (Apache-2.0 / BSD / MIT).
      - 'motion': Naive frame differencing motion detector (low-quality fallback).
    """
    selected = (name or os.getenv("ARGUS_DETECTOR", os.getenv("DETECTOR", "legacy"))).strip().lower()

    if selected == "yolo":
        return ModernYoloDetector()
    elif selected == "motion":
        return MotionFallbackDetector()
    elif selected == "legacy":
        return LegacyBoxFilesDetector()
    else:
        return LegacyBoxFilesDetector()
