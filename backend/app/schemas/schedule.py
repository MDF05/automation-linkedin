"""
Pydantic schemas for Schedule entities.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskType(str, Enum):
    post_konten = "post_konten"
    engage = "engage"
    job_hunt = "job_hunt"
    promosi = "promosi"


class ScheduleCreate(BaseModel):
    """Schema untuk membuat jadwal baru."""

    name: str = Field(..., min_length=1, max_length=100)
    task_type: TaskType
    cron_expression: Optional[str] = Field(None, max_length=100)
    scheduled_once_at: Optional[datetime] = None
    is_active: bool = True
    max_retries: int = Field(default=3, ge=0, le=10)
    config_json: Any = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_schedule_type(self) -> "ScheduleCreate":
        """Harus ada salah satu: cron_expression atau scheduled_once_at."""
        if not self.cron_expression and not self.scheduled_once_at:
            raise ValueError(
                "Harus mengisi salah satu: cron_expression atau scheduled_once_at"
            )
        return self


class ScheduleUpdate(BaseModel):
    """Schema untuk update jadwal (PATCH)."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    task_type: Optional[TaskType] = None
    cron_expression: Optional[str] = Field(None, max_length=100)
    scheduled_once_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    config_json: Optional[Any] = None


class ScheduleRead(BaseModel):
    """Schema untuk membaca data jadwal dari database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    task_type: str
    cron_expression: Optional[str] = None
    scheduled_once_at: Optional[datetime] = None
    is_active: bool
    last_run: Optional[datetime] = None
    last_status: Optional[str] = None
    next_run: Optional[datetime] = None
    retry_count: int
    max_retries: int
    config_json: Any
    run_count: int
    failure_count: int
    created_at: datetime
    updated_at: datetime
