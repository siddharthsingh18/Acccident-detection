#!/usr/bin/env python3
"""
Headless CameraNode worker process.
Streams 30-frame batches with 15-frame overlap to Argus Master node over ZeroMQ.
Emits progress lines to stdout for parent process tracking.
"""
import argparse
import copy
import os
import signal
import socket
import sys
import time
from pathlib import Path
import cv2
import zmq

# Ensure Argus project root and backend are in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from System.Data.CONSTANTS import (
    FEED, FUNCTION, CAMERA_ID, STARTING_FRAME_ID,
    FRAMES, FRAME_WIDTH, FRAME_HEIGHT, READ_FILE,
    BOXES, CITY, DISTRICT
)
from boxes.yoloFiles import loadFile
from boxes.registry import lookup_box_file
from System.Functions.Detector import get_detector, ModernYoloDetector

running = True

def handle_signal(sig, frame):
    global running
    running = False
    print("STATUS:CANCELLED", flush=True)
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def is_master_reachable(ip: str, port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.05)
        s.connect((ip, port))
        s.close()
        return True
    except Exception:
        return False

def send_feed_to_master(master_ip: str, master_port: int, msg: dict, timeout_ms: int = 1500):
    """
    Send feed message to Argus Master node with a short timeout.
    Only attempts network send if the Master node port is open.
    """
    if not is_master_reachable(master_ip, master_port):
        return

    context = zmq.Context.instance()
    socket_zmq = context.socket(zmq.REQ)
    socket_zmq.setsockopt(zmq.RCVTIMEO, timeout_ms)
    socket_zmq.setsockopt(zmq.SNDTIMEO, timeout_ms)
    socket_zmq.setsockopt(zmq.LINGER, 0)
    try:
        from System.Connections.protocol import serialize_message
        socket_zmq.connect(f"tcp://{master_ip}:{master_port}")
        socket_zmq.send_multipart(serialize_message(msg))
        socket_zmq.recv_multipart()
    except Exception:
        pass
    finally:
        socket_zmq.close()

def detect_motion_boxes(frames, frame_width: int, frame_height: int):
    """
    Dynamic vehicle detector for arbitrary video feeds when no pre-annotated box file exists.
    Detects motion contours between consecutive frames in the 30-frame batch.
    """
    if len(frames) < 2:
        return []
    f1 = frames[0]
    f2 = frames[min(5, len(frames) - 1)]
    diff = cv2.absdiff(f1, f2)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w >= 25 and h >= 25 and (w * h) >= 600:
            boxes.append(["car", float(x), float(x + w), float(y), float(y + h), 0.85])
    return boxes[:8]

def run_headless_camera(video_path: str, camera_id: int, city: str, district: str, master_ip: str = "127.0.0.1", master_port: int = 10000, feed_id: str = "", is_test: bool = False):
    global running
    video_file = Path(video_path)
    if not video_file.exists():
        print(f"ERROR: Video file {video_path} does not exist", flush=True)
        sys.exit(1)

    cap = cv2.VideoCapture(str(video_file))
    if not cap.isOpened():
        print(f"ERROR: Cannot open video file {video_path}", flush=True)
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        total_frames = 100

    # Identify pre-annotated dataset box file strictly via content-hash registry (never via camera_id)
    file_boxes = []
    has_boxes = False

    box_file = lookup_box_file(video_path)
    if box_file and box_file.is_file():
        try:
            file_boxes = loadFile(box_file.stem)
            has_boxes = True
            print(f"Loaded {len(file_boxes)} box frames from registered box file: {box_file.name}", flush=True)
        except Exception as e:
            print(f"WARNING: Failed to parse registered box file {box_file}: {e}", flush=True)

    frame_width = 480
    frame_height = 360
    no_of_frames = 0
    frames = []

    print(f"STATUS:PROCESSING:0:{total_frames}", flush=True)

    # Select detector and determine detection quality:
    # 1. Registered videos with verified box files always use reference annotations (legacy parity)
    # 2. Uploaded / unannotated videos auto-select permissive neural detector if weights are installed,
    #    falling back to low-quality motion differencing if unavailable.
    if has_boxes:
        detector = get_detector("legacy")
        detection_quality = "reference"
    else:
        env_detector = os.getenv("ARGUS_DETECTOR", os.getenv("DETECTOR", "auto")).strip().lower()
        if env_detector == "motion":
            detector = get_detector("motion")
            detection_quality = "motion_fallback"
        else:
            neural = ModernYoloDetector()
            if neural.is_available:
                detector = neural
                detection_quality = "neural"
            else:
                detector = get_detector("motion")
                detection_quality = "motion_fallback"
                print("WARNING: No neural detector available for this video; falling back to low-quality motion detection.", flush=True)

    if detection_quality == "motion_fallback":
        print("DETECTION_MODE:low-quality detection mode", flush=True)
    else:
        print(f"DETECTION_MODE:{detector.name}", flush=True)

    print(f"DETECTION_QUALITY:{detection_quality}", flush=True)
    print(f"DETECTOR_NAME:{detector.name}", flush=True)

    max_vehicles_seen = 0
    t = time.time()
    while running:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, (frame_width, frame_height), interpolation=cv2.INTER_AREA)
        frames.append(frame)
        no_of_frames += 1

        if len(frames) == 30:
            new_frames_list = copy.deepcopy(frames)
            frames = frames[15:]

            box_index = no_of_frames - 30
            ref_idx = min(5, len(new_frames_list) - 1)
            boxes = detector.detect(
                new_frames_list[0],
                ref_frame=new_frames_list[ref_idx],
                video_name=video_file.stem,
                camera_id=camera_id,
                frame_index=box_index,
                boxes_file=file_boxes if has_boxes else None,
                frame_width=frame_width,
                frame_height=frame_height
            )

            if boxes:
                max_vehicles_seen = max(max_vehicles_seen, len(boxes))
                print(f"VEHICLES_DETECTED:{max_vehicles_seen}", flush=True)

            msg = {
                FUNCTION: FEED,
                CAMERA_ID: camera_id,
                STARTING_FRAME_ID: no_of_frames - 29,
                FRAMES: new_frames_list,
                FRAME_WIDTH: frame_width,
                FRAME_HEIGHT: frame_height,
                READ_FILE: True,
                BOXES: boxes,
                CITY: city,
                DISTRICT: district,
                "FEED_ID": feed_id,
                "TEST": is_test,
                "DETECTION_QUALITY": detection_quality,
                "DETECTOR_NAME": detector.name,
            }

            # Dispatch over ZeroMQ to Master node
            send_feed_to_master(master_ip, master_port, msg)

            # Report progress
            print(f"PROGRESS:{no_of_frames}:{total_frames}", flush=True)

        if no_of_frames % 30 == 0:
            current_time = time.time() - t
            delay = max(0.05 - current_time, 0.0)
            if delay > 0:
                time.sleep(delay)
            t = time.time()

    cap.release()

    # If the video ended and no batch was ever sent (e.g. short clips < 30 frames),
    # pad the buffer to 30 frames with the last frame so detection and crash analysis run.
    if running and no_of_frames > 0 and len(frames) > 0 and no_of_frames < 30:
        last_frame = frames[-1]
        while len(frames) < 30:
            frames.append(last_frame.copy())

        box_index = 0
        ref_idx = min(5, len(frames) - 1)
        boxes = detector.detect(
            frames[0],
            ref_frame=frames[ref_idx],
            video_name=video_file.stem,
            camera_id=camera_id,
            frame_index=box_index,
            boxes_file=file_boxes if has_boxes else None,
            frame_width=frame_width,
            frame_height=frame_height
        )

        if boxes:
            max_vehicles_seen = max(max_vehicles_seen, len(boxes))
            print(f"VEHICLES_DETECTED:{max_vehicles_seen}", flush=True)

        msg = {
            FUNCTION: FEED,
            CAMERA_ID: camera_id,
            STARTING_FRAME_ID: 1,
            FRAMES: frames,
            FRAME_WIDTH: frame_width,
            FRAME_HEIGHT: frame_height,
            READ_FILE: True,
            BOXES: boxes,
            CITY: city,
            DISTRICT: district,
            "FEED_ID": feed_id,
            "TEST": is_test,
            "DETECTION_QUALITY": detection_quality,
            "DETECTOR_NAME": detector.name,
        }
        send_feed_to_master(master_ip, master_port, msg)
        print(f"PROGRESS:{total_frames}:{total_frames}", flush=True)

    if running:
        print(f"VEHICLES_DETECTED:{max_vehicles_seen}", flush=True)
        print(f"PROGRESS:{total_frames}:{total_frames}", flush=True)
        print("STATUS:DONE", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless Argus Camera Worker")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--camera-id", type=int, required=True, help="Camera identifier")
    parser.add_argument("--city", default="Cairo", help="City name")
    parser.add_argument("--district", default="District 1", help="District name")
    parser.add_argument("--master-ip", default="127.0.0.1", help="Master node IP")
    parser.add_argument("--master-port", type=int, default=10000, help="Master node port")
    parser.add_argument("--feed-id", default="", help="Active feed identifier")
    parser.add_argument("--test", action="store_true", default=False, help="Tag feed as test run")
    parser.add_argument("--detector", default=None, help="Detector override (legacy, motion, yolo)")

    args = parser.parse_args()
    if args.detector:
        os.environ["ARGUS_DETECTOR"] = args.detector

    run_headless_camera(
        video_path=args.video,
        camera_id=args.camera_id,
        city=args.city,
        district=args.district,
        master_ip=args.master_ip,
        master_port=args.master_port,
        feed_id=args.feed_id,
        is_test=args.test
    )
