"""Health Check Routes for EchoDrive Control Plane."""

from fastapi import APIRouter
import time
from ..config.settings import settings
from ..voice.session_manager import session_manager

router = APIRouter(tags=["Health"])


@router.get("/health")
async def get_health():
    """Health check endpoint for service status, active sessions, and dependency readiness."""
    active_sessions = await session_manager.list_sessions()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "active_sessions_count": len(active_sessions),
        "timestamp": int(time.time()),
        "media_plane": {
            "agora_app_id_configured": bool(settings.AGORA_APP_ID),
            "agora_cert_configured": bool(settings.AGORA_APP_CERTIFICATE),
        },
    }
