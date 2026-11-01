import asyncio
import json
import logging
import os
import shutil
import subprocess
import uuid
import zmq
from pathlib import Path
from typing import Dict, Optional, Tuple
from fastapi import HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from ..config import settings, PROJECT_ROOT
from ..models.schemas import Incident
from .database import query_incident_by_id
from .media import sanitize_id

logger = logging.getLogger("argus.services.video")

# Per-clip mutex dictionary to prevent concurrent transcode collisions
_CLIP_LOCKS: Dict[str, asyncio.Lock] = {}

def _get_clip_lock(path: Path) -> asyncio.Lock:
    key = str(path.resolve())
    if key not in _CLIP_LOCKS:
        _CLIP_LOCKS[key] = asyncio.Lock()
    return _CLIP_LOCKS[key]

def send_req_video_to_master(camera_id: int, starting_frame_id: int, timeout_ms: int = 4000) -> bool:
    """
    Send REQ_VIDEO command to Argus Master node over ZeroMQ REQ socket.
    Master replies with empty string and asynchronously triggers video reply/save.
    """
    context = zmq.Context.instance()
    socket = context.socket(zmq.REQ)
    socket.RCVTIMEO = timeout_ms
    socket.SNDTIMEO = timeout_ms
    link = f"tcp://{settings.ZMQ_MASTER_HOST}:{settings.ZMQ_MASTER_PORT}"
    try:
        from System.Connections.protocol import serialize_message
        socket.connect(link)
        msg = {
            "FUNCTION": "REQ_VIDEO",
            "CAMERA_ID": camera_id,
            "STARTING_FRAME_ID": starting_frame_id,
        }
        socket.send_multipart(serialize_message(msg))
        socket.recv_multipart()
        return True
    except Exception as e:
        logger.debug(f"Failed to request video from master: {e}")
        return False
    finally:
        socket.close()

def validate_video_file(file_path: Path) -> dict:
    """
    Probe a video file with ffprobe to verify validity and extract stream info.
    Raises HTTPException(503) if ffprobe is missing.
    Raises HTTPException(422) if file is corrupt or unreadable.
    """
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        raise HTTPException(
            status_code=503,
            detail={"code": "FFPROBE_UNAVAILABLE", "message": "ffprobe binary not found on system path"}
        )

    if not file_path.exists() or file_path.stat().st_size == 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "CORRUPT_VIDEO", "message": f"Video file is empty or missing: {file_path.name}"}
        )

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "stream=codec_name,codec_type,width,height,pix_fmt",
        "-show_entries", "format=format_name,size,duration",
        "-of", "json",
        str(file_path),
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
        if res.returncode != 0:
            err = res.stderr.strip() if res.stderr else "ffprobe probe failed"
            logger.warning(f"ffprobe validation failed for {file_path.name}: {err}")
            raise HTTPException(
                status_code=422,
                detail={"code": "CORRUPT_VIDEO", "message": f"Video validation failed: {err}"}
            )

        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        if not video_streams:
            raise HTTPException(
                status_code=422,
                detail={"code": "NO_VIDEO_STREAM", "message": "No valid video stream found in file"}
            )

        return {
            "format": data.get("format", {}),
            "video_stream": video_streams[0],
            "has_audio": len(audio_streams) > 0,
        }
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=422,
            detail={"code": "CORRUPT_VIDEO", "message": "ffprobe timed out reading video"}
        )
    except Exception as e:
        logger.warning(f"Unexpected error validating video {file_path}: {e}")
        raise HTTPException(
            status_code=422,
            detail={"code": "CORRUPT_VIDEO", "message": f"Unable to validate video file: {str(e)}"}
        )

def is_valid_h264_mp4(mp4_path: Path, min_mtime: float = 0.0) -> bool:
    """
    Check if a file exists, has size > 0, was modified at or after min_mtime,
    and contains a valid H.264 stream inside an MP4 container.
    """
    if not mp4_path.exists() or mp4_path.stat().st_size == 0:
        return False

    if min_mtime > 0 and mp4_path.stat().st_mtime < min_mtime:
        return False

    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        return mp4_path.stat().st_size > 0

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,pix_fmt",
        "-show_entries", "format=format_name",
        "-of", "json",
        str(mp4_path),
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if res.returncode != 0:
            return False
        data = json.loads(res.stdout)
        fmt = data.get("format", {}).get("format_name", "")
        streams = data.get("streams", [])
        if not streams or "mp4" not in fmt:
            return False
        codec = streams[0].get("codec_name")
        return codec == "h264"
    except Exception:
        return False

async def transcode_to_web_mp4(source_path: Path, target_mp4_path: Path) -> Path:
    """
    Transcode source video into web-compatible H.264 MP4 with yuv420p, even dimensions,
    and faststart enabled. Thread-safe with per-clip locking, unique temp files,
    atomic replacement, and stderr error logging.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise HTTPException(
            status_code=503,
            detail={"code": "TRANSCODER_UNAVAILABLE", "message": "ffmpeg binary not found on system path"}
        )

    if not source_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "VIDEO_NOT_FOUND", "message": f"Source video not found: {source_path.name}"}
        )

    target_mp4_path.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_clip_lock(target_mp4_path)

    async with lock:
        source_mtime = source_path.stat().st_mtime
        if is_valid_h264_mp4(target_mp4_path, min_mtime=source_mtime):
            return target_mp4_path

        # Validate source video
        probe_info = await asyncio.to_thread(validate_video_file, source_path)
        has_audio = probe_info.get("has_audio", False)

        # Unique temporary file in the same directory for atomic rename
        temp_id = f".tmp_{os.getpid()}_{uuid.uuid4().hex[:8]}_{target_mp4_path.name}"
        temp_mp4 = target_mp4_path.parent / temp_id

        # libx264 command with even dimensions padding and faststart
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(source_path),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ]
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.append("-an")

        cmd.append(str(temp_mp4))

        logger.info(f"Transcoding {source_path.name} -> {target_mp4_path.name}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            if temp_mp4.exists():
                try:
                    temp_mp4.unlink()
                except Exception:
                    pass
            err_msg = stderr.decode(errors="replace").strip() if stderr else "Unknown ffmpeg error"
            logger.error(f"FFmpeg transcoding failed (code {process.returncode}) for {source_path.name}: {err_msg[-400:]}")
            raise HTTPException(
                status_code=422,
                detail={"code": "TRANSCODING_FAILED", "message": f"FFmpeg transcoding failed: {err_msg[-200:]}"}
            )

        # Atomically replace destination file
        temp_mp4.replace(target_mp4_path)
        return target_mp4_path

# Backward compatibility alias
async def transcode_avi_to_mp4(avi_path: Path, mp4_path: Path) -> bool:
    await transcode_to_web_mp4(avi_path, mp4_path)
    return True

async def get_or_create_incident_mp4(identifier: str) -> Path:
    """
    Retrieve or transcode H.264 MP4 for a given incident identifier.
    1. Sanitizes identifier (supports '1566_151', '(1566) 151', '(1566) 151.avi').
    2. Returns valid cached MP4 if already present.
    3. Locates raw AVI clip on disk in saved_crash_vid/ or saved_frames_vid/.
    4. If missing, sends REQ_VIDEO to Master and polls for file creation.
    5. Transcodes to H.264 MP4 with concurrency safety and returns Path.
    """
    safe_id = sanitize_id(identifier)
    cached_mp4 = settings.VIDEO_CACHE_DIR / f"{safe_id}.mp4"

    if is_valid_h264_mp4(cached_mp4):
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
                return await transcode_to_web_mp4(raw_clip, cached_mp4)
        raise FileNotFoundError(f"Incident '{safe_id}' not found in database or disk records")

    cache_key = f"{incident.camera_id}_{incident.starting_frame_id}"
    cached_mp4 = settings.VIDEO_CACHE_DIR / f"{cache_key}.mp4"

    if is_valid_h264_mp4(cached_mp4):
        return cached_mp4

    # Check for raw clip on disk
    clip_filename = f"({incident.camera_id}) {incident.starting_frame_id}.avi"
    avi_path = settings.SAVED_CRASH_VID_DIR / clip_filename
    if not avi_path.exists():
        avi_path = settings.SAVED_FRAMES_VID_DIR / clip_filename

    if not avi_path.exists():
        # Ask master to retrieve/stitch video
        await asyncio.to_thread(
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
        return await transcode_to_web_mp4(avi_path, cached_mp4)

    raise FileNotFoundError(
        f"Stitched incident clip '{clip_filename}' could not be located on disk or retrieved from Argus Master"
    )

def parse_range_header(range_header: Optional[str], file_size: int) -> Tuple[Optional[int], Optional[int], bool]:
    """
    Parse HTTP Range header 'bytes=start-end', 'bytes=start-', 'bytes=-suffix'.
    Returns (start, end, is_valid).
    - If range_header is None or not bytes, returns (None, None, True) signifying full file (200).
    - If range is invalid or unsatisfiable, returns (None, None, False) signifying 416.
    - Otherwise returns (start, end, True) for 206 Partial Content.
    """
    if not range_header or not range_header.strip().lower().startswith("bytes="):
        return None, None, True

    val = range_header.strip()[6:].strip()
    if not val:
        return None, None, False

    # Take first range if comma-separated
    if "," in val:
        val = val.split(",", 1)[0].strip()

    parts = val.split("-")
    if len(parts) != 2:
        return None, None, False

    start_str, end_str = parts[0].strip(), parts[1].strip()

    if start_str and end_str:
        try:
            start = int(start_str)
            end = int(end_str)
        except ValueError:
            return None, None, False
        if start < 0 or start > end or start >= file_size:
            return None, None, False
        end = min(end, file_size - 1)
        return start, end, True
    elif start_str:
        try:
            start = int(start_str)
        except ValueError:
            return None, None, False
        if start < 0 or start >= file_size:
            return None, None, False
        return start, file_size - 1, True
    elif end_str:
        try:
            suffix_len = int(end_str)
        except ValueError:
            return None, None, False
        if suffix_len <= 0:
            return None, None, False
        start = max(0, file_size - suffix_len)
        return start, file_size - 1, True

    return None, None, False

def stream_video_response(video_path: Path, request: Request) -> Response:
    """
    Build HTTP response for HTML5 video streaming:
    - 200 OK with Content-Length and Accept-Ranges for HEAD requests
    - 416 Range Not Satisfiable when range is invalid
    - 206 Partial Content with proper Content-Range and chunked stream
    - 200 OK with FileResponse for full GET requests
    """
    file_size = video_path.stat().st_size

    if request.method == "HEAD":
        return Response(
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Type": "video/mp4",
            }
        )

    range_header = request.headers.get("range")
    start, end, is_valid = parse_range_header(range_header, file_size)

    if not is_valid:
        return Response(
            status_code=416,
            headers={
                "Content-Range": f"bytes */{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Type": "video/mp4",
            }
        )

    if start is not None and end is not None:
        content_length = (end - start) + 1

        def iterfile():
            with open(video_path, "rb") as f:
                f.seek(start)
                bytes_left = content_length
                chunk_size = 64 * 1024
                while bytes_left > 0:
                    read_len = min(chunk_size, bytes_left)
                    data = f.read(read_len)
                    if not data:
                        break
                    bytes_left -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": "video/mp4",
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)

    return FileResponse(
        video_path,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )
