"""
SQLAlchemy model for the `bot_logs` table.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

_TS = DateTime(timezone=True)


class BotLog(Base):
    """Audit trail setiap aksi bot."""

    __tablename__ = "bot_logs"

    __table_args__ = (
        CheckConstraint(
            "action IN ("
            "'generate_content','search_reference','generate_image',"
            "'open_linkedin','navigate_post','type_content','upload_image',"
            "'publish_post','screenshot','scroll_feed','read_ocr',"
            "'generate_comment','post_comment','open_jobs','search_jobs',"
            "'extract_jobs','easy_apply','fill_form','open_ai_web',"
            "'paste_prompt','copy_response','detect_captcha',"
            "'idle_wait','anti_ban_delay'"
            ")",
            name="ck_bot_logs_action",
        ),
        CheckConstraint(
            "status IN ('success','failed','running','skipped','timeout')",
            name="ck_bot_logs_status",
        ),
        Index("idx_bot_logs_task_id", "task_id"),
        Index("idx_bot_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    module: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, comment="A, B, C, or D"
    )
    metadata_: Mapped[Optional[Any]] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        _TS, nullable=False, server_default=func.now()
    )

    # Relationship (optional, lazy-loaded)
    post = relationship("Post", backref="bot_logs", lazy="select")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BotLog id={self.id} action={self.action!r} status={self.status!r}>"
        )
