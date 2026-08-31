"""
SQLAlchemy model for the `ai_usage` table.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP as _PG_TIMESTAMP

# TIMESTAMPTZ = PostgreSQL TIMESTAMP WITH TIME ZONE
TIMESTAMPTZ = _PG_TIMESTAMP(timezone=True)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AiUsage(Base):
    """Tracking setiap pemanggilan ke provider AI."""

    __tablename__ = "ai_usage"

    __table_args__ = (
        CheckConstraint(
            "provider IN ("
            "'deepseek','groq','chatgpt_web','claude_web','perplexity_web'"
            ")",
            name="ck_ai_usage_provider",
        ),
        Index("idx_ai_usage_provider", "provider"),
        Index("idx_ai_usage_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    cost_estimate: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), server_default="0"
    )
    module: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, comment="A, B, C, or D"
    )
    task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    success: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AiUsage id={self.id} provider={self.provider!r} "
            f"success={self.success}>"
        )
