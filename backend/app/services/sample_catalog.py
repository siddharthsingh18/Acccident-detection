import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import cv2
from fastapi import HTTPException

from ..config import settings, PROJECT_ROOT
from ..models.schemas import SampleItemResponse

logger = logging.getLogger("argus.services.sample_catalog")

_METADATA_CACHE: Dict[str, dict] = {}
_METADATA_CACHE_FILE = settings.SAMPLE_CACHE_DIR / "metadata_cache.json"

def get_sample_dirs() -> List[Path]:
    """Return resolved directories configured for sample discovery."""
    dirs: List[Path] = []
    for d_str in settings.SAMPLE_DIRS:
        p = Path(d_str)
        if not p.is_absolute():
            p = (PROJECT_ROOT / p).resolve()
        else:
            p = p.resolve()
        if p.exists() and p.is_dir():
            dirs.append(p)
    return dirs

def load_manifest() -> Dict[str, dict]:
    """Load videos/manifest.json if present."""
    manifest_path = settings.SAMPLE_MANIFEST_PATH
    if not manifest_path.exists():
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.warning(f"Failed to read sample manifest from {manifest_path}: {e}")
    return {}

def make_stable_id(rel_path: Path) -> str:
    """Generate a stable, URL-safe ID from a project-relative path."""
    posix_str = rel_path.as_posix().strip("/")
    # Replace slashes with double-hyphens for clean, reversible URL safety
    return posix_str.replace("/", "--")

def parse_stable_id(sample_id: str) -> str:
    """Convert a stable ID back into its relative path representation."""
    if "--" in sample_id:
        return sample_id.replace("--", "/")
    return sample_id

def resolve_expected_label(file_path: Path, rel_path_str: str, manifest: Dict[str, dict]) -> Tuple[str, Optional[str]]:
    """
    Resolve expected label with strict precedence:
    1. Explicit manifest entry (keyed by rel_path, filename, or stem).
    2. Inferred from dataset/Accidents directory -> 'accident'.
    3. Inferred from dataset/No_Accidents directory -> 'normal'.
    4. Otherwise -> 'unknown'.
    """
    # 1. Manifest lookup
    keys_to_check = [rel_path_str, file_path.name, file_path.stem]
    for k in keys_to_check:
        if k in manifest:
            entry = manifest[k]
            if isinstance(entry, dict):
                lbl = entry.get("label", "unknown").lower()
                notes = entry.get("notes")
                if lbl in ("accident", "normal", "unknown"):
                    return lbl, notes

    # 2. Inferred from directory
    parts = set(file_path.parts)
    if "dataset" in parts and "Accidents" in parts and "No_Accidents" not in parts:
        return "accident", "Inferred from dataset/Accidents directory"
    if "dataset" in parts and "No_Accidents" in parts:
        return "normal", "Inferred from dataset/No_Accidents directory"

    return "unknown", None

def _load_metadata_cache():
    global _METADATA_CACHE
    if _METADATA_CACHE:
        return
    if _METADATA_CACHE_FILE.exists():
        try:
            with open(_METADATA_CACHE_FILE, "r", encoding="utf-8") as f:
                _METADATA_CACHE = json.load(f)
        except Exception:
            _METADATA_CACHE = {}

def _save_metadata_cache():
    try:
        settings.SAMPLE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_METADATA_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_METADATA_CACHE, f, indent=2)
    except Exception as e:
        logger.debug(f"Failed to persist metadata cache: {e}")

def get_video_metadata(file_path: Path, rel_path_str: str) -> dict:
    """
    Run ffprobe to extract duration, resolution, and fps.
    Cached on disk with mtime/size invalidation.
    Never crashes on corrupt files; logs warning and returns None fields.
    """
    _load_metadata_cache()
    try:
        st = file_path.stat()
        cache_key = f"{rel_path_str}:{st.st_size}:{st.st_mtime_ns}"
    except Exception:
        return {"duration_s": None, "resolution": None, "fps": None}

    if cache_key in _METADATA_CACHE:
        return _METADATA_CACHE[cache_key]

    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,duration:format=duration",
        "-of", "json",
        str(file_path)
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if res.returncode != 0:
            logger.warning(f"ffprobe failed for {file_path.name}: {res.stderr.strip()}")
            result = {"duration_s": None, "resolution": None, "fps": None}
            _METADATA_CACHE[cache_key] = result
            _save_metadata_cache()
            return result

        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {})

        duration: Optional[float] = None
        resolution: Optional[str] = None
        fps: Optional[float] = None

        # Duration
        dur_str = fmt.get("duration")
        if not dur_str and streams:
            dur_str = streams[0].get("duration")
        if dur_str:
            try:
                duration = round(float(dur_str), 2)
            except (ValueError, TypeError):
                duration = None

        # Resolution & FPS from video stream
        if streams:
            s0 = streams[0]
            w = s0.get("width")
            h = s0.get("height")
            if w and h:
                resolution = f"{w}x{h}"

            r_fps = s0.get("r_frame_rate")
            if r_fps and "/" in r_fps:
                try:
                    num, den = r_fps.split("/")
                    fps_val = float(num) / float(den)
                    fps = round(fps_val, 2)
                except Exception:
                    fps = None

        result = {
            "duration_s": duration,
            "resolution": resolution,
            "fps": fps
        }
        _METADATA_CACHE[cache_key] = result
        _save_metadata_cache()
        return result

    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timed out on {file_path}")
        return {"duration_s": None, "resolution": None, "fps": None}
    except Exception as e:
        logger.warning(f"ffprobe metadata extraction failed on {file_path}: {e}")
        return {"duration_s": None, "resolution": None, "fps": None}

def get_or_create_thumbnail(file_path: Path, sample_id: str) -> Path:
    """
    Extract first/middle frame and cache on disk under gitignored artifacts directory.
    Falls back to OpenCV or fallback image if extraction fails.
    """
    settings.SAMPLE_THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitize sample_id for filename
    safe_name = sample_id.replace("/", "--").replace("..", "").replace(" ", "_")
    thumb_path = settings.SAMPLE_THUMBNAILS_DIR / f"{safe_name}.jpg"

    if thumb_path.exists() and thumb_path.stat().st_size > 0:
        return thumb_path

    # Try ffmpeg extraction at t=1s (or 0s)
    cmd = [
        "ffmpeg",
        "-v", "error",
        "-ss", "0.5",
        "-i", str(file_path),
        "-vframes", "1",
        "-q:v", "3",
        str(thumb_path),
        "-y"
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        if res.returncode == 0 and thumb_path.exists() and thumb_path.stat().st_size > 0:
            return thumb_path
    except Exception as e:
        logger.debug(f"ffmpeg thumbnail extraction failed for {file_path}: {e}")

    # Fallback: OpenCV VideoCapture
    try:
        cap = cv2.VideoCapture(str(file_path))
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            cv2.imwrite(str(thumb_path), frame)
            return thumb_path
    except Exception as e:
        logger.debug(f"OpenCV thumbnail extraction failed for {file_path}: {e}")

    # Ultimate fallback: system fallback image
    return settings.FALLBACK_IMAGE_PATH

def resolve_sample_path(sample_id: str) -> Path:
    """
    Strict security path resolution:
    - Rejects path traversal attempts ('..', leading slashes, absolute paths).
    - Ensures resolved canonical path is strictly contained within configured SAMPLE_DIRS.
    - Ensures file exists and has an allowed video extension.
    """
    if ".." in sample_id or sample_id.startswith("/") or sample_id.startswith("\\"):
        raise HTTPException(status_code=400, detail="Invalid sample ID: path traversal is forbidden.")

    # Reconstruct relative path candidate
    rel_path_cand = parse_stable_id(sample_id)
    if ".." in rel_path_cand or rel_path_cand.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid sample ID: path traversal is forbidden.")

    allowed_dirs = get_sample_dirs()

    # Strategy 1: Direct match relative to PROJECT_ROOT
    cand1 = (PROJECT_ROOT / rel_path_cand).resolve()
    if cand1.exists() and cand1.is_file():
        if any(sample_dir in cand1.parents for sample_dir in allowed_dirs):
            if cand1.suffix.lower() in settings.ALLOWED_EXTENSIONS:
                return cand1

    # Strategy 2: Match within any configured sample directory
    for s_dir in allowed_dirs:
        cand2 = (s_dir / rel_path_cand).resolve()
        if cand2.exists() and cand2.is_file():
            if s_dir in cand2.parents or s_dir == cand2.parent:
                if cand2.suffix.lower() in settings.ALLOWED_EXTENSIONS:
                    return cand2

    # Strategy 3: Match by filename or stem across allowed sample directories
    filename_target = Path(rel_path_cand).name
    for s_dir in allowed_dirs:
        for f in s_dir.rglob(filename_target):
            if f.is_file() and f.suffix.lower() in settings.ALLOWED_EXTENSIONS:
                cand3 = f.resolve()
                if any(s in cand3.parents for s in allowed_dirs):
                    return cand3

    raise HTTPException(status_code=404, detail=f"Sample video '{sample_id}' not found.")

def list_samples() -> List[SampleItemResponse]:
    """
    Scan all configured sample directories recursively for video files.
    Enrich with stable IDs, ffprobe metadata, expected labels, and thumbnail URLs.
    """
    allowed_dirs = get_sample_dirs()
    manifest = load_manifest()
    samples: List[SampleItemResponse] = []
    seen_paths = set()

    # Pre-populate suggested camera/city/district from legacy catalog if available
    legacy_suggestions: Dict[str, dict] = {
        "1528": {"camera_id": 1528, "city": "Shibin El Kom", "district": "District 13"},
        "1506": {"camera_id": 1506, "city": "Asyut", "district": "District 16"},
        "1513": {"camera_id": 1513, "city": "Aswan", "district": "District 21"},
        "1543": {"camera_id": 1543, "city": "Asyut", "district": "District 10"},
        "1508": {"camera_id": 1508, "city": "Fayyum", "district": "District 26"},
        "1516": {"camera_id": 1516, "city": "Shubra El-Kheima", "district": "District 27"},
        "1518": {"camera_id": 1518, "city": "Shubra El-Kheima", "district": "District 25"},
        "1519": {"camera_id": 1519, "city": "Qalyub", "district": "District 22"},
        "1521": {"camera_id": 1521, "city": "Qena", "district": "District 2"},
        "1522": {"camera_id": 1522, "city": "Marsa Matruh", "district": "District 6"},
        "1529": {"camera_id": 1529, "city": "Bilbais", "district": "District 29"},
        "1533": {"camera_id": 1533, "city": "Cairo", "district": "District 18"},
        "1534": {"camera_id": 1534, "city": "Ismailia", "district": "District 27"},
        "1548": {"camera_id": 1548, "city": "Luxor", "district": "District 14"},
        "1566": {"camera_id": 1566, "city": "Hurghada", "district": "District 16"},
        "1600": {"camera_id": 1600, "city": "Cairo", "district": "District 5"},
        "1601": {"camera_id": 1601, "city": "Cairo", "district": "District 5"},
        "1602": {"camera_id": 1602, "city": "Cairo", "district": "District 5"},
        "1701": {"camera_id": 1701, "city": "Giza", "district": "District 3"},
    }

    for s_dir in allowed_dirs:
        for file_path in sorted(s_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in settings.ALLOWED_EXTENSIONS:
                continue

            resolved_path = file_path.resolve()
            if resolved_path in seen_paths:
                continue
            seen_paths.add(resolved_path)

            try:
                rel_path = resolved_path.relative_to(PROJECT_ROOT)
            except ValueError:
                # If outside project root, relative to s_dir
                rel_path = resolved_path.relative_to(s_dir)

            rel_path_str = rel_path.as_posix()
            stable_id = make_stable_id(rel_path)
            meta = get_video_metadata(resolved_path, rel_path_str)
            label, notes = resolve_expected_label(resolved_path, rel_path_str, manifest)

            # Derive default suggested camera ID if numeric
            suggested_cam_id: Optional[int] = None
            suggested_city: Optional[str] = None
            suggested_district: Optional[str] = None

            stem = resolved_path.stem
            if stem in legacy_suggestions:
                sug = legacy_suggestions[stem]
                suggested_cam_id = sug["camera_id"]
                suggested_city = sug["city"]
                suggested_district = sug["district"]
            elif stem.isdigit():
                try:
                    suggested_cam_id = int(stem)
                except ValueError:
                    suggested_cam_id = None

            item = SampleItemResponse(
                id=stable_id,
                name=resolved_path.name,
                relative_path=rel_path_str,
                size_bytes=resolved_path.stat().st_size,
                duration_s=meta.get("duration_s"),
                resolution=meta.get("resolution"),
                fps=meta.get("fps"),
                thumbnail_url=f"/api/samples/{stable_id}/thumbnail",
                video_url=f"/api/samples/{stable_id}/video",
                expected_label=label,  # type: ignore[arg-type]
                camera_id=suggested_cam_id,
                city=suggested_city,
                district=suggested_district,
                notes=notes
            )
            samples.append(item)

    # Sort stably by relative_path
    samples.sort(key=lambda s: s.relative_path)
    return samples

async def get_or_create_sample_mp4(sample_id: str) -> Path:
    """
    Retrieve or transcode H.264 MP4 for a requested sample.
    If the source video is already a valid H.264 MP4 with faststart, returns it directly.
    Otherwise, transcodes to artifacts/cache/samples/transcoded/<safe_id>.mp4.
    """
    from .video import transcode_to_web_mp4, is_valid_h264_mp4
    video_path = resolve_sample_path(sample_id)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Sample video '{sample_id}' not found.")

    # If source is already valid web-compatible H.264 MP4, serve directly
    if video_path.suffix.lower() == ".mp4" and is_valid_h264_mp4(video_path):
        return video_path

    transcode_dir = settings.SAMPLE_CACHE_DIR / "transcoded"
    transcode_dir.mkdir(parents=True, exist_ok=True)
    safe_name = sample_id.replace("/", "--").replace("..", "").replace(" ", "_")
    if not safe_name.lower().endswith(".mp4"):
        safe_name = f"{safe_name}.mp4"
    target_mp4 = transcode_dir / safe_name

    return await transcode_to_web_mp4(video_path, target_mp4)

