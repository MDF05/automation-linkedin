"""
SQLAlchemy model for the `schedules` table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import TIMESTAMP as _PG_TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

# TIMESTAMPTZ = PostgreSQL TIMESTAMP WITH TIME ZONE
TIMESTAMPTZ = _PG_TIMESTAMP(timezone=True)

from .base import Base


class Schedule(Base):
    """Jadwal eksekusi tugas otomatis (cron / once)."""

    __tablename__ = "schedules"

    __table_args__ = (
        CheckConstraint(
            "task_type IN ('post_konten','engage','job_hunt','promosi')",
            name="ck_schedules_task_type",
        ),
        Index("idx_schedules_active", "is_active"),
        Index("idx_schedules_next_run", "next_run"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    cron_expression: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    scheduled_once_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMPTZ, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    last_run: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ, nullable=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    next_run: Mapped[Optional[datetime]] = mapped_column(TIMESTAMPTZ, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, server_default="3")
    config_json: Mapped[Any] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    run_count: Mapped[int] = mapped_column(Integer, server_default="0")
    failure_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Schedule id={self.id} name={self.name!r} "
            f"task={self.task_type!r} active={self.is_active}>"
        )
