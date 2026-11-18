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
      - 'yolo' / 'neural': Modern permissive neural vehicle detector (BSD-3 / Apache-2.0).
      - 'auto': Selects neural detector if available, otherwise legacy/motion.
      - 'motion': Naive frame differencing motion detector (low-quality fallback).
    """
    selected = (name or os.getenv("ARGUS_DETECTOR", os.getenv("DETECTOR", "legacy"))).strip().lower()

    if selected in ("yolo", "neural"):
        return ModernYoloDetector()
    elif selected == "motion":
        return MotionFallbackDetector()
    elif selected == "auto":
        neural = ModernYoloDetector()
        if neural.is_available:
            return neural
        return LegacyBoxFilesDetector()
    elif selected == "legacy":
        return LegacyBoxFilesDetector()
    else:
        return LegacyBoxFilesDetector()
