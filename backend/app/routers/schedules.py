"""
Schedules Router — API endpoints untuk penjadwalan tugas otomatis.

Requirements: 6.1–6.7
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.services.scheduler_service import SchedulerService, compute_next_run

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _get_scheduler() -> Optional[SchedulerService]:
    """Return scheduler service instance if available via app state."""
    try:
        from app.main import scheduler_service  # type: ignore[import]
        return scheduler_service
    except ImportError:
        return None


@router.get("", response_model=List[ScheduleRead])
async def list_schedules(db: AsyncSession = Depends(get_db)) -> Any:
    """
    GET /api/schedules

    List semua jadwal.

    Requirements: 6.1
    """
    result = await db.execute(select(Schedule).order_by(Schedule.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=ScheduleRead, status_code=201)
async def create_schedule(
    body: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    POST /api/schedules

    Buat jadwal baru.

    Requirements: 6.1
    """
    from datetime import datetime, timezone

    schedule = Schedule(
        name=body.name,
        task_type=body.task_type.value,
        cron_expression=body.cron_expression,
        scheduled_once_at=body.scheduled_once_at,
        is_active=body.is_active,
        max_retries=body.max_retries,
        config_json=body.config_json or {},
    )

    # Hitung next_run awal — Requirements 6.3
    if body.cron_expression:
        schedule.next_run = compute_next_run(
            body.cron_expression,
            from_dt=datetime.now(tz=timezone.utc),
        )
    elif body.scheduled_once_at:
        schedule.next_run = body.scheduled_once_at

    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)

    # Daftarkan ke APScheduler jika aktif
    if schedule.is_active:
        svc = _get_scheduler()
        if svc:
            svc._register_apscheduler_job(schedule)

    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleRead)
async def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    PATCH /api/schedules/{id}

    Update jadwal.

    Requirements: 6.1
    """
    from datetime import datetime, timezone

    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")

    for field_name, value in body.model_dump(exclude_unset=True).items():
        setattr(schedule, field_name, value)

    # Recalculate next_run jika cron berubah
    if body.cron_expression:
        schedule.next_run = compute_next_run(
            body.cron_expression,
            from_dt=datetime.now(tz=timezone.utc),
        )

    await db.flush()
    await db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    DELETE /api/schedules/{id}

    Hapus jadwal.

    Requirements: 6.1
    """
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")

    svc = _get_scheduler()
    if svc:
        await svc.remove_schedule(schedule_id)

    await db.delete(schedule)
    await db.flush()


@router.post("/{schedule_id}/toggle", response_model=ScheduleRead)
async def toggle_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    POST /api/schedules/{id}/toggle

    Aktifkan atau nonaktifkan jadwal.
    Jika diaktifkan kembali, next_run dihitung dari sekarang (Requirements 6.7).

    Requirements: 6.6, 6.7
    """
    svc = _get_scheduler()
    if svc:
        schedule = await svc.toggle_schedule(schedule_id, db)
    else:
        # Fallback tanpa APScheduler
        from datetime import datetime, timezone

        result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()
        if schedule is None:
            raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")

        schedule.is_active = not schedule.is_active
        if schedule.is_active and schedule.cron_expression:
            schedule.next_run = compute_next_run(
                schedule.cron_expression,
                from_dt=datetime.now(tz=timezone.utc),
            )
            schedule.retry_count = 0
        await db.flush()

    if schedule is None:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")

    await db.refresh(schedule)
    return schedule
