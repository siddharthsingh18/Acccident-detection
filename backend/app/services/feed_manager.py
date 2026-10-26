import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np
from fastapi import HTTPException

from app.config import settings, BACKEND_DIR
from app.models.schemas import FeedResponse, FeedProgress, FeedCancelResponse

logger = logging.getLogger("argus.feeds")

class FeedItem:
    def __init__(self, feed_id: str, camera_id: int, city: str, district: str, video_path: Path, thumbnail_path: Path):
        self.feed_id = feed_id
        self.camera_id = camera_id
        self.city = city
        self.district = district
        self.video_path = video_path
        self.thumbnail_path = thumbnail_path
        self.status = "queued"  # queued, processing, done, failed, cancelled
        self.frames_sent = 0
        self.total_frames = 0
        self.percent = 0.0
        self.error: Optional[str] = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.process: Optional[subprocess.Popen] = None
        self.reader_thread: Optional[threading.Thread] = None

    def to_response(self) -> FeedResponse:
        return FeedResponse(
            id=self.feed_id,
            camera_id=self.camera_id,
            city=self.city,
            district=self.district,
            status=self.status,
            progress=FeedProgress(
                frames_sent=self.frames_sent,
                total_frames=self.total_frames,
                percent=self.percent
            ),
            thumbnail_url=f"/api/feeds/{self.feed_id}/thumbnail",
            error=self.error,
            created_at=self.created_at
        )


class FeedManager:
    def __init__(self):
        self.feeds: Dict[str, FeedItem] = {}
        self.active_feed_id: Optional[str] = None

    def reset(self):
        """Cancel any running feeds and clear state (useful for tests)."""
        if self.active_feed_id:
            item = self.feeds.get(self.active_feed_id)
            if item and item.process and item.process.poll() is None:
                try:
                    item.process.terminate()
                    item.process.wait(timeout=1)
                except Exception:
                    pass
        self.active_feed_id = None
        self.feeds.clear()

    def validate_video_file(self, file_path: Path) -> dict:
        """
        Validate video file size, extension, and container/streams with ffprobe.
        """
        if not file_path.exists():
            raise HTTPException(status_code=400, detail="Uploaded file not found.")

        ext = file_path.suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        file_size = file_path.stat().st_size
        if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB"
            )

        # Inspect container and video stream using ffprobe
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration,format_name:stream=codec_type,codec_name,nb_frames,width,height",
            "-of", "json",
            str(file_path)
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if res.returncode != 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid or corrupted video content: {res.stderr.strip() or 'ffprobe failed'}"
                )
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            video_streams = [s for s in streams if s.get("codec_type") == "video"]
            if not video_streams:
                raise HTTPException(status_code=400, detail="No valid video stream found in uploaded media.")
            return {
                "duration": float(data.get("format", {}).get("duration", 0) or 0),
                "stream": video_streams[0]
            }
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=400, detail="ffprobe inspection timed out on uploaded file.")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Failed to parse ffprobe output.")

    def create_thumbnail_with_overlay(self, video_path: Path, output_path: Path) -> Path:
        """
        Extract frame 0 and apply the play-button overlay (matching RunCamera.py logic).
        """
        cap = cv2.VideoCapture(str(video_path))
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            raise HTTPException(status_code=400, detail="Could not extract video frame for thumbnail.")

        img = cv2.resize(frame, (351, 241), interpolation=cv2.INTER_AREA)

        play_button_path = settings.PLAY_BUTTON_PATH
        if play_button_path.exists():
            button = cv2.imread(str(play_button_path))
            button = cv2.resize(button, (111, 111), interpolation=cv2.INTER_AREA)
            height_needed = 241 - button.shape[0]
            width_needed = 351 - button.shape[1]
            top = int(np.floor(height_needed / 2))
            bottom = int(np.ceil(height_needed / 2))
            left = int(np.floor(width_needed / 2))
            right = int(np.ceil(width_needed / 2))
            border = cv2.copyMakeBorder(button, top=top, bottom=bottom, left=left, right=right, borderType=cv2.BORDER_CONSTANT, value=0)
            border = np.where(border < 150, img, border)
            final_thumb = cv2.resize(border, (559, 300), interpolation=cv2.INTER_AREA)
        else:
            final_thumb = cv2.resize(img, (559, 300), interpolation=cv2.INTER_AREA)
            h, w = final_thumb.shape[:2]
            center = (w // 2, h // 2)
            cv2.circle(final_thumb, center, 35, (0, 0, 0), -1)
            cv2.circle(final_thumb, center, 35, (255, 255, 255), 2)
            pts = np.array([[center[0] - 10, center[1] - 18], [center[0] - 10, center[1] + 18], [center[0] + 18, center[1]]], np.int32)
            cv2.fillPoly(final_thumb, [pts], (255, 255, 255))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), final_thumb)
        return output_path

    async def start_feed(self, file_path: Path, camera_id: int, city: str, district: str) -> FeedResponse:
        # Check if an active feed is currently running
        if self.active_feed_id:
            active_item = self.feeds.get(self.active_feed_id)
            if active_item and active_item.status in ("queued", "processing"):
                if active_item.process and active_item.process.poll() is None:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Camera feed {self.active_feed_id} is currently running. Only one active feed is allowed at a time."
                    )
                else:
                    active_item.status = "done"
                    self.active_feed_id = None

        feed_id = str(uuid.uuid4())
        thumbnail_path = settings.FEEDS_DIR / f"{feed_id}_thumb.jpg"
        self.create_thumbnail_with_overlay(file_path, thumbnail_path)

        feed_item = FeedItem(
            feed_id=feed_id,
            camera_id=camera_id,
            city=city,
            district=district,
            video_path=file_path,
            thumbnail_path=thumbnail_path
        )
        self.feeds[feed_id] = feed_item
        self.active_feed_id = feed_id

        # Launch worker in a separate subprocess
        worker_script = BACKEND_DIR / "app" / "services" / "camera_worker.py"
        cmd = [
            sys.executable,
            str(worker_script),
            "--video", str(file_path),
            "--camera-id", str(camera_id),
            "--city", city,
            "--district", district,
            "--master-ip", settings.ZMQ_HOST,
            "--master-port", str(settings.ZMQ_MASTER_PORT)
        ]

        logger.info(f"Starting camera worker subprocess for feed {feed_id}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        feed_item.process = process
        feed_item.status = "processing"

        # Daemon thread for stdout monitoring (avoids blocking loop or thread pool on exit)
        t = threading.Thread(target=self._monitor_feed_process, args=(feed_item,), daemon=True)
        feed_item.reader_thread = t
        t.start()

        return feed_item.to_response()

    def _monitor_feed_process(self, feed_item: FeedItem):
        """Daemon thread reading stdout from camera worker and tracking progress."""
        if not feed_item.process or not feed_item.process.stdout:
            return

        for line in iter(feed_item.process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            if line.startswith("PROGRESS:"):
                parts = line.split(":")
                if len(parts) >= 3:
                    try:
                        feed_item.frames_sent = int(parts[1])
                        feed_item.total_frames = int(parts[2])
                        if feed_item.total_frames > 0:
                            feed_item.percent = round(min(100.0, (feed_item.frames_sent / feed_item.total_frames) * 100), 1)
                    except ValueError:
                        pass
            elif line.startswith("STATUS:"):
                parts = line.split(":")
                status_val = parts[1].lower()
                if status_val in ("done", "cancelled", "failed", "processing"):
                    feed_item.status = status_val
                    if status_val == "done":
                        feed_item.percent = 100.0
            elif line.startswith("ERROR:"):
                feed_item.error = line[6:].strip()
                feed_item.status = "failed"

        returncode = feed_item.process.wait()
        if returncode != 0 and feed_item.status != "cancelled":
            feed_item.status = "failed"
            stderr_out = feed_item.process.stderr.read().strip() if feed_item.process.stderr else ""
            if stderr_out and not feed_item.error:
                feed_item.error = stderr_out

        if feed_item.status == "processing":
            feed_item.status = "done"
            feed_item.percent = 100.0

        if self.active_feed_id == feed_item.feed_id:
            self.active_feed_id = None

        logger.info(f"Feed {feed_item.feed_id} finished with status '{feed_item.status}'")
        self._cleanup_feed_video(feed_item)

    def _cleanup_feed_video(self, feed_item: FeedItem):
        """Clean up uploaded video file while keeping thumbnail and metadata."""
        try:
            if feed_item.video_path.exists():
                feed_item.video_path.unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to remove uploaded feed file {feed_item.video_path}: {e}")

    def get_feed(self, feed_id: str) -> FeedResponse:
        item = self.feeds.get(feed_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Feed '{feed_id}' not found.")
        return item.to_response()

    def get_thumbnail_path(self, feed_id: str) -> Path:
        item = self.feeds.get(feed_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Feed '{feed_id}' not found.")
        if item.thumbnail_path.exists():
            return item.thumbnail_path
        return settings.FALLBACK_IMAGE_PATH

    async def cancel_feed(self, feed_id: str) -> FeedCancelResponse:
        item = self.feeds.get(feed_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Feed '{feed_id}' not found.")

        if item.status in ("queued", "processing") and item.process:
            try:
                item.process.terminate()
                try:
                    item.process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    item.process.kill()
            except Exception as e:
                logger.warning(f"Error terminating process for feed {feed_id}: {e}")

            item.status = "cancelled"
            if self.active_feed_id == feed_id:
                self.active_feed_id = None

            self._cleanup_feed_video(item)
            return FeedCancelResponse(id=feed_id, status="cancelled", message="Feed cancelled successfully.")

        return FeedCancelResponse(
            id=feed_id,
            status=item.status,
            message=f"Feed already in terminal status '{item.status}'."
        )

# Global FeedManager instance
feed_manager = FeedManager()
