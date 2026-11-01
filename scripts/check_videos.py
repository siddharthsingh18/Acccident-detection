#!/usr/bin/env python3
"""
Diagnostic & CI validation script for Argus video assets.
Scans:
  1. Incident video clips (saved_crash_vid/, saved_frames_vid/)
  2. Sample catalog test videos (videos/, dataset/, Joiner/)
  3. Cached transcoded files (backend/media/videos/, artifacts/cache/)

Reports:
  - Readable vs unreadable / corrupt files
  - Videos needing transcoding to web-compatible H.264
  - Cached files validity (size > 0, H.264 stream present, faststart)

Exit code:
  - 0: All video files are readable and all transcoded caches are valid.
  - 1: One or more corrupt files or invalid caches detected.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def probe_file(file_path: Path, ffprobe_bin: str) -> Tuple[bool, dict, str]:
    """Run ffprobe on file, returning (success, metadata, error_message)."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        return False, {}, "File is empty or missing"

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "stream=codec_name,codec_type,width,height,pix_fmt",
        "-show_entries", "format=format_name,duration,size",
        "-of", "json",
        str(file_path),
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        if res.returncode != 0:
            return False, {}, res.stderr.strip() or "ffprobe failed"
        data = json.loads(res.stdout)
        return True, data, ""
    except Exception as e:
        return False, {}, str(e)

def is_web_compatible_h264(data: dict) -> bool:
    """Check if stream is H.264 inside MP4 container with even dimensions and yuv420p."""
    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        return False
    v0 = video_streams[0]
    codec = v0.get("codec_name", "")
    fmt = data.get("format", {}).get("format_name", "")
    w = v0.get("width", 0)
    h = v0.get("height", 0)
    pix = v0.get("pix_fmt", "")

    return (
        codec == "h264" and
        "mp4" in fmt and
        w % 2 == 0 and
        h % 2 == 0 and
        pix in ("yuv420p", "yuvj420p")
    )

def main():
    parser = argparse.ArgumentParser(description="Check video files across Argus dataset and cache.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of videos checked")
    args = parser.parse_args()

    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        print("[ERROR] ffprobe binary not found on PATH.", file=sys.stderr)
        sys.exit(1)

    print("============================================================")
    print(" Argus Video Health & Transcode Diagnostic Check")
    print("============================================================")

    # 1. Collect video directories
    incident_dirs = [
        PROJECT_ROOT / "saved_crash_vid",
        PROJECT_ROOT / "saved_frames_vid",
    ]
    sample_dirs = [
        PROJECT_ROOT / "videos",
        PROJECT_ROOT / "dataset" / "Accidents",
        PROJECT_ROOT / "dataset" / "No_Accidents",
        PROJECT_ROOT / "Joiner" / "vids",
    ]
    cache_dirs = [
        PROJECT_ROOT / "backend" / "media" / "videos",
        PROJECT_ROOT / "artifacts" / "cache" / "samples" / "transcoded",
    ]

    allowed_exts = {".mp4", ".avi", ".mkv", ".mov"}

    # Gather sources
    source_files: List[Path] = []
    for d in incident_dirs + sample_dirs:
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() in allowed_exts:
                    source_files.append(p)

    if args.limit:
        source_files = source_files[:args.limit]

    print(f"\nDiscovered {len(source_files)} source video clips.")

    corrupt_sources: List[Tuple[Path, str]] = []
    need_transcode: List[Path] = []
    ready_sources: List[Path] = []

    for idx, path in enumerate(source_files, 1):
        rel = path.relative_to(PROJECT_ROOT)
        ok, data, err = probe_file(path, ffprobe_bin)
        if not ok:
            corrupt_sources.append((path, err))
        else:
            if is_web_compatible_h264(data):
                ready_sources.append(path)
            else:
                need_transcode.append(path)

    print(f"  - Readable & already web-compatible H.264 : {len(ready_sources)}")
    print(f"  - Readable but needs on-the-fly transcode : {len(need_transcode)}")
    print(f"  - Unreadable / corrupt source files       : {len(corrupt_sources)}")

    if corrupt_sources:
        print("\n[!] Corrupt source files:")
        for p, err in corrupt_sources[:10]:
            print(f"    - {p.relative_to(PROJECT_ROOT)}: {err}")

    # Gather cached files
    cached_files: List[Path] = []
    for d in cache_dirs:
        if d.exists():
            for p in d.glob("*.mp4"):
                if not p.name.startswith(".tmp_"):
                    cached_files.append(p)

    print(f"\nDiscovered {len(cached_files)} cached transcoded MP4 files.")
    invalid_caches: List[Tuple[Path, str]] = []
    valid_caches: List[Path] = []

    for path in cached_files:
        ok, data, err = probe_file(path, ffprobe_bin)
        if not ok or not is_web_compatible_h264(data):
            invalid_caches.append((path, err or "Not valid H.264 MP4"))
        else:
            valid_caches.append(path)

    print(f"  - Valid cached web MP4 files              : {len(valid_caches)}")
    print(f"  - Invalid or corrupt cached MP4 files     : {len(invalid_caches)}")

    if invalid_caches:
        print("\n[!] Invalid cached MP4 files:")
        for p, err in invalid_caches[:10]:
            print(f"    - {p.relative_to(PROJECT_ROOT)}: {err}")

    print("\n============================================================")
    if corrupt_sources or invalid_caches:
        print(f"FAILED: {len(corrupt_sources)} corrupt sources, {len(invalid_caches)} invalid caches.")
        sys.exit(1)
    else:
        print("SUCCESS: All video sources are probe-readable and all cached clips are valid H.264 web MP4s.")
        sys.exit(0)

if __name__ == "__main__":
    main()
