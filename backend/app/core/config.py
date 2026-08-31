"""
Konfigurasi aplikasi berbasis Pydantic BaseSettings.

Semua nilai dibaca dari environment variables atau file .env.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Konfigurasi utama aplikasi LinkedIn Automation Bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/linkedin_bot",
        description="URL koneksi PostgreSQL (asyncpg driver untuk SQLAlchemy async)",
    )

    # ------------------------------------------------------------------ #
    # ADB / Device
    # ------------------------------------------------------------------ #
    adb_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout perintah ADB dalam detik (Requirement 1.4)",
    )

    # ------------------------------------------------------------------ #
    # AI Providers
    # ------------------------------------------------------------------ #
    deepseek_api_key: Optional[str] = Field(
        default=None,
        description="API key DeepSeek",
    )
    groq_api_key: Optional[str] = Field(
        default=None,
        description="API key Groq",
    )
    ideogram_api_key: Optional[str] = Field(
        default=None,
        description="API key Ideogram.ai untuk generate gambar",
    )

    # Urutan provider chain — default sesuai design doc
    ai_provider_chain: List[str] = Field(
        default=["deepseek", "groq", "chatgpt_web", "claude_web"],
        description="Urutan prioritas provider AI dengan fallback otomatis (Requirement 8.5)",
    )

    # Batas token/bulan per provider (Requirement 8.3)
    ai_usage_limit_deepseek: int = Field(
        default=500_000,
        ge=0,
        description="Batas token/bulan DeepSeek",
    )
    ai_usage_limit_groq: int = Field(
        default=30_000,
        ge=0,
        description="Batas token/bulan Groq",
    )
    ai_usage_limit_chatgpt_web: int = Field(
        default=100,
        ge=0,
        description="Batas request/bulan ChatGPT web",
    )
    ai_usage_limit_claude_web: int = Field(
        default=50,
        ge=0,
        description="Batas request/bulan Claude web",
    )
    ai_usage_limit_perplexity_web: int = Field(
        default=50,
        ge=0,
        description="Batas request/bulan Perplexity web",
    )

    # Persentase kuota yang memicu peringatan dan fallback otomatis (Requirement 8.3)
    ai_usage_warning_threshold: float = Field(
        default=0.80,
        ge=0.0,
        le=1.0,
        description="Threshold usage (0–1) untuk trigger peringatan dan fallback",
    )

    # ------------------------------------------------------------------ #
    # Anti-Ban Limits (Requirement 9.2)
    # ------------------------------------------------------------------ #
    anti_ban_posts_per_day: int = Field(
        default=3,
        ge=1,
        description="Maksimal posting per hari (Requirement 9.2)",
    )
    anti_ban_comments_per_day: int = Field(
        default=15,
        ge=1,
        description="Maksimal komentar per hari (Requirement 9.2)",
    )
    anti_ban_applies_per_day: int = Field(
        default=20,
        ge=1,
        description="Maksimal lamaran per hari (Requirement 9.2)",
    )

    # Anti-Ban Delays (Requirement 9.1)
    anti_ban_tap_min_ms: int = Field(
        default=1000,
        ge=100,
        description="Minimum delay antar tap (ms)",
    )
    anti_ban_tap_max_ms: int = Field(
        default=3000,
        ge=100,
        description="Maksimum delay antar tap (ms)",
    )
    anti_ban_nav_min_ms: int = Field(
        default=2000,
        ge=100,
        description="Minimum delay antar navigasi (ms)",
    )
    anti_ban_nav_max_ms: int = Field(
        default=5000,
        ge=100,
        description="Maksimum delay antar navigasi (ms)",
    )

    # Interval minimum antar sesi engage (Requirement 9.7)
    anti_ban_session_gap_minutes: int = Field(
        default=30,
        ge=1,
        description="Interval minimum antar sesi engage berturut-turut (menit)",
    )

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    screenshots_dir: str = Field(
        default="/app/static/screenshots",
        description="Direktori penyimpanan screenshot",
    )
    screenshot_enabled: bool = Field(
        default=True,
        description="Aktifkan screenshot setelah setiap aksi bot (Requirement 1.6)",
    )
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000"],
        description="CORS allowed origins",
    )
    content_language: str = Field(
        default="indonesia",
        description="Bahasa konten default",
    )
    cv_path: Optional[str] = Field(
        default=None,
        description="Path file CV untuk auto apply Job Hunter",
    )

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("ai_provider_chain", mode="before")
    @classmethod
    def parse_provider_chain(cls, v: object) -> List[str]:
        """Support env var sebagai comma-separated string."""
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v  # type: ignore[return-value]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: object) -> List[str]:
        """Support env var sebagai comma-separated string."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v  # type: ignore[return-value]

    # ------------------------------------------------------------------ #
    # Computed helpers
    # ------------------------------------------------------------------ #
    @property
    def ai_usage_limits(self) -> dict[str, int]:
        """Map provider → batas token/bulan."""
        return {
            "deepseek": self.ai_usage_limit_deepseek,
            "groq": self.ai_usage_limit_groq,
            "chatgpt_web": self.ai_usage_limit_chatgpt_web,
            "claude_web": self.ai_usage_limit_claude_web,
            "perplexity_web": self.ai_usage_limit_perplexity_web,
        }


@lru_cache
def get_settings() -> Settings:
    """Return singleton Settings — cached setelah pertama kali dipanggil."""
    return Settings()
