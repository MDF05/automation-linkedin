"""
Pydantic schemas for JobApplication entities.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobType(str, Enum):
    full_time = "full-time"
    part_time = "part-time"
    kontrak = "kontrak"
    freelance = "freelance"


class JobStatus(str, Enum):
    found = "found"
    applied = "applied"
    skipped = "skipped"
    rejected = "rejected"
    interview = "interview"
    offer = "offer"
    skipped_incomplete_form = "skipped_incomplete_form"
    skipped_no_easy_apply = "skipped_no_easy_apply"


class JobCriteria(BaseModel):
    """Kriteria pencarian lowongan kerja untuk Job Hunter."""

    titles: List[str] = Field(..., min_length=1, description="Satu atau lebih judul posisi")
    skills: List[str] = Field(default_factory=list, description="Skill yang diinginkan")
    location: Optional[str] = Field(None, description="Kota atau 'remote'")
    min_salary: Optional[str] = Field(None, description="Range gaji minimum")
    job_type: Optional[JobType] = None


class JobApplicationRead(BaseModel):
    """Schema untuk membaca data job application dari database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_title: str
    company: str
    location: Optional[str] = None
    salary_range: Optional[str] = None
    job_url: str
    status: str
    has_easy_apply: bool
    job_type: Optional[str] = None
    applied_at: Optional[datetime] = None
    notes: Optional[str] = None
    form_fields_filled: Optional[Any] = None
    search_session_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
