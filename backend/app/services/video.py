import asyncio
import os
import shutil
import tempfile
import zmq
from pathlib import Path
from typing import Optional, Tuple
import cv2

from ..config import settings, PROJECT_ROOT
from ..models.schemas import Incident
from .database import query_incident_by_id
from .media import sanitize_id

def send_req_video_to_master(camera_id: int, starting_frame_id: int, timeout_ms: int = 4000) -> bool:
    """
    Send REQ_VIDEO command to Argus Master node over ZeroMQ REQ socket.
    Master replies with empty string and asynchronously triggers video reply/save.
    """
    context = zmq.Context.instance()
    socket = context.socket(zmq.REQ)
    socket.RCVTIMEO = timeout_ms
    socket.SNDTIMEO = timeout_ms
    link = f"tcp://{settings.ZMQ_HOST}:{settings.ZMQ_MASTER_PORT}"
    try:
        socket.connect(link)
        msg = {
            "FUNCTION": "REQ_VIDEO",
            "CAMERA_ID": camera_id,
            "STARTING_FRAME_ID": starting_frame_id,
        }
        socket.send_pyobj(msg)
        socket.recv_pyobj()
        return True
    except Exception:
        return False
    finally:
        socket.close()

async def transcode_avi_to_mp4(avi_path: Path, mp4_path: Path) -> bool:
    """
    Transcode Motion-JPEG AVI into web-compatible H.264 MP4 with yuv420p and faststart.
    Transcodes to a temporary file first, then atomically replaces the destination.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg binary not found on system path")

    mp4_path.parent.mkdir(parents=True, exist_ok=True)
    temp_mp4 = mp4_path.with_suffix(".tmp.mp4")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(avi_path),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(temp_mp4),
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        if temp_mp4.exists():
            temp_mp4.unlink()
        err_msg = stderr.decode() if stderr else "Unknown ffmpeg error"
        raise RuntimeError(f"FFmpeg transcoding failed (code {process.returncode}): {err_msg}")

    temp_mp4.replace(mp4_path)
    return True

async def get_or_create_incident_mp4(identifier: str) -> Path:
    """
    Retrieve or transcode H.264 MP4 for given incident.
    1. Returns cached .mp4 if already present.
    2. Locates raw AVI clip on disk in saved_crash_vid/ or saved_frames_vid/.
    3. If missing, sends REQ_VIDEO to Master and polls briefly for file creation.
    4. Transcodes AVI to MP4, caches it, and returns the Path.
    """
    safe_id = sanitize_id(identifier)
    cached_mp4 = settings.VIDEO_CACHE_DIR / f"{safe_id}.mp4"

    if cached_mp4.exists() and cached_mp4.stat().st_size > 0:
        return cached_mp4

    incident = query_incident_by_id(safe_id)
    if not incident:
        # Check if raw clip exists on disk even if not in DB
        if "_" in safe_id:
            cam, frm = safe_id.split("_", 1)
            clip_name = f"({cam}) {frm}.avi"
            raw_clip = settings.SAVED_CRASH_VID_DIR / clip_name
            if not raw_clip.exists():
                raw_clip = settings.SAVED_FRAMES_VID_DIR / clip_name
            if raw_clip.exists():
                await transcode_avi_to_mp4(raw_clip, cached_mp4)
                return cached_mp4
        raise FileNotFoundError(f"Incident '{safe_id}' not found in database")

    cache_key = f"{incident.camera_id}_{incident.starting_frame_id}"
    cached_mp4 = settings.VIDEO_CACHE_DIR / f"{cache_key}.mp4"

    if cached_mp4.exists() and cached_mp4.stat().st_size > 0:
        return cached_mp4

    # Check for raw clip on disk
    clip_filename = f"({incident.camera_id}) {incident.starting_frame_id}.avi"
    avi_path = settings.SAVED_CRASH_VID_DIR / clip_filename
    if not avi_path.exists():
        avi_path = settings.SAVED_FRAMES_VID_DIR / clip_filename

    if not avi_path.exists():
        # Ask master to retrieve/stitch video
        sent = await asyncio.to_thread(
            send_req_video_to_master,
            incident.camera_id,
            incident.starting_frame_id,
            3000
        )
        # Wait up to 3 seconds for file to be ready
        for _ in range(6):
            await asyncio.sleep(0.5)
            if avi_path.exists():
                break

    if avi_path.exists():
        # Transcode to H.264 MP4
        await transcode_avi_to_mp4(avi_path, cached_mp4)
        return cached_mp4

    raise FileNotFoundError(
        f"Stitched incident clip '{clip_filename}' could not be located on disk or retrieved from Argus Master"
    )

def parse_range_header(range_header: str, file_size: int) -> Tuple[int, int]:
    """Parse HTTP Range header 'bytes=start-end' returning (start, end)."""
    try:
        range_val = range_header.strip().lower()
        if not range_val.startswith("bytes="):
            return 0, file_size - 1

        parts = range_val[6:].split("-")
        start_str = parts[0].strip()
        end_str = parts[1].strip() if len(parts) > 1 else ""

        if start_str and end_str:
            start = int(start_str)
            end = int(end_str)
        elif start_str:
            start = int(start_str)
            end = file_size - 1
        elif end_str:
            # Suffix byte range
            length = int(end_str)
            start = max(0, file_size - length)
            end = file_size - 1
        else:
            return 0, file_size - 1

        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        return start, end
    except Exception:
        return 0, file_size - 1
