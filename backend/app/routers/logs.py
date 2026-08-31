"""
Logs Router — API endpoints untuk history, audit trail, dan export CSV.

Requirements: 7.1–7.7, 11.1–11.4
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.bot_log import BotLog
from app.schemas.bot_log import BotLogRead

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=List[BotLogRead])
async def list_logs(
    status: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/logs

    List bot_logs dengan filter.

    Requirements: 7.3
    """
    q = select(BotLog)
    if status:
        q = q.where(BotLog.status == status)
    if action:
        q = q.where(BotLog.action == action)
    if module:
        q = q.where(BotLog.module == module)
    if date_from:
        q = q.where(BotLog.created_at >= date_from)
    if date_to:
        q = q.where(BotLog.created_at <= date_to)

    total_q = q
    q = q.order_by(BotLog.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    items = result.scalars().all()

    return items


@router.get("/export")
async def export_logs_csv(
    status: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/logs/export

    Download CSV bot_logs.

    Requirements: 7.5, 11.1
    """
    from fastapi.responses import Response
    from app.services.csv_exporter import export_bot_logs

    csv_bytes = await export_bot_logs(
        db, status=status, module=module, date_from=date_from, date_to=date_to
    )
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8-bom",
        headers={"Content-Disposition": "attachment; filename=bot_logs.csv"},
    )


@router.get("/{log_id}", response_model=BotLogRead)
async def get_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/logs/{id}

    Detail satu log entry termasuk screenshot path dan stack trace.

    Requirements: 7.4
    """
    result = await db.execute(select(BotLog).where(BotLog.id == log_id))
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="Log tidak ditemukan")
    return log
