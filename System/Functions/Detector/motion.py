import logging
from typing import List, Optional
import cv2
import numpy as np

from System.Functions.Detector.base import BaseDetector, DetectionBox

logger = logging.getLogger("argus.detector.motion")


class MotionFallbackDetector(BaseDetector):
    """
    Naive frame-differencing motion detector.
    Used ONLY as a fallback when no pre-annotated box files or deep learning weights exist.
    Flags shadows, headlights, and noise, so a prominent warning is logged and surfaced to UI.
    """

    def __init__(self, min_area: int = 600, min_dimension: int = 25):
        self.min_area = min_area
        self.min_dimension = min_dimension
        self.prev_frame: Optional[np.ndarray] = None
        self._warned = False

    @property
    def name(self) -> str:
        return "motion"

    @property
    def is_low_quality(self) -> bool:
        return True

    def detect(self, frame: np.ndarray, **kwargs) -> List[DetectionBox]:
        if not self._warned:
            logger.warning(
                "LOW-QUALITY DETECTION MODE: MotionFallbackDetector active. "
                "Shadows, camera shaking, and lighting changes may be misidentified as vehicles."
            )
            self._warned = True

        if frame is None or frame.size == 0:
            return []

        # If secondary reference frame was passed in kwargs (e.g. from 30-frame batch)
        ref_frame = kwargs.get("ref_frame")
        if ref_frame is None:
            ref_frame = self.prev_frame

        if ref_frame is None:
            self.prev_frame = frame.copy()
            return []

        try:
            diff = cv2.absdiff(frame, ref_frame)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            boxes: List[DetectionBox] = []
            for c in contours:
                x, y, w, h = cv2.boundingRect(c)
                if w >= self.min_dimension and h >= self.min_dimension and (w * h) >= self.min_area:
                    # [class_name, xmin, xmax, ymin, ymax, score]
                    boxes.append(["car", float(x), float(x + w), float(y), float(y + h), 0.70])

            self.prev_frame = frame.copy()
            return boxes[:8]
        except Exception as e:
            logger.error(f"Error in MotionFallbackDetector: {e}")
            return []
