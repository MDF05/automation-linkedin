"""
SQLAlchemy model for the `interactions` table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

_TS = DateTime(timezone=True)


class Interaction(Base):
    """Komentar / reaksi / share bot terhadap post pengguna lain."""

    __tablename__ = "interactions"

    __table_args__ = (
        CheckConstraint(
            "action_type IN ('comment','react','share','connect')",
            name="ck_interactions_action_type",
        ),
        CheckConstraint(
            "status IN ('success','failed','skipped')",
            name="ck_interactions_status",
        ),
        Index("idx_interactions_target_url", "target_post_url"),
        Index("idx_interactions_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_post_url: Mapped[str] = mapped_column(Text, nullable=False)
    target_author: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    target_post_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content_sent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    skip_reason: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    ai_provider_used: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    screenshot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        _TS, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Interaction id={self.id} action={self.action_type!r} "
            f"status={self.status!r}>"
        )
