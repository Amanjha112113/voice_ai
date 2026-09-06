"""Main Application Entry Point for EchoDrive FastAPI Control Plane."""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config.settings import settings
from .api.routes_health import router as health_router
from .api.routes_sessions import router as sessions_router
from .api.routes_ws import router as ws_router
from .api.routes_catalog import router as catalog_router
from .api.routes_leads import router as leads_router
from .api.routes_mcp import router as mcp_router
from .api.routes_tts import router as tts_router

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("echodrive")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan setup and teardown."""
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} environment...")
    logger.info(f"Agora App ID: {settings.AGORA_APP_ID[:8]}... (Certificate configured: {bool(settings.AGORA_APP_CERTIFICATE)})")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


def create_app() -> FastAPI:
    """Factory function creating configured FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Production-grade realtime conversational voice AI sales agent for automotive dealerships.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API Routers
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(ws_router)
    app.include_router(catalog_router)
    app.include_router(leads_router)
    app.include_router(mcp_router)
    app.include_router(tts_router)

    # Static index route for the Interactive Voice Console
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def get_index():
        index_file = os.path.join(static_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "EchoDrive Voice Runtime API is running. Visit /health or /sessions"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
