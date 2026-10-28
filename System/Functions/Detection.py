import logging
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np

from System.Functions.Detector import get_detector

logger = logging.getLogger("argus.detection")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Detection:
    """
    Argus Vehicle Detection Stage.
    Delegates to configured detector (legacy box files, modern YOLO, or motion fallback).
    """

    def __init__(self, yolo=None):
        self.yolo = yolo
        self.detector = get_detector()

    def detect(self, frames, frame_width, frame_height, read_file, boxes_file=None, read_file_self=False, tf=True):
        if not frames or len(frames) == 0:
            return []

        # 1. If pre-annotated dataset box files are available and legacy read is enabled
        if read_file_self and boxes_file is not None:
            return boxes_file

        # 2. Use configured modular detector
        first_frame = frames[0]
        ref_frame = frames[min(5, len(frames) - 1)] if len(frames) > 1 else None

        return self.detector.detect(
            first_frame,
            ref_frame=ref_frame,
            boxes_file=boxes_file,
            frame_width=frame_width,
            frame_height=frame_height
        )