import json
import threading
import time
import numpy as np
import zmq
from app.config import settings

def test_zmq_to_websocket_alert_pipeline(client):
    """
    Test ZeroMQ Alert Listener -> asyncio Queue -> WebSocket broadcaster.
    Simulates Argus Master sending a NOTIFICATION message over ZeroMQ REQ/REP socket
    and verifies that the connected WebSocket client receives the parsed JSON alert.
    """
    # 1. Connect WebSocket client
    with client.websocket_connect("/ws/alerts") as ws:
        # Send heartbeat ping to verify active WebSocket connection
        ws.send_text("ping")
        assert ws.receive_text() == "pong"

        # 2. Setup mock ZeroMQ client (simulating Master.py SenderController)
        from System.Connections.protocol import serialize_message, deserialize_reply
        context = zmq.Context()
        req_socket = context.socket(zmq.REQ)
        req_socket.RCVTIMEO = 4000
        req_socket.SNDTIMEO = 4000
        req_socket.connect(f"tcp://127.0.0.1:{settings.ZMQ_ALERT_PORT}")

        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        alert_msg = {
            "FUNCTION": "NOTIFICATION",
            "CAMERA_ID": 9999,
            "STARTING_FRAME_ID": 42,
            "CITY": "Alexandria",
            "DISTRICT": "District 5",
            "CRASH_TIME": "2026-10-27 12:00:00",
            "CRASH_PIC": dummy_frame,
        }

        # Send alert in a background thread or directly
        def send_alert():
            payload = serialize_message(alert_msg)
            req_socket.send_multipart(payload)
            reply_parts = req_socket.recv_multipart()
            reply = deserialize_reply(reply_parts)
            assert reply.get("status") == "ok"

        sender_thread = threading.Thread(target=send_alert)
        sender_thread.start()
        sender_thread.join(timeout=3.0)
        req_socket.close()
        context.term()

        # 3. Assert WebSocket client receives broadcasted Alert
        raw_msg = ws.receive_text()
        alert_data = json.loads(raw_msg)

        assert alert_data["incident_id"] == "9999_42"
        assert alert_data["camera_id"] == 9999
        assert alert_data["starting_frame_id"] == 42
        assert alert_data["city"] == "Alexandria"
        assert alert_data["district"] == "District 5"
        assert alert_data["date"] == "2026-10-27"
        assert alert_data["time"] == "12:00:00"
        assert alert_data["thumbnail_url"] == "/media/thumbnails/9999_42.jpg"
        assert alert_data["video_url"] == "/api/incidents/9999_42/video"

        # 4. Verify thumbnail was written to disk
        thumb_path = settings.THUMBNAILS_DIR / "9999_42.jpg"
        assert thumb_path.exists()


def test_zmq_to_websocket_alert_with_model_scores(client):
    """
    Verify that when Master/Crashing sends MODEL_SCORES in NOTIFICATION,
    the alert listener deserializes it and WebSocket clients receive the breakdown.
    """
    with client.websocket_connect("/ws/alerts") as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"

        from System.Connections.protocol import serialize_message, deserialize_reply
        context = zmq.Context()
        req_socket = context.socket(zmq.REQ)
        req_socket.RCVTIMEO = 4000
        req_socket.SNDTIMEO = 4000
        req_socket.connect(f"tcp://127.0.0.1:{settings.ZMQ_ALERT_PORT}")

        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        scores_payload = {
            "policy": "majority",
            "threshold": 0.65,
            "decision": True,
            "scorers": [
                {
                    "name": "vif_svm",
                    "score": 0.88,
                    "fired": True,
                    "calibrated": True,
                    "available": True,
                    "latency_ms": 14.0,
                    "reason_unavailable": None,
                },
                {
                    "name": "convae",
                    "score": 0.72,
                    "fired": True,
                    "calibrated": False,
                    "available": True,
                    "latency_ms": 32.5,
                    "reason_unavailable": None,
                },
            ],
        }

        alert_msg = {
            "FUNCTION": "NOTIFICATION",
            "CAMERA_ID": 8888,
            "STARTING_FRAME_ID": 99,
            "CITY": "Cairo",
            "DISTRICT": "District 1",
            "CRASH_TIME": "2026-11-01 10:30:00",
            "CRASH_PIC": dummy_frame,
            "MODEL_SCORES": scores_payload,
        }

        def send_alert():
            payload = serialize_message(alert_msg)
            req_socket.send_multipart(payload)
            reply_parts = req_socket.recv_multipart()
            reply = deserialize_reply(reply_parts)
            assert reply.get("status") == "ok"

        sender_thread = threading.Thread(target=send_alert)
        sender_thread.start()
        sender_thread.join(timeout=3.0)
        req_socket.close()
        context.term()

        raw_msg = ws.receive_text()
        alert_data = json.loads(raw_msg)

        assert alert_data["incident_id"] == "8888_99"
        assert alert_data["model_scores"] is not None
        assert alert_data["model_scores"]["policy"] == "majority"
        assert alert_data["model_scores"]["decision"] is True
        assert len(alert_data["model_scores"]["scorers"]) == 2
        assert alert_data["model_scores"]["scorers"][0]["name"] == "vif_svm"
        assert alert_data["model_scores"]["scorers"][0]["score"] == 0.88
