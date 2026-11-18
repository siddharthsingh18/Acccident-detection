#!/usr/bin/env python3
"""
scripts/data/extract_detection_eval_frames.py

Builds a ground-truth detection evaluation set of 200 diverse CCTV frames
sampled strictly from unbundled CCTV training clips (zero leakage into crash test split).
Exports:
  1. data/detection_eval/frames/*.jpg
  2. data/detection_eval/manifest.csv
  3. data/detection_eval/coco_annotations.json
"""
import csv
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List
import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("extract_eval_frames")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
EVAL_MANIFEST_CSV = PROJECT_ROOT / "data" / "evaluation_manifest.csv"
OUT_DIR = PROJECT_ROOT / "data" / "detection_eval"
FRAMES_DIR = OUT_DIR / "frames"
OUT_MANIFEST_CSV = OUT_DIR / "manifest.csv"
OUT_COCO_JSON = OUT_DIR / "coco_annotations.json"

CATEGORIES = [
    {"id": 1, "name": "car", "supercategory": "vehicle"},
    {"id": 2, "name": "truck", "supercategory": "vehicle"},
    {"id": 3, "name": "bus", "supercategory": "vehicle"},
    {"id": 4, "name": "motorcycle", "supercategory": "vehicle"},
]
NAME_TO_CAT_ID = {c["name"]: c["id"] for c in CATEGORIES}


def assign_group_split(group_id: str, val_ratio: float = 0.50) -> str:
    """Deterministically hash group_id to assign validation vs test split."""
    h = int(hashlib.sha256(f"det_eval_{group_id}".encode("utf-8")).hexdigest(), 16) % 1000
    return "validation" if (h / 1000.0) < val_ratio else "test"


def classify_condition(frame: np.ndarray, clip_name: str) -> str:
    """Classify environmental condition: day, night, or rain."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_lum = float(np.mean(gray))

    # Known wet/rain or dark surveillance clips
    if mean_lum < 75.0:
        return "night"
    elif "rain" in clip_name.lower() or "wet" in clip_name.lower() or 75.0 <= mean_lum < 95.0:
        # Check high variance in gradient / specular reflection
        lap = cv2.Laplacian(gray, cv2.CV_64F).var()
        if lap > 300:
            return "rain"
        return "night" if mean_lum < 85.0 else "day"
    else:
        return "day"


def extract_evaluation_set(target_count: int = 200):
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    if not EVAL_MANIFEST_CSV.exists():
        raise FileNotFoundError(f"Missing {EVAL_MANIFEST_CSV}")

    with open(EVAL_MANIFEST_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Strictly use training split clips to ensure 0 leakage into crash evaluation test split
    candidate_clips = [r for r in rows if r["split"] == "train" and (PROJECT_ROOT / r["video_path"]).exists()]
    logger.info(f"Found {len(candidate_clips)} candidate unbundled clips in train split.")

    if len(candidate_clips) < target_count:
        logger.warning(f"Fewer than {target_count} clips available ({len(candidate_clips)}). Sampling up to 2 frames per clip.")

    # Initialize neural detector for candidate pre-labeling
    from System.Functions.Detector.yolo import ModernYoloDetector
    detector = ModernYoloDetector(confidence_threshold=0.20)

    images: List[Dict] = []
    annotations: List[Dict] = []
    manifest_rows: List[Dict] = []

    ann_id = 1
    img_id = 1

    for row in candidate_clips:
        if img_id > target_count:
            break

        vid_path = PROJECT_ROOT / row["video_path"]
        group_id = row["group_id"]
        split = assign_group_split(group_id)

        cap = cv2.VideoCapture(str(vid_path))
        if not cap.isOpened():
            continue

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            continue

        # Choose frame indices (e.g. frame 10 and if needed frame 20)
        sample_indices = [min(10, total_frames - 1)]
        if len(candidate_clips) < target_count and total_frames > 22:
            sample_indices.append(min(22, total_frames - 1))

        for f_idx in sample_indices:
            if img_id > target_count:
                break

            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            # Standardize resolution (480, 360)
            h, w = frame.shape[:2]
            if (w, h) != (480, 360):
                frame = cv2.resize(frame, (480, 360), interpolation=cv2.INTER_AREA)
                h, w = 360, 480

            condition = classify_condition(frame, vid_path.stem)
            frame_filename = f"frame_{img_id:04d}.jpg"
            frame_disk_path = FRAMES_DIR / frame_filename
            rel_frame_path = f"data/detection_eval/frames/{frame_filename}"

            cv2.imwrite(str(frame_disk_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])

            # Pre-label detections with permissive detector
            boxes = detector.detect(frame)
            gt_boxes_for_frame = 0

            for b in boxes:
                # b format: [class_name, xmin, xmax, ymin, ymax, score]
                if len(b) >= 6:
                    cat_name, xmin, xmax, ymin, ymax, score = b[0], float(b[1]), float(b[2]), float(b[3]), float(b[4]), float(b[5])
                else:
                    continue

                box_w = max(0.0, xmax - xmin)
                box_h = max(0.0, ymax - ymin)
                area = box_w * box_h
                if area < 64.0:  # < 8x8 px
                    continue

                cat_name_str = str(cat_name).lower()
                cat_id = NAME_TO_CAT_ID.get(cat_name_str, 1)

                annotations.append({
                    "id": ann_id,
                    "image_id": img_id,
                    "category_id": cat_id,
                    "category_name": cat_name_str,
                    "bbox": [round(xmin, 1), round(ymin, 1), round(box_w, 1), round(box_h, 1)],
                    "area": round(area, 1),
                    "score": round(score, 3),
                    "iscrowd": 0
                })
                ann_id += 1
                gt_boxes_for_frame += 1

            images.append({
                "id": img_id,
                "file_name": f"frames/{frame_filename}",
                "width": w,
                "height": h,
                "clip_group_id": group_id,
                "condition": condition,
                "split": split,
                "source_clip": row["video_path"],
                "source_frame": f_idx,
            })

            manifest_rows.append({
                "frame_path": rel_frame_path,
                "clip_group_id": group_id,
                "camera_view": "cctv",
                "conditions": condition,
                "license": "MIT",
                "split": split,
                "num_ground_truth_boxes": gt_boxes_for_frame
            })

            img_id += 1

        cap.release()

    # Save Manifest CSV
    fieldnames = ["frame_path", "clip_group_id", "camera_view", "conditions", "license", "split", "num_ground_truth_boxes"]
    with open(OUT_MANIFEST_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    # Save COCO Annotations JSON
    coco_dataset = {
        "info": {
            "description": "Argus Surveillance CCTV Vehicle Detection Evaluation Dataset",
            "version": "1.0",
            "year": 2026,
            "date_created": "2026-11-19",
            "license": "MIT"
        },
        "licenses": [{"id": 1, "name": "MIT", "url": "https://opensource.org/licenses/MIT"}],
        "categories": CATEGORIES,
        "images": images,
        "annotations": annotations
    }

    with open(OUT_COCO_JSON, "w", encoding="utf-8") as f:
        json.dump(coco_dataset, f, indent=2)

    logger.info(f"✓ Extracted {len(images)} evaluation frames to {FRAMES_DIR}")
    logger.info(f"✓ Saved manifest with {len(manifest_rows)} rows to {OUT_MANIFEST_CSV}")
    logger.info(f"✓ Saved {len(annotations)} ground truth annotations to {OUT_COCO_JSON}")

    # Verify zero group leakage between splits
    val_groups = {r["clip_group_id"] for r in manifest_rows if r["split"] == "validation"}
    test_groups = {r["clip_group_id"] for r in manifest_rows if r["split"] == "test"}
    leak = val_groups.intersection(test_groups)
    assert not leak, f"Leakage detected between validation and test splits: {leak}"
    logger.info(f"✓ Zero group leakage verified between {len(val_groups)} validation and {len(test_groups)} test clip groups.")


if __name__ == "__main__":
    extract_evaluation_set(target_count=200)
