"""
SQLAlchemy model for the `posts` table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# Shorthand for TIMESTAMPTZ columns
_TS = DateTime(timezone=True)


class Post(Base):
    """Konten LinkedIn yang dibuat/diposting oleh sistem."""

    __tablename__ = "posts"

    __table_args__ = (
        CheckConstraint(
            "content_type IN ("
            "'storytelling','tips_list','pertanyaan','kutipan',"
            "'video_script','thread','promo','promo_portofolio','promo_testimoni'"
            ")",
            name="ck_posts_content_type",
        ),
        CheckConstraint(
            "status IN ('draft','scheduled','posted','failed')",
            name="ck_posts_status",
        ),
        Index("idx_posts_status", "status"),
        Index("idx_posts_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft"
    )
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_thread: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    thread_parts: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    thread_count: Mapped[int] = mapped_column(Integer, server_default="1")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        _TS, nullable=True
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(_TS, nullable=True)
    likes: Mapped[int] = mapped_column(Integer, server_default="0")
    comments: Mapped[int] = mapped_column(Integer, server_default="0")
    shares: Mapped[int] = mapped_column(Integer, server_default="0")
    ai_provider_used: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    prompt_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    search_references: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    linkedin_post_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        _TS, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        _TS, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Post id={self.id} status={self.status!r} type={self.content_type!r}>"
