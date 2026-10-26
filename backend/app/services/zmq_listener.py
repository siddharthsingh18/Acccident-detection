import asyncio
import logging
import threading
import time
from typing import Optional
import cv2
from numpy import ndarray
import zmq

from ..config import settings
from ..models.schemas import Alert
from .broadcaster import get_alert_queue

logger = logging.getLogger("argus.zmq_listener")

class ZmqAlertListener(threading.Thread):
    """
    Background worker thread listening on the Argus Surveillance Alert port (10010).
    Replaces RunGui.py's WorkerThread:
      - Binds zmq.REP on tcp://{ZMQ_HOST}:{ZMQ_ALERT_PORT}
      - Receives Python-pickled messages via socket.recv_pyobj()
      - Responds immediately with socket.send_pyobj("") to release Master's REQ socket
      - Saves received crash_pic frame as JPEG thumbnail
      - Enqueues parsed Alert into asyncio.Queue for WebSocket broadcasting
      - Handles automatic reconnect/rebinding on errors
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, port: Optional[int] = None):
        super().__init__(daemon=True, name="ZmqAlertListener")
        self.loop = loop
        self.port = port or settings.ZMQ_ALERT_PORT
        self.host = settings.ZMQ_HOST
        self._stop_event = threading.Event()
        self.socket: Optional[zmq.Socket] = None
        self.context: Optional[zmq.Context] = None

    def stop(self) -> None:
        """Signal thread to stop and close ZeroMQ socket."""
        self._stop_event.set()
        if self.context:
            try:
                self.context.destroy(linger=0)
            except Exception:
                pass

    def run(self) -> None:
        logger.info(f"Starting ZmqAlertListener on tcp://{self.host}:{self.port}")
        bind_addr = f"tcp://{self.host}:{self.port}"

        while not self._stop_event.is_set():
            try:
                self.context = zmq.Context()
                self.socket = self.context.socket(zmq.REP)
                self.socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 sec timeout for clean stop check
                self.socket.setsockopt(zmq.LINGER, 0)
                self.socket.bind(bind_addr)
                logger.info(f"ZmqAlertListener bound successfully to {bind_addr}")

                while not self._stop_event.is_set():
                    try:
                        message = self.socket.recv_pyobj()
                    except zmq.Again:
                        continue  # Timeout, check stop_event
                    except zmq.ZMQError as ze:
                        if self._stop_event.is_set():
                            break
                        raise ze

                    # Send immediate REP reply so Argus SenderController releases
                    try:
                        self.socket.send_pyobj("")
                    except Exception as se:
                        logger.warning(f"Error sending REP reply: {se}")

                    # Process alert payload
                    self._handle_message(message)

            except Exception as e:
                if self._stop_event.is_set():
                    break
                logger.error(f"ZMQ listener error on {bind_addr}: {e}. Retrying in 2 seconds...", exc_info=False)
                if self.socket:
                    try:
                        self.socket.close(linger=0)
                    except Exception:
                        pass
                if self.context:
                    try:
                        self.context.term()
                    except Exception:
                        pass
                time.sleep(2.0)

        logger.info("ZmqAlertListener stopped")

    def _handle_message(self, message: dict) -> None:
        if not isinstance(message, dict):
            logger.warning(f"Received non-dict message: {type(message)}")
            return

        func = message.get("FUNCTION")
        if func != "NOTIFICATION":
            logger.debug(f"Ignoring message with function: {func}")
            return

        try:
            camera_id = int(message.get("CAMERA_ID", 0))
            frame_id = int(message.get("STARTING_FRAME_ID", 0))
            city = message.get("CITY")
            district = message.get("DISTRICT")
            crash_time = str(message.get("CRASH_TIME", ""))
            crash_pic = message.get("CRASH_PIC")

            incident_id = f"{camera_id}_{frame_id}"

            # Parse date and time components
            if " " in crash_time:
                date_part, time_part = crash_time.split(" ", 1)
            else:
                date_part = crash_time
                time_part = ""

            # Save thumbnail frame if available
            if isinstance(crash_pic, ndarray) and crash_pic.size > 0:
                thumb_path = settings.THUMBNAILS_DIR / f"{incident_id}.jpg"
                try:
                    cv2.imwrite(str(thumb_path), crash_pic)
                    logger.info(f"Saved crash thumbnail to {thumb_path}")
                except Exception as ex:
                    logger.error(f"Failed to save thumbnail: {ex}")

            alert = Alert(
                incident_id=incident_id,
                camera_id=camera_id,
                starting_frame_id=frame_id,
                date=date_part,
                time=time_part,
                city=city,
                district=district,
                thumbnail_url=f"/media/thumbnails/{incident_id}.jpg",
                video_url=f"/api/incidents/{incident_id}/video",
            )

            # Safely schedule put into asyncio.Queue
            self.loop.call_soon_threadsafe(self._enqueue_alert, alert)
            logger.info(f"Enqueued alert for incident {incident_id} ({city}, {district})")

        except Exception as e:
            logger.error(f"Error parsing NOTIFICATION message: {e}", exc_info=True)

    def _enqueue_alert(self, alert: Alert) -> None:
        try:
            get_alert_queue().put_nowait(alert)
        except Exception as e:
            logger.error(f"Failed to enqueue alert: {e}")
