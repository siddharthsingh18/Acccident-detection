import logging
import threading
from typing import Optional
import zmq

from System.Connections.protocol import (
    deserialize_message,
    serialize_reply
)
from System.Controller.JsonDecoder import JsonDecoder
from System.Data.CONSTANTS import BIND_HOST

logger = logging.getLogger("argus.receiver")


class ReceiverController(threading.Thread):
    """
    ZeroMQ REP listener node.
    Binds to 127.0.0.1 by default (configurable via ARGUS_BIND_HOST).
    Safely deserializes multipart JSON/JPEG messages and rejects unknown schema versions
    or malformed/pickled byte streams.
    """

    def __init__(self, port: int, type=None, read_file: bool = False, tf: bool = False, bind_host: Optional[str] = None):
        super().__init__(daemon=True, name=f"ReceiverController-{port}")
        self.port = int(port)
        self.type = type
        self.read_file = read_file
        self.tf = tf
        self.bind_host = bind_host or BIND_HOST
        self._stop_event = threading.Event()
        self.socket: Optional[zmq.Socket] = None
        self.context: Optional[zmq.Context] = None

    def stop(self):
        """Signal thread to stop and unbind socket."""
        self._stop_event.set()

    def run(self):
        bind_addr = f"tcp://{self.bind_host}:{self.port}"
        logger.info(f"Binding ReceiverController to {bind_addr}")

        self.context = zmq.Context.instance()
        self.socket = self.context.socket(zmq.REP)
        self.socket.setsockopt(zmq.RCVTIMEO, 250)  # 250ms timeout for clean stop checks
        self.socket.setsockopt(zmq.LINGER, 0)

        try:
            self.socket.bind(bind_addr)
        except zmq.ZMQError as ze:
            logger.error(f"Failed to bind {bind_addr}: {ze}")
            return

        jsonDecoder = JsonDecoder(type=self.type, read_file=self.read_file, tf=self.tf)

        while not self._stop_event.is_set():
            try:
                parts = self.socket.recv_multipart()
            except zmq.Again:
                continue
            except zmq.ZMQError:
                if self._stop_event.is_set():
                    break
                continue

            try:
                message = deserialize_message(parts)
                # Send immediate ACK reply
                self.socket.send_multipart(serialize_reply({"v": 1, "status": "ok"}))
                jsonDecoder.run(message)
            except Exception as e:
                logger.warning(f"Rejected malformed or unsupported message on {bind_addr}: {e}")
                try:
                    self.socket.send_multipart(serialize_reply({"v": 1, "status": "error", "error": str(e)}))
                except Exception:
                    pass

        try:
            self.socket.close(linger=0)
        except Exception:
            pass
