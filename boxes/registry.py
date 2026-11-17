"""
Content-addressed registry mapping video content hashes to pre-annotated bounding box files.

Decouples vehicle box lookup from camera IDs or filenames so unrelated uploads
(e.g. uploaded video with camera_id=1528) never accidentally load collision annotations.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "boxes" / "registry.json"
DEFAULT_BOXES_DIR = PROJECT_ROOT / "boxes"
HASH_CHUNK_SIZE_BYTES = 1024 * 1024  # 1 MB


def compute_video_hash(video_path: Union[str, Path], max_bytes: int = HASH_CHUNK_SIZE_BYTES) -> str:
    """
    Compute a fast content hash (SHA-256 of the first 1 MB) for video identification.
    """
    p = Path(video_path)
    if not p.is_file():
        raise FileNotFoundError(f"Video file not found for hashing: {video_path}")

    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        chunk = f.read(max_bytes)
        hasher.update(chunk)
    return hasher.hexdigest()


_REGISTRY_CACHE: Dict[str, Any] = {}
_REGISTRY_MTIME: float = 0.0


def load_box_registry(registry_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load boxes/registry.json into memory with mtime-based reload caching.
    """
    global _REGISTRY_CACHE, _REGISTRY_MTIME

    reg_path = Path(registry_path) if registry_path else DEFAULT_REGISTRY_PATH
    if not reg_path.is_file():
        return {}

    try:
        current_mtime = reg_path.stat().st_mtime
        if _REGISTRY_CACHE and current_mtime == _REGISTRY_MTIME:
            return _REGISTRY_CACHE

        with open(reg_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        _REGISTRY_CACHE = data if isinstance(data, dict) else {}
        _REGISTRY_MTIME = current_mtime
        return _REGISTRY_CACHE
    except Exception as e:
        logger.warning(f"Failed to read box registry from {reg_path}: {e}")
        return {}


def lookup_box_file(
    video_path: Union[str, Path],
    registry_path: Optional[Union[str, Path]] = None,
    boxes_dir: Optional[Union[str, Path]] = None
) -> Optional[Path]:
    """
    Look up the ground-truth box file for a video strictly via content hash.
    Does NOT use camera ID, preventing accidental collisions with uploaded clips.

    Returns:
        Path to the matching box file if registered and existing on disk, else None.
    """
    vpath = Path(video_path)
    if not vpath.is_file():
        return None

    try:
        video_hash = compute_video_hash(vpath)
    except Exception as e:
        logger.warning(f"Could not hash video {vpath}: {e}")
        return None

    registry = load_box_registry(registry_path)
    entries = registry.get("entries", registry)

    entry = entries.get(video_hash)
    if not entry:
        return None

    box_rel = entry.get("box_file") if isinstance(entry, dict) else str(entry)
    if not box_rel:
        return None

    b_dir = Path(boxes_dir) if boxes_dir else DEFAULT_BOXES_DIR
    resolved_box = (PROJECT_ROOT / box_rel).resolve() if not Path(box_rel).is_absolute() else Path(box_rel)

    if resolved_box.is_file():
        return resolved_box

    # Fallback to direct filename inside boxes_dir
    alt_box = (b_dir / Path(box_rel).name).resolve()
    if alt_box.is_file():
        return alt_box

    return None


def build_box_registry(
    search_dirs: Optional[Sequence[Path]] = None,
    boxes_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Scan known video directories, compute content hashes, and generate boxes/registry.json.
    """
    b_dir = boxes_dir or DEFAULT_BOXES_DIR
    out_file = output_path or DEFAULT_REGISTRY_PATH
    s_dirs = search_dirs or [
        PROJECT_ROOT / "videos",
        PROJECT_ROOT / "videos" / "Extra",
        PROJECT_ROOT / "Joiner" / "vids",
    ]

    entries: Dict[str, Dict[str, str]] = {}

    for directory in s_dirs:
        if not directory.is_dir():
            continue
        for vpath in directory.glob("*.mp4"):
            stem = vpath.stem
            box_candidate = b_dir / f"{stem}.txt"
            if box_candidate.is_file():
                try:
                    v_hash = compute_video_hash(vpath)
                    entries[v_hash] = {
                        "box_file": f"boxes/{box_candidate.name}",
                        "box_stem": stem,
                        "video_name": vpath.name,
                        "relative_path": str(vpath.relative_to(PROJECT_ROOT)),
                    }
                except Exception as e:
                    logger.warning(f"Error indexing {vpath}: {e}")

    registry_data = {
        "version": 1,
        "algorithm": "sha256_1mb",
        "description": "Content-addressed registry mapping video content hashes to bounding box files",
        "total_entries": len(entries),
        "entries": entries,
    }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, indent=2)

    logger.info(f"Generated {out_file} with {len(entries)} indexed video hashes.")
    return registry_data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_box_registry()

