#!/usr/bin/env python3
"""
Generate comprehensive data manifest with leak-free group-based splits.
Fields: video_path, label (accident|normal), source, camera_view (cctv|dashcam),
        license, group_id, split (train|val|test), duration_s, frames_count.
"""
import argparse
import csv
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
import cv2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("make_manifest")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_group_split(group_id: str, train_ratio=0.70, val_ratio=0.15) -> str:
    """
    Deterministically hash group_id to assign a split.
    Guarantees zero group leakage across train, val, and test.
    """
    h = int(hashlib.sha256(group_id.encode("utf-8")).hexdigest(), 16) % 1000
    bucket = h / 1000.0
    if bucket < train_ratio:
        return "train"
    elif bucket < (train_ratio + val_ratio):
        return "val"
    else:
        return "test"


def inspect_video_meta(path: Path):
    """Read frame count and duration using cv2.VideoCapture."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return 0, 0.0
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    duration = frames / fps if fps > 0 else 0.0
    cap.release()
    return frames, round(duration, 2)


def generate_manifest(output_csv: Path, output_jsonl: Path) -> List[Dict]:
    records: List[Dict] = []

    # 1. CCTV Subvideos - Accidents
    accidents_dir = PROJECT_ROOT / "dataset" / "Accidents" / "subvideos"
    if accidents_dir.exists():
        for avi in sorted(accidents_dir.glob("*.avi")):
            group = f"cctv_subvid_acc_{avi.stem}"
            split = get_group_split(group)
            frames, dur = inspect_video_meta(avi)
            records.append({
                "video_path": str(avi.relative_to(PROJECT_ROOT)),
                "label": "accident",
                "source": "argus_surveillance_vif",
                "camera_view": "cctv",
                "license": "MIT",
                "group_id": group,
                "split": split,
                "frames_count": frames,
                "duration_s": dur,
            })

    # 2. CCTV Subvideos - No Accidents (Normal)
    no_accidents_dir = PROJECT_ROOT / "dataset" / "No_Accidents" / "subvideos"
    if no_accidents_dir.exists():
        for avi in sorted(no_accidents_dir.glob("*.avi")):
            group = f"cctv_subvid_norm_{avi.stem}"
            split = get_group_split(group)
            frames, dur = inspect_video_meta(avi)
            records.append({
                "video_path": str(avi.relative_to(PROJECT_ROOT)),
                "label": "normal",
                "source": "argus_surveillance_vif",
                "camera_view": "cctv",
                "license": "MIT",
                "group_id": group,
                "split": split,
                "frames_count": frames,
                "duration_s": dur,
            })

    # 3. Full CCTV Surveillance Feeds (videos/*.mp4)
    # Known accident feeds vs normal feeds
    known_accident_cams = {1528, 1506, 1513, 1543, 1508, 1516, 1518, 1519, 1521, 1522, 1529, 1533, 1534}
    videos_dir = PROJECT_ROOT / "videos"
    if videos_dir.exists():
        for mp4 in sorted(videos_dir.glob("*.mp4")):
            try:
                cam_id = int(mp4.stem)
            except ValueError:
                cam_id = 9999
            label = "accident" if cam_id in known_accident_cams else "normal"
            group = f"cctv_cam_{cam_id}"
            split = get_group_split(group)
            frames, dur = inspect_video_meta(mp4)
            records.append({
                "video_path": str(mp4.relative_to(PROJECT_ROOT)),
                "label": label,
                "source": "argus_cctv_feed",
                "camera_view": "cctv",
                "license": "MIT",
                "group_id": group,
                "split": split,
                "frames_count": frames,
                "duration_s": dur,
            })

    # 4. Extra CCTV Feeds (videos/Extra/*.mp4)
    extra_dir = PROJECT_ROOT / "videos" / "Extra"
    if extra_dir.exists():
        for mp4 in sorted(extra_dir.glob("*.mp4")):
            try:
                cam_id = int(mp4.stem)
            except ValueError:
                cam_id = 9998
            label = "normal"  # Extra videos default to background normal traffic
            group = f"cctv_extra_cam_{cam_id}"
            split = get_group_split(group)
            frames, dur = inspect_video_meta(mp4)
            records.append({
                "video_path": str(mp4.relative_to(PROJECT_ROOT)),
                "label": label,
                "source": "argus_cctv_extra",
                "camera_view": "cctv",
                "license": "MIT",
                "group_id": group,
                "split": split,
                "frames_count": frames,
                "duration_s": dur,
            })

    # Write CSV
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "video_path",
                "label",
                "source",
                "camera_view",
                "license",
                "group_id",
                "split",
                "frames_count",
                "duration_s",
            ],
        )
        writer.writeheader()
        writer.writerows(records)

    # Write JSONL
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(output_jsonl, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    logger.info(f"Generated manifest with {len(records)} items.")
    split_counts = {}
    for r in records:
        split_counts[r["split"]] = split_counts.get(r["split"], 0) + 1
    logger.info(f"Split breakdown: {split_counts}")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate dataset manifest with group splits")
    parser.add_argument(
        "--csv",
        type=Path,
        default=PROJECT_ROOT / "data" / "manifest.csv",
        help="Path for manifest CSV",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=PROJECT_ROOT / "data" / "manifest.jsonl",
        help="Path for manifest JSONL",
    )
    args = parser.parse_args()
    generate_manifest(args.csv, args.jsonl)
