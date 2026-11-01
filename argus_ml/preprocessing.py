import logging
from pathlib import Path
from typing import List, Optional, Tuple, Union
import cv2
import numpy as np

logger = logging.getLogger("argus.ml.preprocessing")

DEFAULT_CCTV_SIZE = (480, 360)
DEFAULT_CONVAE_SIZE = (227, 227)
DEFAULT_WINDOW_SIZE = 30
DEFAULT_WINDOW_STRIDE = 15


def load_video_frames(
    video_path: Union[str, Path],
    max_frames: Optional[int] = None,
    target_size: Optional[Tuple[int, int]] = DEFAULT_CCTV_SIZE,
) -> List[np.ndarray]:
    """
    Load frames from a video file into a list of BGR numpy arrays.
    Optionally resizes each frame to target_size (width, height).
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video file: {path}")

    frames = []
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            if target_size:
                frame = cv2.resize(frame, target_size)
            frames.append(frame)
            if max_frames and len(frames) >= max_frames:
                break
    finally:
        cap.release()

    return frames


def create_sliding_windows(
    frames: List[np.ndarray],
    window_size: int = DEFAULT_WINDOW_SIZE,
    stride: int = DEFAULT_WINDOW_STRIDE,
) -> List[List[np.ndarray]]:
    """
    Slice a continuous frame sequence into overlapping temporal windows.
    Default: 30-frame window with 15-frame stride (50% temporal overlap).
    """
    if len(frames) < window_size:
        return [frames] if frames else []

    windows = []
    for start in range(0, len(frames) - window_size + 1, stride):
        windows.append(frames[start : start + window_size])
    return windows


def preprocess_for_convae(
    frames: List[np.ndarray],
    target_size: Tuple[int, int] = DEFAULT_CONVAE_SIZE,
    mode: str = "gray",
) -> np.ndarray:
    """
    Transform a list of frames into a normalized numpy tensor for ConvAE inference/training.
    Returns array of shape: (T, target_height, target_width) for mode='gray'
    or (T, target_height, target_width, 3) for mode='rgb'. Values in [0.0, 1.0].
    """
    processed = []
    width, height = target_size

    for f in frames:
        img = cv2.resize(f, (width, height))
        if mode == "gray":
            if len(img.shape) == 3 and img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        elif mode == "rgb":
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            elif img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        processed.append(img.astype(np.float32) / 255.0)

    return np.array(processed, dtype=np.float32)
