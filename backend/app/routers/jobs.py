"""
Jobs Router — API endpoints untuk Module D: Job Hunter & Auto Apply.

Requirements: 5.1–5.10
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.job_application import JobApplication
from app.schemas.job_application import JobApplicationRead, JobCriteria

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/search")
async def search_jobs(
    criteria: JobCriteria,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    POST /api/jobs/search

    Mulai sesi job hunting berdasarkan kriteria.

    Requirements: 5.1, 5.2
    """
    import uuid

    session_id = str(uuid.uuid4())

    try:
        from app.core.websocket_manager import manager as ws_manager
        from app.services.adb_service import ADBService
        from app.services.bots.job_hunter_bot import JobHunterBot
        from app.services import ocr_service
        from app.core.config import get_settings

        settings = get_settings()
        cv_fields = {
            "cv_path": settings.cv_path or "",
        }

        adb = ADBService()
        bot = JobHunterBot(
            adb_service=adb,
            ocr_service=ocr_service,
            cv_fields=cv_fields,
            websocket_manager=ws_manager,
        )

        background_tasks.add_task(
            bot.search_jobs,
            criteria=criteria.model_dump(),
            db=db,
            session_id=session_id,
        )

        return {
            "session_id": session_id,
            "status": "started",
            "criteria": criteria.model_dump(),
            "started_at": datetime.now().isoformat(),
        }

    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/applications", response_model=List[JobApplicationRead])
async def list_applications(
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/jobs/applications

    List semua lamaran kerja dengan filter status.

    Requirements: 5.4
    """
    q = select(JobApplication)
    if status:
        q = q.where(JobApplication.status == status)
    if date_from:
        q = q.where(JobApplication.created_at >= date_from)
    if date_to:
        q = q.where(JobApplication.created_at <= date_to)
    q = q.order_by(JobApplication.created_at.desc()).offset((page - 1) * limit).limit(limit)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/applications/export")
async def export_applications_csv(
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/jobs/applications/export

    Download CSV job applications.

    Requirements: 11.1, 11.4
    """
    from fastapi.responses import Response
    from app.services.csv_exporter import export_job_applications

    csv_bytes = await export_job_applications(
        db, status=status, date_from=date_from, date_to=date_to
    )
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8-bom",
        headers={"Content-Disposition": "attachment; filename=job_applications.csv"},
    )


@router.get("/report/{session_id}")
async def get_session_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/jobs/report/{session_id}

    Laporan ringkasan satu sesi job hunting.

    Requirements: 5.9
    """
    from app.services.job_report_service import generate_session_report
    return await generate_session_report(session_id=session_id, db=db)


@router.get("/stats")
async def get_job_stats(db: AsyncSession = Depends(get_db)) -> Any:
    """
    GET /api/jobs/stats

    Statistik total apply dan breakdown per status.

    Requirements: 5.10
    """
    result = await db.execute(
        select(JobApplication.status, func.count(JobApplication.id).label("count"))
        .group_by(JobApplication.status)
    )
    rows = result.all()

    breakdown = {row.status: row.count for row in rows}
    total = sum(breakdown.values())

    return {
        "total": total,
        "breakdown": breakdown,
        "total_applied": breakdown.get("applied", 0),
        "total_found": breakdown.get("found", 0),
        "total_skipped": sum(
            breakdown.get(s, 0)
            for s in ("skipped", "skipped_incomplete_form", "skipped_no_easy_apply")
        ),
    }
