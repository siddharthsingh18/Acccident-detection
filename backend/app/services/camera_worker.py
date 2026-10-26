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
        socket_zmq.connect(f"tcp://{master_ip}:{master_port}")
        socket_zmq.send_pyobj(msg)
        socket_zmq.recv_pyobj()
    except Exception:
        pass
    finally:
        socket_zmq.close()

def run_headless_camera(video_path: str, camera_id: int, city: str, district: str, master_ip: str = "127.0.0.1", master_port: int = 10000):
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

    stem = video_file.stem
    box_path = PROJECT_ROOT / "boxes" / f"{stem}.txt"
    file_boxes = []
    has_boxes = False
    if box_path.exists():
        try:
            file_boxes = loadFile(str(video_file))
            has_boxes = True
        except Exception:
            file_boxes = []

    frame_width = 480
    frame_height = 360
    no_of_frames = 0
    frames = []

    print(f"STATUS:PROCESSING:0:{total_frames}", flush=True)

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
            if has_boxes and 0 <= box_index < len(file_boxes):
                boxes = file_boxes[box_index]
            else:
                boxes = []

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
                DISTRICT: district
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

    if running:
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

    args = parser.parse_args()
    run_headless_camera(
        video_path=args.video,
        camera_id=args.camera_id,
        city=args.city,
        district=args.district,
        master_ip=args.master_ip,
        master_port=args.master_port
    )
