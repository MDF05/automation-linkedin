"""
SQLAlchemy model for the `job_applications` table.
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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import DateTime as _DT
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import TIMESTAMP as _PG_TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

# TIMESTAMPTZ = PostgreSQL TIMESTAMP WITH TIME ZONE
TIMESTAMPTZ = _PG_TIMESTAMP(timezone=True)

from .base import Base


class JobApplication(Base):
    """Lowongan kerja yang ditemukan / dilamar oleh Job Hunter."""

    __tablename__ = "job_applications"

    __table_args__ = (
        UniqueConstraint("job_url", name="uq_job_applications_job_url"),
        CheckConstraint(
            "status IN ("
            "'found','applied','skipped','rejected',"
            "'interview','offer',"
            "'skipped_incomplete_form','skipped_no_easy_apply'"
            ")",
            name="ck_job_applications_status",
        ),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    salary_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    job_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="found"
    )
    has_easy_apply: Mapped[bool] = mapped_column(
        Boolean, server_default="false"
    )
    job_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMPTZ, nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    form_fields_filled: Mapped[Optional[Any]] = mapped_column(
        JSONB, nullable=True
    )
    search_session_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )
    screenshot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<JobApplication id={self.id} title={self.job_title!r} "
            f"status={self.status!r}>"
        )
