#!/usr/bin/env python3
"""
Argus Phase 0 Pipeline Tracer & Diagnosis Runner.
Executes all 19 bundled clips through the full CV pipeline with ARGUS_TRACE=true,
outputs artifacts/traces/<clip_name>.jsonl, generates contact sheets for failing clips,
and prints a complete diagnostic table.
"""
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

# Ensure Argus project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["ARGUS_TRACE"] = "true"

from System.Functions.Detection import Detection
from System.Functions.Tracking import Tracking
from System.Functions.Crashing import Crashing
from System.Functions.Detector.legacy import LegacyBoxFilesDetector
from VIF.vif import VIF
from boxes.yoloFiles import loadFile
from argus_ml.trace import read_run_trace, summarize_run_trace, get_trace_dir

BUNDLED_CLIPS: List[Tuple[str, str, str, int]] = [
    ("1528.mp4", "videos/1528.mp4", "accident", 1528),
    ("1506.mp4", "videos/1506.mp4", "accident", 1506),
    ("1513.mp4", "videos/1513.mp4", "accident", 1513),
    ("1543.mp4", "videos/1543.mp4", "accident", 1543),
    ("1508.mp4", "videos/1508.mp4", "accident", 1508),
    ("1516.mp4", "videos/1516.mp4", "accident", 1516),
    ("1518.mp4", "videos/1518.mp4", "accident", 1518),
    ("1519.mp4", "videos/1519.mp4", "accident", 1519),
    ("1521.mp4", "videos/1521.mp4", "accident", 1521),
    ("1522.mp4", "videos/Extra/1522.mp4", "accident", 1522),
    ("1529.mp4", "videos/1529.mp4", "accident", 1529),
    ("1533.mp4", "videos/1533.mp4", "accident", 1533),
    ("1534.mp4", "videos/1534.mp4", "accident", 1534),
    ("1548.mp4", "videos/1548.mp4", "accident", 1548),
    ("1566.mp4", "videos/1566.mp4", "accident", 1566),
    ("1600.mp4", "videos/1600.mp4", "normal", 1600),
    ("1601.mp4", "videos/1601.mp4", "normal", 1601),
    ("1602.mp4", "videos/1602.mp4", "normal", 1602),
    ("1701.mp4", "videos/1701.mp4", "normal", 1701),
]


def generate_contact_sheet(video_path: Path, output_path: Path, num_frames: int = 12) -> None:
    """Extract num_frames evenly across the video and stitch into a 3x4 contact sheet."""
    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if total_frames <= 0:
        cap.release()
        return

    indices = np.linspace(0, max(0, total_frames - 1), num_frames, dtype=int)
    extracted = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        if not ret or frame is None:
            frame = np.zeros((180, 240, 3), dtype=np.uint8)
        else:
            frame = cv2.resize(frame, (240, 180))

        # Add label overlay
        sec = round(idx / fps, 2)
        cv2.putText(frame, f"F:{idx} ({sec}s)", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
        extracted.append(frame)

    cap.release()

    # Create 3 rows of 4 columns
    rows = []
    for r in range(3):
        row_frames = extracted[r * 4:(r + 1) * 4]
        rows.append(np.hstack(row_frames))
    sheet = np.vstack(rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), sheet)


def run_clip_trace(
    name: str,
    path_str: str,
    expected_label: str,
    camera_id: int,
    vif: VIF,
    tracking: Tracking,
) -> Dict[str, Any]:
    """Execute a single clip through the pipeline, recording batch traces."""
    video_path = PROJECT_ROOT / path_str
    if not video_path.exists():
        return {"name": name, "error": "file not found"}

    run_id = Path(name).stem
    os.environ["ARGUS_TRACE_RUN_ID"] = run_id

    # Clean existing trace file for this clip
    trace_file = get_trace_dir() / f"{run_id}.jsonl"
    if trace_file.exists():
        trace_file.unlink()

    # Identify detector used
    legacy_detector = LegacyBoxFilesDetector()
    box_file = legacy_detector._get_box_file(name)
    if box_file and box_file.exists():
        detector_used = f"box file ({box_file.name})"
        file_boxes = loadFile(str(camera_id))
    else:
        detector_used = "motion (fallback)"
        file_boxes = None

    cap = cv2.VideoCapture(str(video_path))
    crashing = Crashing(vif)

    frames = []
    alerts = 0
    batches = 0
    no_of_frames = 0

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
            else:
                # Use motion fallback detection
                cur_boxes = legacy_detector._motion_fallback.detect(
                    cur_frames[0],
                    ref_frame=cur_frames[min(5, len(cur_frames) - 1)],
                    frame_width=480,
                    frame_height=360,
                )

            trackers = tracking.track(cur_frames, cur_boxes, 480, 360)
            dims = crashing.crash(
                cur_frames,
                trackers,
                camera_id=camera_id,
                starting_frame_id=no_of_frames - 29,
                run_id=run_id,
                batch_index=batches,
            )
            if len(dims) > 0:
                alerts += 1

    cap.release()

    # Read collected traces from artifacts/traces/<run_id>.jsonl
    records = read_run_trace(run_id)
    summary = summarize_run_trace(records)

    # Classify outcome
    if expected_label == "accident":
        outcome = "Alert on accident clip" if alerts > 0 else "Missed accident"
    elif expected_label == "normal":
        outcome = "False alarm" if alerts > 0 else "No alert on normal clip"
    else:
        outcome = "Not scored (unlabeled)"

    # Determine primary cause
    if alerts > 0 and expected_label == "accident":
        primary_cause = "CRASH_DETECTED"
    elif alerts == 0 and expected_label == "normal":
        primary_cause = "CORRECT_NORMAL"
    elif alerts > 0 and expected_label == "normal":
        primary_cause = "CLASSIFIER_HIGH_ON_NORMAL"
    else:
        # Missed accident
        primary_cause = summary["primary_cause"]

    contact_sheet_path = None
    if outcome in ("Missed accident", "False alarm"):
        sheet_p = PROJECT_ROOT / "artifacts" / "traces" / "contact_sheets" / f"{run_id}.jpg"
        generate_contact_sheet(video_path, sheet_p)
        contact_sheet_path = str(sheet_p.relative_to(PROJECT_ROOT))

    return {
        "clip": name,
        "detector_used": detector_used,
        "batches": batches,
        "max_trackers": summary["max_trackers"],
        "pairs_evaluated": summary["total_pairs_evaluated"],
        "dominant_filter": summary["dominant_filter"],
        "filter_counts": summary["filter_counts"],
        "max_classifier_score": summary["max_classifier_score"],
        "alert_count": alerts,
        "expected_label": expected_label,
        "outcome": outcome,
        "primary_cause": primary_cause,
        "contact_sheet": contact_sheet_path,
        "trace_file": str(trace_file.relative_to(PROJECT_ROOT)),
    }


def main():
    print("=" * 80)
    print("ARGUS PHASE 0: BUNDLED CLIPS PIPELINE TRACE & DIAGNOSIS")
    print("=" * 80)

    vif = VIF()
    tracking = Tracking()

    results = []
    for item in BUNDLED_CLIPS:
        name, path_str, expected_label, camera_id = item
        print(f"Tracing {name}...", end="", flush=True)
        res = run_clip_trace(name, path_str, expected_label, camera_id, vif, tracking)
        results.append(res)
        print(f" done (outcome: {res['outcome']}, cause: {res['primary_cause']})")

    # Output Markdown Table
    print("\n\n### Trace Summary Table (All 19 Bundled Clips)")
    print("| Clip | Detector | Batches | Max Trackers | Pairs Eval | Dominant Filter | Max Score | Alerts | Expected | Outcome | Primary Cause |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in results:
        print(
            f"| `{r['clip']}` | {r['detector_used'].split(' ')[0]} | {r['batches']} | "
            f"{r['max_trackers']} | {r['pairs_evaluated']} | {r['dominant_filter']} | "
            f"{r['max_classifier_score']:.4f} | {r['alert_count']} | {r['expected_label']} | "
            f"**{r['outcome']}** | `{r['primary_cause']}` |"
        )

    # Save complete JSON artifact
    out_json = PROJECT_ROOT / "artifacts" / "traces" / "phase0_trace_summary.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nTrace summary written to: {out_json}")


if __name__ == "__main__":
    main()
