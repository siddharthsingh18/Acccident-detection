import json
import logging
from typing import Any, Dict, List, Optional
import cv2
import numpy as np

from System.Data.CONSTANTS import FRAMES, CRASH_PIC, TRACKERS

logger = logging.getLogger("argus.protocol")

SCHEMA_VERSION = 1


def serialize_message(msg: Dict[str, Any]) -> List[bytes]:
    """
    Serializes a message dictionary into ZeroMQ multipart byte buffers.
    Part 0: UTF-8 encoded JSON header containing metadata and schema version {"v": 1}.
    Parts 1..N: JPEG-encoded byte buffers for video frames.
    Last Part (optional): JPEG-encoded crash thumbnail frame.
    """
    if not isinstance(msg, dict):
        raise TypeError(f"Message must be a dictionary, got {type(msg)}")

    header = {}
    frame_bytes_list: List[bytes] = []
    crash_pic_bytes: Optional[bytes] = None

    for k, v in msg.items():
        if k == FRAMES and isinstance(v, (list, tuple)):
            header["frame_count"] = len(v)
            for frame in v:
                if isinstance(frame, np.ndarray):
                    success, enc = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    if success:
                        frame_bytes_list.append(enc.tobytes())
                    else:
                        raise ValueError("Failed to JPEG-encode frame")
                elif isinstance(frame, bytes):
                    frame_bytes_list.append(frame)
                else:
                    raise TypeError(f"Unsupported frame type in FRAMES: {type(frame)}")

        elif k == CRASH_PIC and isinstance(v, np.ndarray):
            header["has_crash_pic"] = True
            success, enc = cv2.imencode(".jpg", v, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if success:
                crash_pic_bytes = enc.tobytes()
            else:
                raise ValueError("Failed to JPEG-encode crash_pic")

        elif k == TRACKERS and isinstance(v, (list, tuple)):
            serialized_trackers = []
            for item in v:
                if hasattr(item, "to_dict"):
                    serialized_trackers.append(item.to_dict())
                elif isinstance(item, dict):
                    serialized_trackers.append(item)
                else:
                    serialized_trackers.append(str(item))
            header[TRACKERS] = serialized_trackers

        else:
            # Preserve metadata (numbers, strings, booleans, lists of numbers)
            header[k] = v

    header["v"] = SCHEMA_VERSION
    header_bytes = json.dumps(header).encode("utf-8")

    parts = [header_bytes]
    parts.extend(frame_bytes_list)
    if crash_pic_bytes is not None:
        parts.append(crash_pic_bytes)

    return parts


def deserialize_message(parts: List[bytes]) -> Dict[str, Any]:
    """
    Safely deserializes ZeroMQ multipart byte buffers into a message dictionary.
    Guarantees that no arbitrary code execution or unpickling is ever performed.
    Rejects unknown schema versions and malformed byte sequences.
    """
    if not parts or len(parts) == 0:
        raise ValueError("Cannot deserialize empty multipart message")

    header_part = parts[0]
    try:
        header_text = header_part.decode("utf-8")
        header = json.loads(header_text)
    except Exception as e:
        raise ValueError(f"Malformed or non-JSON message header: {str(e)}")

    if not isinstance(header, dict):
        raise ValueError(f"Decoded header is not a dictionary: {type(header)}")

    version = header.get("v")
    if version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported or missing schema version '{version}'. Expected {SCHEMA_VERSION}")

    msg = dict(header)

    # Reconstruct FRAMES
    frame_count = header.get("frame_count", 0)
    if frame_count > 0:
        frames = []
        for i in range(1, 1 + frame_count):
            if i >= len(parts):
                raise ValueError(f"Multipart frame count mismatch: expected {frame_count}, got {len(parts) - 1}")
            img_buf = np.frombuffer(parts[i], dtype=np.uint8)
            frame = cv2.imdecode(img_buf, cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError(f"Corrupted JPEG byte stream for frame index {i - 1}")
            frames.append(frame)
        msg[FRAMES] = frames

    # Reconstruct CRASH_PIC
    if header.get("has_crash_pic", False):
        crash_pic_idx = 1 + frame_count
        if crash_pic_idx < len(parts):
            img_buf = np.frombuffer(parts[crash_pic_idx], dtype=np.uint8)
            crash_pic = cv2.imdecode(img_buf, cv2.IMREAD_COLOR)
            msg[CRASH_PIC] = crash_pic

    # Reconstruct TRACKERS
    if TRACKERS in header and isinstance(header[TRACKERS], list):
        try:
            from Mosse_Tracker.TrackerManager import Tracker
            reconstructed_trackers = []
            for item in header[TRACKERS]:
                if isinstance(item, dict):
                    reconstructed_trackers.append(Tracker.from_dict(item))
                else:
                    reconstructed_trackers.append(item)
            msg[TRACKERS] = reconstructed_trackers
        except Exception as ex:
            logger.warning(f"Tracker deserialization fallback: {ex}")

    return msg


def serialize_reply(reply: Dict[str, Any]) -> List[bytes]:
    """Serialize a worker acknowledgment reply dictionary."""
    reply_copy = dict(reply)
    reply_copy["v"] = SCHEMA_VERSION
    return [json.dumps(reply_copy).encode("utf-8")]


def deserialize_reply(parts: List[bytes]) -> Dict[str, Any]:
    """Deserialize a worker acknowledgment reply."""
    if not parts or len(parts) == 0:
        return {"v": SCHEMA_VERSION, "status": "ok"}
    try:
        reply = json.loads(parts[0].decode("utf-8"))
        if not isinstance(reply, dict):
            return {"v": SCHEMA_VERSION, "status": "ok"}
        if reply.get("v") != SCHEMA_VERSION:
            raise ValueError(f"Invalid reply schema version: {reply.get('v')}")
        return reply
    except Exception as e:
        raise ValueError(f"Malformed reply: {e}")
