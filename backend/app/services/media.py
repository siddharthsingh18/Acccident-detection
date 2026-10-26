import re
from pathlib import Path
from typing import Optional
import cv2
from ..config import settings
from .database import query_incident_by_id

SAFE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")

def sanitize_id(identifier: str) -> str:
    """Validate and sanitize ID to prevent path traversal."""
    identifier = identifier.strip()
    if not SAFE_ID_REGEX.match(identifier):
        raise ValueError("Invalid identifier format: must contain only alphanumeric, underscores, or dashes")
    return identifier

def extract_thumbnail_from_video(video_path: Path, output_path: Path) -> bool:
    """Extract frame 89 (or latest available frame) from an AVI video and save as JPG."""
    if not video_path.exists():
        return False
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return False

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            return False

        target_frame = min(89, total_frames - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), frame)
            return True
        return False
    except Exception:
        return False

def get_thumbnail_file(identifier: str) -> Path:
    """
    Get path to thumbnail JPG file for an incident.
    1. Returns cached thumbnail if exists.
    2. Tries to extract from saved AVI video clip on disk.
    3. Falls back to fallback image (UI/notfound.png).
    """
    safe_id = sanitize_id(identifier)
    cached_path = settings.THUMBNAILS_DIR / f"{safe_id}.jpg"

    if cached_path.exists() and cached_path.stat().st_size > 0:
        return cached_path

    # Attempt to extract from raw clip
    incident = query_incident_by_id(safe_id)
    if incident:
        clip_name = f"({incident.camera_id}) {incident.starting_frame_id}.avi"
        clip_path = settings.SAVED_CRASH_VID_DIR / clip_name
        if extract_thumbnail_from_video(clip_path, cached_path):
            return cached_path

    # Fallback to default Argus missing image
    if settings.FALLBACK_IMAGE_PATH.exists():
        return settings.FALLBACK_IMAGE_PATH

    return cached_path
