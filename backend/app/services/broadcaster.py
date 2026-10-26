import asyncio
import logging
from typing import Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from ..models.schemas import Alert

logger = logging.getLogger("argus.broadcaster")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def _send_safe(self, websocket: WebSocket, message: str, timeout: float = 2.0) -> None:
        """Send message to a single client with strict timeout to prevent slow-client backpressure."""
        try:
            await asyncio.wait_for(websocket.send_text(message), timeout=timeout)
        except (asyncio.TimeoutError, WebSocketDisconnect, Exception) as e:
            logger.warning(f"Dropping slow/dead WebSocket client: {e}")
            await self.disconnect(websocket)

    async def broadcast(self, message: str) -> None:
        """Broadcast message to all connected clients concurrently without blocking."""
        async with self._lock:
            clients = list(self.active_connections)

        if not clients:
            return

        tasks = [asyncio.create_task(self._send_safe(ws, message)) for ws in clients]
        await asyncio.gather(*tasks, return_exceptions=True)

manager = ConnectionManager()
_alert_queue: Optional[asyncio.Queue] = None

def get_alert_queue() -> asyncio.Queue[Alert]:
    global _alert_queue
    if _alert_queue is None:
        _alert_queue = asyncio.Queue()
    return _alert_queue

def reset_alert_queue() -> asyncio.Queue[Alert]:
    global _alert_queue
    _alert_queue = asyncio.Queue()
    return _alert_queue

async def alert_broadcast_worker() -> None:
    """Async background worker pulling alerts from the queue and broadcasting to WebSocket clients."""
    logger.info("Alert broadcast worker started")
    queue = get_alert_queue()
    while True:
        try:
            alert = await queue.get()
            payload = alert.model_dump_json()
            await manager.broadcast(payload)
            queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error broadcasting alert: {e}", exc_info=True)
            await asyncio.sleep(0.1)
