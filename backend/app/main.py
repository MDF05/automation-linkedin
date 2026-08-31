"""
LinkedIn Automation Bot — FastAPI application entry point.

Menyatukan semua router, middleware CORS, lifespan events (device monitor,
scheduler), dan static file serving untuk screenshots.

Requirements: semua requirement
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global service instances (accessible by routers via import)
# ---------------------------------------------------------------------------
scheduler_service = None  # initialised in lifespan


# ---------------------------------------------------------------------------
# Lifespan — startup & shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Startup:
    - Mulai APScheduler
    - Mulai device monitor background task

    Shutdown:
    - Hentikan scheduler dan device monitor
    """
    global scheduler_service

    settings = get_settings()

    # ── Device monitor ────────────────────────────────────────────────
    device_monitor_task = None
    try:
        from app.core.websocket_manager import manager as ws_manager
        from app.services.device_monitor import DeviceMonitor, DeviceEvent

        async def _device_broadcaster(event: DeviceEvent) -> None:
            await ws_manager.broadcast("device_status", {
                "event_type": event.event_type.value,
                "device_id": event.device_id,
                "state": event.state.value,
                "message": event.message,
                "timestamp": event.timestamp.isoformat(),
            })

        monitor = DeviceMonitor(broadcaster=_device_broadcaster)
        import asyncio
        device_monitor_task = asyncio.create_task(monitor.start())
        logger.info("main: device monitor dimulai.")
    except Exception as exc:
        logger.warning("main: device monitor gagal dimulai: %s", exc)

    # ── Scheduler ─────────────────────────────────────────────────────
    try:
        from app.core.database import AsyncSessionLocal
        from app.services.scheduler_service import SchedulerService
        scheduler_service = SchedulerService(session_factory=AsyncSessionLocal)
        scheduler_service.start()
        logger.info("main: scheduler service dimulai.")
    except Exception as exc:
        logger.warning("main: scheduler service gagal dimulai: %s", exc)

    yield  # ── Application running ──────────────────────────────────

    # ── Shutdown ──────────────────────────────────────────────────────
    if device_monitor_task is not None:
        device_monitor_task.cancel()
        logger.info("main: device monitor dihentikan.")

    if scheduler_service is not None:
        try:
            scheduler_service.shutdown()
        except Exception as exc:
            logger.warning("main: scheduler shutdown error: %s", exc)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="LinkedIn Automation Bot",
        version="1.0.0",
        description="Sistem otomasi LinkedIn berbasis ADB + AI multi-provider.",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────
    from app.routers import (
        ai,
        content,
        device,
        engage,
        jobs,
        logs,
        schedules,
        settings as settings_router,
        ws,
    )

    prefix = "/api"
    application.include_router(device.router, prefix=prefix)
    application.include_router(content.router, prefix=prefix)
    application.include_router(engage.router, prefix=prefix)
    application.include_router(jobs.router, prefix=prefix)
    application.include_router(schedules.router, prefix=prefix)
    application.include_router(logs.router, prefix=prefix)
    application.include_router(ai.router, prefix=prefix)
    application.include_router(settings_router.router, prefix=prefix)
    application.include_router(ws.router)  # WebSocket — no /api prefix

    # ── Exception handlers ────────────────────────────────────────────
    from app.core.exceptions import register_exception_handlers
    register_exception_handlers(application)

    # ── Static files (screenshots) ────────────────────────────────────
    import os
    screenshots_dir = settings.screenshots_dir
    os.makedirs(screenshots_dir, exist_ok=True)
    application.mount(
        "/static/screenshots",
        StaticFiles(directory=screenshots_dir),
        name="screenshots",
    )

    # ── Health check ──────────────────────────────────────────────────
    @application.get("/health", tags=["health"])
    async def health() -> dict:
        """Liveness probe."""
        return {"status": "ok"}

    return application


app = create_app()
