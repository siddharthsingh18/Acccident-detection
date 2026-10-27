import logging
import threading
import time
from typing import Any, Dict, List, Optional
import zmq

from System.Connections.protocol import serialize_message, deserialize_reply

logger = logging.getLogger("argus.sender")


class ZmqSocketPool:
    """
    Thread-safe connection pool and Lazy Pirate client for ZeroMQ REQ sockets.
    Reuses persistent sockets, prevents file-descriptor leaks, and implements
    timeout and retry backoff so dropped nodes never deadlock the caller.
    """
    _instance: Optional["ZmqSocketPool"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.context = zmq.Context.instance()
        self._sockets: Dict[str, List[zmq.Socket]] = {}
        self._pool_lock = threading.Lock()
        self._is_closed = False

    @classmethod
    def get_instance(cls) -> "ZmqSocketPool":
        with cls._lock:
            if cls._instance is None or cls._instance._is_closed:
                cls._instance = cls()
            return cls._instance

    def _create_socket(self, endpoint: str, timeout_ms: int) -> zmq.Socket:
        sock = self.context.socket(zmq.REQ)
        sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
        sock.setsockopt(zmq.SNDTIMEO, timeout_ms)
        sock.setsockopt(zmq.LINGER, 0)
        sock.connect(endpoint)
        return sock

    def acquire_socket(self, endpoint: str, timeout_ms: int) -> zmq.Socket:
        with self._pool_lock:
            if self._is_closed:
                raise RuntimeError("ZmqSocketPool has been shut down")
            pool = self._sockets.setdefault(endpoint, [])
            if pool:
                return pool.pop()
        return self._create_socket(endpoint, timeout_ms)

    def release_socket(self, endpoint: str, sock: zmq.Socket, discard: bool = False):
        if discard:
            try:
                sock.close(linger=0)
            except Exception:
                pass
            return

        with self._pool_lock:
            if self._is_closed:
                try:
                    sock.close(linger=0)
                except Exception:
                    pass
                return
            pool = self._sockets.setdefault(endpoint, [])
            # Keep up to 8 idle sockets per endpoint
            if len(pool) < 8:
                pool.append(sock)
            else:
                try:
                    sock.close(linger=0)
                except Exception:
                    pass

    def send_request(
        self,
        ip: str,
        port: int,
        msg: Dict[str, Any],
        timeout_ms: int = 1500,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Sends request message using the Lazy Pirate pattern:
        retries with exponential backoff and discards dead sockets.
        """
        endpoint = f"tcp://{ip}:{port}"
        payload = serialize_message(msg)

        retries_left = max_retries
        backoff = 0.05

        while retries_left > 0:
            sock = self.acquire_socket(endpoint, timeout_ms)
            try:
                sock.send_multipart(payload)
                reply_parts = sock.recv_multipart()
                reply = deserialize_reply(reply_parts)
                self.release_socket(endpoint, sock, discard=False)
                return reply
            except (zmq.Again, zmq.ZMQError) as e:
                # Socket is out-of-sync or dead: discard and recreate
                self.release_socket(endpoint, sock, discard=True)
                retries_left -= 1
                if retries_left > 0:
                    time.sleep(backoff)
                    backoff *= 2.0
                else:
                    logger.warning(
                        f"ZeroMQ send to {endpoint} timed out or failed after {max_retries} attempts: {e}"
                    )
                    return None
            except Exception as ex:
                self.release_socket(endpoint, sock, discard=True)
                logger.error(f"Unexpected error sending to {endpoint}: {ex}")
                return None

        return None

    def close_all(self):
        """Cleanly close all pooled sockets."""
        with self._pool_lock:
            self._is_closed = True
            for endpoint, pool in self._sockets.items():
                for sock in pool:
                    try:
                        sock.close(linger=0)
                    except Exception:
                        pass
                pool.clear()
            self._sockets.clear()


class SenderController(threading.Thread):
    """
    Drop-in replacement for legacy SenderController.
    Uses shared ZmqSocketPool to eliminate thread and socket exhaustion.
    """

    def __init__(self, ip: str, port: int, msg: Dict[str, Any]):
        super().__init__(daemon=True, name="SenderController")
        self.ip = str(ip)
        self.port = int(port)
        self.msg = msg
        self.result = None

    def run(self):
        pool = ZmqSocketPool.get_instance()
        self.result = pool.send_request(self.ip, self.port, self.msg)
