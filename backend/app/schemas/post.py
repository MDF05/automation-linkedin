"""
Pydantic schemas for Post entities.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ContentType(str, Enum):
    storytelling = "storytelling"
    tips_list = "tips_list"
    pertanyaan = "pertanyaan"
    kutipan = "kutipan"
    video_script = "video_script"
    thread = "thread"
    promo = "promo"
    promo_portofolio = "promo_portofolio"
    promo_testimoni = "promo_testimoni"


class ContentTone(str, Enum):
    profesional = "profesional"
    kasual = "kasual"
    inspiratif = "inspiratif"
    edukasi = "edukasi"


class ContentLength(str, Enum):
    pendek = "pendek"    # ~300 chars
    sedang = "sedang"    # ~1000 chars
    panjang = "panjang"  # ~2500 chars


class PostStatus(str, Enum):
    draft = "draft"
    scheduled = "scheduled"
    posted = "posted"
    failed = "failed"


class PostCreate(BaseModel):
    """Schema untuk membuat post baru (draft atau langsung posting)."""

    title: Optional[str] = Field(None, max_length=255)
    content: str = Field(..., min_length=1)
    content_type: ContentType
    tone: Optional[ContentTone] = None
    status: PostStatus = PostStatus.draft
    image_url: Optional[str] = None
    is_thread: bool = False
    thread_parts: Optional[Any] = None  # List[{part_number, content, char_count}]
    thread_count: int = Field(default=1, ge=1, le=10)
    scheduled_at: Optional[datetime] = None
    ai_provider_used: Optional[str] = None
    prompt_used: Optional[str] = None
    search_references: Optional[Any] = None  # List[{url, title, snippet}]


class PostUpdate(BaseModel):
    """Schema untuk update sebagian field post (PATCH)."""

    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    content_type: Optional[ContentType] = None
    tone: Optional[ContentTone] = None
    status: Optional[PostStatus] = None
    image_url: Optional[str] = None
    is_thread: Optional[bool] = None
    thread_parts: Optional[Any] = None
    thread_count: Optional[int] = Field(None, ge=1, le=10)
    scheduled_at: Optional[datetime] = None


class PostRead(BaseModel):
    """Schema untuk membaca data post dari database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: Optional[str] = None
    content: str
    content_type: str
    tone: Optional[str] = None
    status: str
    image_url: Optional[str] = None
    is_thread: bool
    thread_parts: Optional[Any] = None
    thread_count: int
    scheduled_at: Optional[datetime] = None
    posted_at: Optional[datetime] = None
    likes: int
    comments: int
    shares: int
    ai_provider_used: Optional[str] = None
    prompt_used: Optional[str] = None
    search_references: Optional[Any] = None
    linkedin_post_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PostGenerateVariant(BaseModel):
    """Satu variasi konten hasil generate AI."""

    content: str
    char_count: int
    hashtags: List[str] = []


class PostGenerateRequest(BaseModel):
    """Request untuk generate konten baru."""

    topic: str = Field(..., min_length=1)
    description: Optional[str] = None
    content_type: ContentType
    tone: ContentTone
    length: ContentLength
    generate_image: bool = False


class PostGenerateResponse(BaseModel):
    """Response generate konten — selalu 3 variasi."""

    variants: List[PostGenerateVariant] = Field(..., min_length=3, max_length=3)
    image_url: Optional[str] = None
    search_references: List[Any] = []
    ai_provider_used: str
