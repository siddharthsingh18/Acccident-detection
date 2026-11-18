#!/usr/bin/env python3
"""
Phase 4 Crash Geometry Flags Measurement Runner.
Systematically evaluates:
  1. Baseline (all flags OFF: CRASH_ADAPTIVE_BOX_FILTER=false, CRASH_DISTANCE_FACTOR=0.25, CRASH_SINGLE_VEHICLE=false)
  2. Flag 1 Alone: CRASH_ADAPTIVE_BOX_FILTER=true (fraction=0.04)
  3. Flag 2 Alone: CRASH_DISTANCE_FACTOR=0.35
  4. Flag 3 Alone: CRASH_SINGLE_VEHICLE=true (decel=0.60, heading=45°)
  5. All flags combined

Runs across:
  A. The Seattle CCTV Upload (03f0c255... / reconstructed_feed.mp4) with ModernYoloDetector
  B. Smoke test summary on bundled clips (1528 accident, 1600 normal, 1548 low-res/distant accident)
"""
import copy
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from System.Functions.Tracking import Tracking
from System.Functions.Crashing import Crashing
from System.Functions.Detector.yolo import ModernYoloDetector
from System.Functions.Detector.legacy import LegacyBoxFilesDetector
from VIF.vif import VIF
from boxes.yoloFiles import loadFile


def evaluate_video(video_path: Path, use_box_file: bool = False, box_name: str = "") -> Dict[str, Any]:
    vif = VIF()
    crashing = Crashing(vif)
    tracking = Tracking()

    if use_box_file and box_name:
        file_boxes = loadFile(box_name)
        detector = None
    else:
        file_boxes = None
        detector = ModernYoloDetector()

    cap = cv2.VideoCapture(str(video_path))
    frames = []
    no_of_frames = 0
    batches = 0
    alerts = 0
    total_detections = 0
    total_pairs = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (480, 360))
        frames.append(frame)
        no_of_frames += 1

        if len(frames) == 30:
            batches += 1
            cur_frames = copy.deepcopy(frames)
            frames = frames[15:]

            box_idx = no_of_frames - 30
            if file_boxes and 0 <= box_idx < len(file_boxes):
                cur_boxes = file_boxes[box_idx]
            elif detector:
                cur_boxes = detector.detect(cur_frames[0], frame_index=box_idx)
            else:
                cur_boxes = []

            total_detections += len(cur_boxes)
            trackers = tracking.track(cur_frames, cur_boxes, 480, 360)

            dims = crashing.crash(
                cur_frames,
                trackers,
                camera_id=999,
                starting_frame_id=no_of_frames - 29,
            )
            if dims and len(dims) > 0:
                alerts += 1

    cap.release()
    return {
        "batches": batches,
        "total_detections": total_detections,
        "alerts": alerts,
        "last_failed_box_size": crashing.last_failed_box_size,
        "last_failed_aspect_ratio": crashing.last_failed_aspect_ratio,
    }


def main():
    configs = [
        ("Baseline (All Flags OFF)", {
            "CRASH_ADAPTIVE_BOX_FILTER": "false",
            "CRASH_DISTANCE_FACTOR": "0.25",
            "CRASH_SINGLE_VEHICLE": "false",
        }),
        ("Flag 1 Alone (CRASH_ADAPTIVE_BOX_FILTER=true)", {
            "CRASH_ADAPTIVE_BOX_FILTER": "true",
            "CRASH_ADAPTIVE_BOX_FRACTION": "0.04",
            "CRASH_DISTANCE_FACTOR": "0.25",
            "CRASH_SINGLE_VEHICLE": "false",
        }),
        ("Flag 2 Alone (CRASH_DISTANCE_FACTOR=0.35)", {
            "CRASH_ADAPTIVE_BOX_FILTER": "false",
            "CRASH_DISTANCE_FACTOR": "0.35",
            "CRASH_SINGLE_VEHICLE": "false",
        }),
        ("Flag 3 Alone (CRASH_SINGLE_VEHICLE=true)", {
            "CRASH_ADAPTIVE_BOX_FILTER": "false",
            "CRASH_DISTANCE_FACTOR": "0.25",
            "CRASH_SINGLE_VEHICLE": "true",
            "CRASH_SINGLE_DECEL_THRESHOLD": "0.60",
            "CRASH_SINGLE_HEADING_ANGLE": "45.0",
        }),
        ("All Flags Combined", {
            "CRASH_ADAPTIVE_BOX_FILTER": "true",
            "CRASH_ADAPTIVE_BOX_FRACTION": "0.04",
            "CRASH_DISTANCE_FACTOR": "0.35",
            "CRASH_SINGLE_VEHICLE": "true",
            "CRASH_SINGLE_DECEL_THRESHOLD": "0.60",
            "CRASH_SINGLE_HEADING_ANGLE": "45.0",
        }),
    ]

    seattle_video = PROJECT_ROOT / "artifacts" / "extracted_frames" / "feed_03f0c255" / "reconstructed_feed.mp4"
    clip_1528 = PROJECT_ROOT / "videos" / "1528.mp4"
    clip_1600 = PROJECT_ROOT / "videos" / "1600.mp4"

    print("=" * 80)
    print("PHASE 4 CRASH GEOMETRY FLAGS MEASUREMENT MATRIX")
    print("=" * 80)

    print("\n1. SEATTLE CCTV UPLOAD (03f0c255... - Unannotated Real Upload with ModernYoloDetector)")
    print(f"{'Configuration':<45} {'Batches':<10} {'Detections':<12} {'Alerts':<8}")
    print("-" * 75)

    for name, env_vars in configs:
        for k, v in env_vars.items():
            os.environ[k] = v
        res = evaluate_video(seattle_video, use_box_file=False)
        print(f"{name:<45} {res['batches']:<10} {res['total_detections']:<12} {res['alerts']:<8}")

    print("\n2. BUNDLED CLIP 1528 (Smoke Test - Confirmed Accident with Box File)")
    print(f"{'Configuration':<45} {'Batches':<10} {'Detections':<12} {'Alerts':<8}")
    print("-" * 75)

    for name, env_vars in configs:
        for k, v in env_vars.items():
            os.environ[k] = v
        res = evaluate_video(clip_1528, use_box_file=True, box_name="1528")
        print(f"{name:<45} {res['batches']:<10} {res['total_detections']:<12} {res['alerts']:<8}")

    print("\n3. BUNDLED CLIP 1600 (Smoke Test - Confirmed Normal Footage with Box File)")
    print(f"{'Configuration':<45} {'Batches':<10} {'Detections':<12} {'Alerts':<8}")
    print("-" * 75)

    for name, env_vars in configs:
        for k, v in env_vars.items():
            os.environ[k] = v
        res = evaluate_video(clip_1600, use_box_file=True, box_name="1600")
        print(f"{name:<45} {res['batches']:<10} {res['total_detections']:<12} {res['alerts']:<8}")

    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())

