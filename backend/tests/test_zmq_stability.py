import os
import pickle
import threading
import time
import numpy as np
import pytest
import zmq

from System.Connections.SenderController import ZmqSocketPool
from System.Connections.ReceiverController import ReceiverController
from System.Connections.protocol import (
    serialize_message,
    deserialize_message,
    serialize_reply,
    deserialize_reply,
    SCHEMA_VERSION,
)
from System.Data.CONSTANTS import FUNCTION, NOTIFICATION, CAMERA_ID, STARTING_FRAME_ID

_EXPLOIT_EXECUTED = False


def _malicious_callback():
    global _EXPLOIT_EXECUTED
    _EXPLOIT_EXECUTED = True


class MaliciousPayload:
    def __reduce__(self):
        return (_malicious_callback, ())


def get_fd_count() -> int:
    """Return count of currently open file descriptors."""
    if os.path.exists("/dev/fd"):
        return len(os.listdir("/dev/fd"))
    try:
        import resource
        return resource.getrlimit(resource.RLIMIT_NOFILE)[0]
    except Exception:
        return 0


def test_zmq_soak_10000_messages_flat_file_descriptors():
    """
    Soak test: Send 10,000 requests via ZmqSocketPool to assert persistent socket reuse
    and verify zero file-descriptor leaks.
    """
    port = 28901
    ctx = zmq.Context.instance()
    rep = ctx.socket(zmq.REP)
    rep.setsockopt(zmq.RCVTIMEO, 250)
    rep.setsockopt(zmq.LINGER, 0)
    rep.bind(f"tcp://127.0.0.1:{port}")

    stop_server = threading.Event()

    def echo_worker():
        while not stop_server.is_set():
            try:
                parts = rep.recv_multipart()
                rep.send_multipart(serialize_reply({"v": 1, "status": "ok"}))
            except zmq.Again:
                continue
            except Exception:
                break
        rep.close(linger=0)

    worker_thread = threading.Thread(target=echo_worker, daemon=True)
    worker_thread.start()

    pool = ZmqSocketPool.get_instance()

    # Warm up connection pool
    for i in range(10):
        res = pool.send_request("127.0.0.1", port, {"FUNCTION": "PING", "seq": i})
        assert res is not None

    baseline_fds = get_fd_count()

    # Soak test: 10,000 requests
    for i in range(10000):
        res = pool.send_request("127.0.0.1", port, {"FUNCTION": "PING", "seq": i})
        assert res is not None
        assert res.get("status") == "ok"

    final_fds = get_fd_count()

    stop_server.set()
    worker_thread.join(timeout=2.0)

    # Assert flat file descriptors (allow at most 2 for transient OS buffers)
    fd_delta = final_fds - baseline_fds
    assert fd_delta <= 2, f"File descriptor leak detected: baseline={baseline_fds}, final={final_fds}, delta={fd_delta}"


def test_zmq_kill_node_midstream_and_recover():
    """
    Resilience test: Kill a receiver node mid-stream.
    Assert that the sender does not deadlock, times out cleanly with backoff,
    and automatically recovers once the node restarts.
    """
    port = 28902
    ctx = zmq.Context.instance()

    def make_server():
        sock = ctx.socket(zmq.REP)
        sock.setsockopt(zmq.RCVTIMEO, 100)
        sock.setsockopt(zmq.LINGER, 0)
        sock.bind(f"tcp://127.0.0.1:{port}")
        stop_evt = threading.Event()

        def loop():
            while not stop_evt.is_set():
                try:
                    parts = sock.recv_multipart()
                    sock.send_multipart(serialize_reply({"v": 1, "status": "ok"}))
                except zmq.Again:
                    continue
                except Exception:
                    break
            sock.close(linger=0)

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        return stop_evt, t

    stop1, t1 = make_server()
    pool = ZmqSocketPool.get_instance()

    # 1. Normal communication succeeds
    res1 = pool.send_request("127.0.0.1", port, {"FUNCTION": "HEARTBEAT"}, timeout_ms=300, max_retries=2)
    assert res1 is not None
    assert res1.get("status") == "ok"

    # 2. Kill the node mid-stream
    stop1.set()
    t1.join(timeout=1.0)
    time.sleep(0.05)

    # 3. Pipeline must not hang or deadlock; returns None after retries
    t_start = time.time()
    fail_res = pool.send_request("127.0.0.1", port, {"FUNCTION": "HEARTBEAT"}, timeout_ms=200, max_retries=2)
    elapsed = time.time() - t_start
    assert fail_res is None
    assert elapsed < 3.0, f"Request took too long to timeout: {elapsed:.2f}s"

    # 4. Restart the node
    stop2, t2 = make_server()
    time.sleep(0.05)

    # 5. Subsequent request must recover cleanly
    res_recovered = pool.send_request("127.0.0.1", port, {"FUNCTION": "HEARTBEAT"}, timeout_ms=500, max_retries=2)
    assert res_recovered is not None
    assert res_recovered.get("status") == "ok"

    stop2.set()
    t2.join(timeout=1.0)


def test_zmq_reject_malformed_and_pickled_payloads_without_code_execution():
    """
    Security test: Assert that pickled payloads, invalid schema versions, and corrupted
    buffers are strictly rejected without executing arbitrary code.
    """
    global _EXPLOIT_EXECUTED
    _EXPLOIT_EXECUTED = False

    pickled_exploit = pickle.dumps(MaliciousPayload())
    assert not _EXPLOIT_EXECUTED, "Exploit triggered during dump"

    # 1. Direct deserialize_message must reject pickled payload
    with pytest.raises(ValueError, match="Malformed or non-JSON message header"):
        deserialize_message([pickled_exploit])

    assert not _EXPLOIT_EXECUTED, "SECURITY VULNERABILITY: Pickled payload was executed!"

    # 2. Reject missing or invalid schema version
    with pytest.raises(ValueError, match="Unsupported or missing schema version"):
        deserialize_message([b'{"action": "test"}'])

    with pytest.raises(ValueError, match="Unsupported or missing schema version"):
        deserialize_message([b'{"v": 999, "action": "test"}'])

    # 3. Reject corrupted image bytes
    with pytest.raises(ValueError, match="Corrupted JPEG byte stream"):
        deserialize_message([b'{"v": 1, "frame_count": 1}', b"not-a-valid-jpeg-image"])

    # 4. Live socket test: send pickled payload to ReceiverController
    receiver_port = 28903
    receiver = ReceiverController(port=receiver_port)
    receiver.start()
    time.sleep(0.1)

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.RCVTIMEO, 1500)
    sock.setsockopt(zmq.SNDTIMEO, 1500)
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(f"tcp://127.0.0.1:{receiver_port}")

    try:
        # Send pickled exploit over socket
        sock.send_multipart([pickled_exploit])
        reply_parts = sock.recv_multipart()
        reply = deserialize_reply(reply_parts)

        assert reply.get("status") == "error"
        assert not _EXPLOIT_EXECUTED, "SECURITY VULNERABILITY: Exploit executed on ReceiverController!"

        # Receiver should still be alive and process a valid message
        valid_msg = {"FUNCTION": "TEST", "CAMERA_ID": 100}
        sock.send_multipart(serialize_message(valid_msg))
        valid_reply = deserialize_reply(sock.recv_multipart())
        assert valid_reply.get("status") == "ok"

    finally:
        sock.close(linger=0)
        receiver.stop()
        receiver.join(timeout=1.0)
