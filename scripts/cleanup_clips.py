#!/usr/bin/env python3
"""
Argus Video Clip Retention Cleanup Utility.

Purges saved video clip files older than `clip_retention_days`.
Performs a safe dry-run by default unless `--apply` is specified.
Never alters or deletes SQLite database records.
"""

import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_CLIP_DIRS = [
    PROJECT_ROOT / "saved_crash_vid",
    PROJECT_ROOT / "saved_frames_vid",
    PROJECT_ROOT / "backend" / "media" / "videos",
]

ALLOWED_VIDEO_EXTENSIONS = {".avi", ".mp4", ".mkv", ".mov"}

def get_retention_days_from_db(db_path: Path) -> int:
    """Retrieve clip_retention_days from settings table, defaulting to 30."""
    if not db_path.exists():
        return 30
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3.0)
        cursor = conn.cursor()
        row = cursor.execute("SELECT value FROM settings WHERE key = 'clip_retention_days';").fetchone()
        conn.close()
        if row and row[0]:
            return int(row[0])
    except Exception:
        pass
    return 30

def find_expired_clips(directories: List[Path], retention_days: int) -> List[Tuple[Path, float, float]]:
    """
    Find video files in target directories older than retention_days.
    Returns list of tuples: (file_path, size_bytes, age_in_days).
    """
    now = time.time()
    cutoff_timestamp = now - (retention_days * 86400.0)
    expired_files: List[Tuple[Path, float, float]] = []

    for d in directories:
        if not d.exists() or not d.is_dir():
            continue
        for root, _, files in os.walk(d):
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in ALLOWED_VIDEO_EXTENSIONS:
                    file_path = Path(root) / f
                    try:
                        st = file_path.stat()
                        if st.st_mtime < cutoff_timestamp:
                            age_days = (now - st.st_mtime) / 86400.0
                            expired_files.append((file_path, st.st_size, age_days))
                    except (OSError, PermissionError):
                        continue

    return expired_files

def main():
    parser = argparse.ArgumentParser(
        description="Argus Clip Retention Cleanup: Purge clip files older than retention policy threshold."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute file deletion. Defaults to safe dry-run mode if omitted.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Override retention policy days (defaults to setting stored in Argus database).",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to SQLite database to read settings from.",
    )
    parser.add_argument(
        "--dir",
        action="append",
        dest="custom_dirs",
        help="Specific directory to scan (can be repeated). Defaults to standard clip directories.",
    )

    args = parser.parse_args()

    db_file = Path(args.db_path) if args.db_path else PROJECT_ROOT / "System" / "Database" / "Argus_DB.db"
    retention_days = args.days if args.days is not None else get_retention_days_from_db(db_file)

    if retention_days < 1:
        print(f"Error: retention days must be at least 1 (got {retention_days})", file=sys.stderr)
        sys.exit(1)

    target_dirs = [Path(p) for p in args.custom_dirs] if args.custom_dirs else DEFAULT_CLIP_DIRS

    mode_label = "EXECUTE (APPLY)" if args.apply else "DRY-RUN (SIMULATION)"
    print(f"============================================================")
    print(f" Argus Clip Storage Retention Policy — {mode_label}")
    print(f" Retention Policy Threshold : {retention_days} days")
    print(f" Scanned Directories        : {', '.join(str(d) for d in target_dirs)}")
    print(f" Database Protection        : NO database rows are altered")
    print(f"============================================================")

    expired_clips = find_expired_clips(target_dirs, retention_days)

    if not expired_clips:
        print(f"No clip files found older than {retention_days} days. All clips are within retention threshold.")
        sys.exit(0)

    total_bytes = sum(size for _, size, _ in expired_clips)
    total_mb = total_bytes / (1024 * 1024)

    for path, size, age in expired_clips:
        size_mb = size / (1024 * 1024)
        if args.apply:
            try:
                path.unlink()
                print(f" [DELETED] {path} ({size_mb:.2f} MB, {age:.1f} days old)")
            except Exception as e:
                print(f" [FAILED]  {path}: {e}", file=sys.stderr)
        else:
            print(f" [WOULD DELETE] {path} ({size_mb:.2f} MB, {age:.1f} days old)")

    print(f"------------------------------------------------------------")
    if args.apply:
        print(f"Retention cleanup complete: {len(expired_clips)} files purged, freeing {total_mb:.2f} MB.")
    else:
        print(f"Dry run complete: {len(expired_clips)} files ({total_mb:.2f} MB) identified for deletion.")
        print(f"To execute deletion, re-run with: python3 scripts/cleanup_clips.py --apply")

if __name__ == "__main__":
    main()
