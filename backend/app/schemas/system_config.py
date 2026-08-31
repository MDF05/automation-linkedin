"""
Pydantic schemas for SystemConfig (Settings) entities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AntiBanDelays(BaseModel):
    """Konfigurasi range delay untuk anti-ban."""

    tap_min_ms: int = Field(default=1000, ge=100)
    tap_max_ms: int = Field(default=3000, ge=100)
    nav_min_ms: int = Field(default=2000, ge=100)
    nav_max_ms: int = Field(default=5000, ge=100)

    @model_validator(mode="after")
    def check_min_lt_max(self) -> "AntiBanDelays":
        if self.tap_min_ms >= self.tap_max_ms:
            raise ValueError(
                "tap_min_ms harus lebih kecil dari tap_max_ms"
            )
        if self.nav_min_ms >= self.nav_max_ms:
            raise ValueError(
                "nav_min_ms harus lebih kecil dari nav_max_ms"
            )
        return self


class AntiBanLimits(BaseModel):
    """Konfigurasi batas harian per modul."""

    posts_per_day: int = Field(default=3, ge=1)
    comments_per_day: int = Field(default=15, ge=1)
    applies_per_day: int = Field(default=20, ge=1)


class SystemConfigUpdate(BaseModel):
    """Schema untuk update konfigurasi sistem (PUT /settings)."""

    ai_provider_chain: Optional[List[str]] = None
    ai_usage_limits: Optional[Dict[str, int]] = None
    anti_ban_limits: Optional[AntiBanLimits] = None
    anti_ban_delays: Optional[AntiBanDelays] = None
    content_language: Optional[str] = None
    cv_path: Optional[str] = None
    screenshot_enabled: Optional[bool] = None


class SystemConfigRead(BaseModel):
    """Schema untuk membaca satu entri konfigurasi (key-value) dari database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: Any
    description: Optional[str] = None
    updated_at: datetime


class SystemConfigMapRead(BaseModel):
    """Semua konfigurasi sistem sekaligus sebagai map key → value."""

    ai_provider_chain: List[str] = Field(
        default_factory=lambda: ["deepseek", "groq", "chatgpt_web", "claude_web"]
    )
    ai_usage_limits: Dict[str, int] = Field(default_factory=dict)
    anti_ban_limits: AntiBanLimits = Field(default_factory=AntiBanLimits)
    anti_ban_delays: AntiBanDelays = Field(default_factory=AntiBanDelays)
    content_language: str = "indonesia"
    cv_path: Optional[str] = None
    screenshot_enabled: bool = True
    updated_at: Optional[datetime] = None
