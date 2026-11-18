#!/usr/bin/env python3
"""
Phase 3 Seattle CCTV Upload Trace Runner.
Runs the reconstructed Seattle CCTV feed (03f0c255...) through the full pipeline
with the new ModernYoloDetector (SSDLite320 / BSD-3) and outputs artifacts/traces/03f0c255_p3.jsonl.
"""
import copy
import json
import os
import sys
from pathlib import Path
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("ARGUS_TRACE", "true")
os.environ.setdefault("ARGUS_TRACE_RUN_ID", "03f0c255_p3")
os.environ.setdefault("ARGUS_DETECTOR", "yolo")
os.environ.setdefault("ARGUS_DETECTOR_CONFIDENCE", "0.35")
os.environ.setdefault("ARGUS_DETECTOR_STRIDE", "1")

from System.Functions.Tracking import Tracking
from System.Functions.Crashing import Crashing
from System.Functions.Detector.yolo import ModernYoloDetector
from VIF.vif import VIF
from argus_ml.trace import read_run_trace, summarize_run_trace, get_trace_dir


def main():
    video_path = PROJECT_ROOT / "artifacts" / "extracted_frames" / "feed_03f0c255" / "reconstructed_feed.mp4"
    if not video_path.exists():
        print(f"Error: {video_path} does not exist", file=sys.stderr)
        return 1

    trace_file = get_trace_dir() / "03f0c255_p3.jsonl"
    if trace_file.exists():
        trace_file.unlink()

    detector = ModernYoloDetector()
    print(f"Using detector: {detector.name} (backend: {detector.backend})")
    print(f"Confidence threshold: {detector.conf_threshold}, frame stride: {detector.frame_stride}")

    vif = VIF()
    tracking = Tracking()
    crashing = Crashing(vif)

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Processing {total_frames} frames from {video_path.name}...")

    frames = []
    no_of_frames = 0
    batches = 0
    alerts = 0

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

            # Run neural vehicle detection
            cur_boxes = detector.detect(
                cur_frames[0],
                ref_frame=cur_frames[min(5, len(cur_frames) - 1)],
                frame_width=480,
                frame_height=360,
                frame_index=no_of_frames - 30,
            )

            # Track detected vehicles
            trackers = tracking.track(cur_frames, cur_boxes, 480, 360)

            # Evaluate crash candidates
            dims = crashing.crash(
                cur_frames,
                trackers,
                camera_id=10,
                starting_frame_id=no_of_frames - 29,
            )
            if dims and len(dims) > 0:
                alerts += 1

    cap.release()
    print(f"Processed {batches} batches, total alerts: {alerts}")

    # Read and summarize the recorded trace
    entries = read_run_trace("03f0c255_p3")
    summary = summarize_run_trace(entries)

    print("\n" + "=" * 65)
    print("PHASE 3 TRACE SUMMARY: SEATTLE CCTV UPLOAD (03f0c255_p3)")
    print("=" * 65)
    print(f"Detector Backend:     {detector.backend}")
    print(f"Total Batches:        {len(entries)}")
    print(f"Batches with Vehicles:{sum(1 for e in entries if e.get('num_detections', 0) > 0)}")
    print(f"Max Vehicles/Batch:   {max(e.get('num_detections', 0) for e in entries)}")
    print(f"Total Trackers:       {summary.get('total_trackers', 0)}")
    print(f"Total Pairs Evaluated:{summary.get('total_pairs_evaluated', 0)}")
    print(f"Passed Geometry:      {summary.get('total_passed_geometry', 0)}")
    print(f"Classifier Calls:     {summary.get('total_classifier_calls', 0)}")
    print(f"Max Classifier Score: {summary.get('max_classifier_score')}")
    print(f"Total Alerts:         {summary.get('total_alerts', 0)}")
    print(f"Drop Reasons:         {summary.get('reasons_breakdown')}")
    print("=" * 65)

    # Print per-batch comparison table
    print("\nPer-Batch Trace Detail:")
    print(f"{'Batch':<6} {'Start':<6} {'Detections':<12} {'Trackers':<10} {'Pairs':<8} {'PassedGeom':<12} {'MaxScore':<10} {'Reason'}")
    print("-" * 75)
    for i, e in enumerate(entries, 1):
        score_str = f"{e.get('classifier_score'):.3f}" if e.get('classifier_score') is not None else "None"
        print(f"{i:<6} {e.get('starting_frame_id'):<6} {e.get('num_detections'):<12} {e.get('num_trackers'):<10} {e.get('pairs_evaluated'):<8} {e.get('candidates_passed_geometry'):<12} {score_str:<10} {e.get('primary_reason')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
