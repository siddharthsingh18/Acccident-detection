import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services.broadcaster import manager

logger = logging.getLogger("argus.websocket")
router = APIRouter(tags=["websockets"])

@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint broadcasting real-time incident alerts to web clients.
    Replaces RunGui.py WorkerThread reception with live browser push.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and accept heartbeat ping/pongs from frontend
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
        await manager.disconnect(websocket)
