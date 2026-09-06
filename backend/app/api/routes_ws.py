"""WebSocket Telemetry Event Feed for EchoDrive Dashboard.

NOTE: This WebSocket is for telemetry and transcript dashboard monitoring only.
It is NOT the primary realtime audio transport (Agora RTC handles media).
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import logging
from typing import Set

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


class DashboardConnectionManager:
    """Manages active dashboard WebSocket subscribers."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Dashboard client connected (total: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info(f"Dashboard client disconnected (total: {len(self.active_connections)})")

    async def broadcast_event(self, event_type: str, session_id: str, payload: dict) -> None:
        """Broadcast a structured JSON telemetry event to all connected dashboards."""
        if not self.active_connections:
            return

        message = json.dumps({
            "type": event_type,
            "session_id": session_id,
            "payload": payload,
        })

        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.add(connection)

        for dead in dead_connections:
            self.disconnect(dead)


dashboard_manager = DashboardConnectionManager()


@router.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket):
    """Realtime dashboard event stream."""
    await dashboard_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; receive client ping
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        dashboard_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"Dashboard WebSocket connection error: {e}")
        dashboard_manager.disconnect(websocket)
