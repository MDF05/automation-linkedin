"""
Engage Router — API endpoints untuk Module C: Auto Interaksi dengan Audiens.

Requirements: 4.1–4.10
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.interaction import Interaction
from app.schemas.interaction import InteractionRead

router = APIRouter(prefix="/engage", tags=["engage"])

# Track running sessions
_running_sessions: Dict[str, bool] = {}


@router.post("/start")
async def start_engage_session(
    body: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    POST /api/engage/start

    Mulai sesi engage otomatis.

    Body: {"duration_minutes": 30, "topic_keywords": ["tech", "AI"]}

    Requirements: 4.1–4.10
    """
    import uuid

    duration = body.get("duration_minutes", 30)
    topic_keywords = body.get("topic_keywords", [])

    try:
        from app.core.websocket_manager import manager as ws_manager
        from app.services.adb_service import ADBService
        from app.services.ai_service import ProviderChain
        from app.services.bots.engage_bot import EngageBot
        from app.services import ocr_service

        adb = ADBService()
        ai = ProviderChain()
        bot = EngageBot(
            adb_service=adb,
            ai_service=ai,
            ocr_service=ocr_service,
            websocket_manager=ws_manager,
        )

        task_id = str(uuid.uuid4())
        _running_sessions[task_id] = True

        # Run as background task
        background_tasks.add_task(
            bot.run_engage_session,
            duration_minutes=duration,
            db=db,
            topic_keywords=topic_keywords if topic_keywords else None,
        )

        return {
            "task_id": task_id,
            "status": "started",
            "duration_minutes": duration,
            "topic_keywords": topic_keywords,
            "started_at": datetime.now().isoformat(),
        }

    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/stop")
async def stop_engage_session(
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """
    POST /api/engage/stop

    Hentikan sesi engage yang sedang berjalan.

    Body: {"task_id": "uuid"}

    Requirements: 4.1
    """
    task_id = body.get("task_id", "")
    if task_id in _running_sessions:
        _running_sessions.pop(task_id, None)

    return {"task_id": task_id, "status": "stopped"}


@router.get("/interactions", response_model=List[InteractionRead])
async def list_interactions(
    status: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/engage/interactions

    List interaksi dengan filter.

    Requirements: 4.6
    """
    q = select(Interaction)
    if status:
        q = q.where(Interaction.status == status)
    if action_type:
        q = q.where(Interaction.action_type == action_type)
    if date_from:
        q = q.where(Interaction.created_at >= date_from)
    if date_to:
        q = q.where(Interaction.created_at <= date_to)
    q = q.order_by(Interaction.created_at.desc()).offset((page - 1) * limit).limit(limit)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/interactions/export")
async def export_interactions_csv(
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/engage/interactions/export

    Download CSV interactions.

    Requirements: 11.1, 11.3
    """
    from fastapi.responses import Response
    from app.services.csv_exporter import export_interactions

    csv_bytes = await export_interactions(
        db, status=status, date_from=date_from, date_to=date_to
    )
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8-bom",
        headers={"Content-Disposition": "attachment; filename=interactions.csv"},
    )
