import logging
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

from System.Functions.Detector.base import BaseDetector, DetectionBox
from System.Functions.Detector.motion import MotionFallbackDetector
from boxes.yoloFiles import loadFile

logger = logging.getLogger("argus.detector.legacy")
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BOXES_DIR = PROJECT_ROOT / "boxes"


class LegacyBoxFilesDetector(BaseDetector):
    """
    Default Argus legacy detector.
    Reads pre-annotated bounding boxes from boxes/*.txt matching the video filename or camera ID.
    If no pre-annotated box file is found, it cleanly falls back to MotionFallbackDetector.
    """

    def __init__(self):
        self._cache: Dict[str, List[List[DetectionBox]]] = {}
        self._motion_fallback = MotionFallbackDetector()

    @property
    def name(self) -> str:
        return "legacy"

    @property
    def is_low_quality(self) -> bool:
        return False

    def _get_box_file(self, video_name: str) -> Optional[Path]:
        stem = Path(video_name).stem
        candidates = [stem]
        if "_" in stem:
            candidates.append(stem.split("_", 1)[1])
            candidates.append(stem.rsplit("_", 1)[1])

        for cand in candidates:
            clean = Path(cand).stem
            candidate_path = BOXES_DIR / f"{clean}.txt"
            if candidate_path.exists():
                return candidate_path
        return None

    def detect(self, frame: np.ndarray, **kwargs) -> List[DetectionBox]:
        video_name = kwargs.get("video_name") or str(kwargs.get("camera_id", ""))
        frame_index = kwargs.get("frame_index", 0)

        # If pre-loaded boxes were passed directly (e.g. from Master / Feeder)
        boxes_file = kwargs.get("boxes_file")
        if boxes_file is not None and isinstance(boxes_file, list):
            if 0 <= frame_index < len(boxes_file):
                return boxes_file[frame_index]
            return []

        if not video_name:
            return self._motion_fallback.detect(frame, **kwargs)

        # Check cache
        if video_name not in self._cache:
            box_file = self._get_box_file(video_name)
            if box_file:
                try:
                    loaded = loadFile(box_file.stem)
                    self._cache[video_name] = loaded
                    logger.info(f"Loaded {len(loaded)} pre-annotated frames from {box_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to parse box file {box_file}: {e}")
                    self._cache[video_name] = []
            else:
                logger.warning(
                    f"No pre-annotated box file found in boxes/ for '{video_name}'. "
                    "Falling back to MotionFallbackDetector (low-quality detection mode)."
                )
                self._cache[video_name] = []

        cached_frames = self._cache.get(video_name, [])
        if cached_frames and 0 <= frame_index < len(cached_frames):
            return cached_frames[frame_index]

        # Fallback to motion detector if no boxes exist for this frame
        return self._motion_fallback.detect(frame, **kwargs)
