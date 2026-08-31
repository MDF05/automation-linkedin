"""
SQLAlchemy model for the `settings` table (key-value store).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import TIMESTAMP as _PG_TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

# TIMESTAMPTZ = PostgreSQL TIMESTAMP WITH TIME ZONE
TIMESTAMPTZ = _PG_TIMESTAMP(timezone=True)

from .base import Base


class Settings(Base):
    """Penyimpanan konfigurasi sistem berbasis key-value dengan nilai JSONB."""

    __tablename__ = "settings"

    __table_args__ = (
        UniqueConstraint("key", name="uq_settings_key"),
        Index("idx_settings_key", "key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Settings key={self.key!r}>"
