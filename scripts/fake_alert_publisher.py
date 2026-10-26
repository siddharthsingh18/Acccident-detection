#!/usr/bin/env python3
"""
Fake Argus ZeroMQ alert publisher.
Sends a simulated road crash alert to the FastAPI Bridge port 10010.
"""
import sys
import argparse
from pathlib import Path
import numpy as np
import zmq

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from System.Data.CONSTANTS import (
    FUNCTION, NOTIFICATION, CAMERA_ID, STARTING_FRAME_ID,
    CITY, DISTRICT, CRASH_TIME, CRASH_PIC
)

def send_alert(port=10010, camera_id=9876, frame_id=88, city="Cairo", district="District 1"):
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.RCVTIMEO, 3000)
    sock.setsockopt(zmq.SNDTIMEO, 3000)
    sock.connect(f"tcp://127.0.0.1:{port}")

    # Generate sample 100x100 RGB thumbnail
    pic = np.zeros((100, 100, 3), dtype=np.uint8)
    pic[:, :, 2] = 200  # Red tint

    msg = {
        FUNCTION: NOTIFICATION,
        CAMERA_ID: camera_id,
        STARTING_FRAME_ID: frame_id,
        CITY: city,
        DISTRICT: district,
        CRASH_TIME: "2026-10-27 12:34:56",
        CRASH_PIC: pic,
    }

    # Ensure sample incident video is available in backend/media/videos
    video_dir = ROOT_DIR / "backend" / "media" / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    video_target = video_dir / f"{camera_id}_{frame_id}.mp4"
    if not video_target.exists():
        sample_src = ROOT_DIR / "UI" / "liveFeed" / "1.mp4"
        if sample_src.exists():
            import subprocess
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(sample_src), "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video_target)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True
                )
            except Exception:
                import shutil
                shutil.copyfile(str(sample_src), str(video_target))


    try:
        sock.send_pyobj(msg)
        reply = sock.recv_pyobj()
        print(f"Sent fake alert for Camera {camera_id} ({city}). Reply: {reply}")
        return True

    except Exception as e:
        print(f"Failed to send alert: {e}")
        return False
    finally:
        sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=10010)
    parser.add_argument("--camera-id", type=int, default=9876)
    parser.add_argument("--city", default="Cairo")
    parser.add_argument("--district", default="District 1")
    args = parser.parse_args()

    success = send_alert(args.port, args.camera_id, 88, args.city, args.district)
    sys.exit(0 if success else 1)
