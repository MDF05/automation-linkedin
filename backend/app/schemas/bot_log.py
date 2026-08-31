"""
Pydantic schemas for BotLog entities.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class BotAction(str, Enum):
    generate_content = "generate_content"
    search_reference = "search_reference"
    generate_image = "generate_image"
    open_linkedin = "open_linkedin"
    navigate_post = "navigate_post"
    type_content = "type_content"
    upload_image = "upload_image"
    publish_post = "publish_post"
    screenshot = "screenshot"
    scroll_feed = "scroll_feed"
    read_ocr = "read_ocr"
    generate_comment = "generate_comment"
    post_comment = "post_comment"
    open_jobs = "open_jobs"
    search_jobs = "search_jobs"
    extract_jobs = "extract_jobs"
    easy_apply = "easy_apply"
    fill_form = "fill_form"
    open_ai_web = "open_ai_web"
    paste_prompt = "paste_prompt"
    copy_response = "copy_response"
    detect_captcha = "detect_captcha"
    idle_wait = "idle_wait"
    anti_ban_delay = "anti_ban_delay"


class BotLogStatus(str, Enum):
    success = "success"
    failed = "failed"
    running = "running"
    skipped = "skipped"
    timeout = "timeout"


class BotLogRead(BaseModel):
    """Schema untuk membaca data bot_log dari database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: Optional[int] = None
    task_id: str
    action: str
    status: str
    message: Optional[str] = None
    error_detail: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None
    duration_ms: Optional[int] = None
    module: Optional[str] = None
    metadata: Optional[Any] = None
    created_at: datetime
