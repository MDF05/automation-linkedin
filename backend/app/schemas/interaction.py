"""
Pydantic schemas for Interaction entities.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ActionType(str, Enum):
    comment = "comment"
    react = "react"
    share = "share"
    connect = "connect"


class InteractionStatus(str, Enum):
    success = "success"
    failed = "failed"
    skipped = "skipped"


class InteractionRead(BaseModel):
    """Schema untuk membaca data interaksi dari database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    target_post_url: str
    target_author: Optional[str] = None
    target_post_text: Optional[str] = None
    action_type: str
    content_sent: Optional[str] = None
    status: str
    skip_reason: Optional[str] = None
    ai_provider_used: Optional[str] = None
    screenshot_path: Optional[str] = None
    created_at: datetime
