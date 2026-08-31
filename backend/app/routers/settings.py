"""
Settings Router — API endpoints untuk konfigurasi sistem.

Requirements: 12.1–12.5
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.settings import Settings
from app.schemas.system_config import SystemConfigMapRead, SystemConfigUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

# Default keys sesuai design.md seed data
_CONFIG_KEYS = [
    "ai_provider_chain",
    "ai_usage_limits",
    "anti_ban_limits",
    "anti_ban_delays",
    "content_language",
    "cv_path",
    "screenshot_enabled",
]


async def _get_all_settings(db: AsyncSession) -> Dict[str, Any]:
    """Load semua konfigurasi dari tabel settings sebagai dict key → value."""
    result = await db.execute(select(Settings))
    rows = result.scalars().all()
    return {row.key: row.value for row in rows}


async def _get_latest_updated_at(db: AsyncSession) -> datetime | None:
    """Return timestamp update terbaru dari semua settings."""
    from sqlalchemy import func as sqlfunc
    result = await db.execute(select(sqlfunc.max(Settings.updated_at)))
    return result.scalar_one_or_none()


@router.get("", response_model=SystemConfigMapRead)
async def get_settings(db: AsyncSession = Depends(get_db)) -> Any:
    """
    GET /api/settings

    Semua konfigurasi sistem dengan timestamp terakhir diubah.

    Requirements: 12.5
    """
    config = await _get_all_settings(db)
    updated_at = await _get_latest_updated_at(db)

    # Build response with defaults merged over DB values
    anti_ban_limits_raw = config.get("anti_ban_limits", {})
    anti_ban_delays_raw = config.get("anti_ban_delays", {})

    from app.schemas.system_config import AntiBanDelays, AntiBanLimits

    try:
        anti_ban_limits = AntiBanLimits(**(anti_ban_limits_raw if isinstance(anti_ban_limits_raw, dict) else {}))
    except Exception:
        anti_ban_limits = AntiBanLimits()

    try:
        anti_ban_delays = AntiBanDelays(**(anti_ban_delays_raw if isinstance(anti_ban_delays_raw, dict) else {}))
    except Exception:
        anti_ban_delays = AntiBanDelays()

    return SystemConfigMapRead(
        ai_provider_chain=config.get("ai_provider_chain", ["deepseek", "groq", "chatgpt_web", "claude_web"]),
        ai_usage_limits=config.get("ai_usage_limits", {}),
        anti_ban_limits=anti_ban_limits,
        anti_ban_delays=anti_ban_delays,
        content_language=config.get("content_language", "indonesia"),
        cv_path=config.get("cv_path"),
        screenshot_enabled=config.get("screenshot_enabled", True),
        updated_at=updated_at,
    )


@router.put("")
async def update_settings(
    body: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    PUT /api/settings

    Update konfigurasi sistem. Validasi Pydantic (422 jika invalid).

    Validasi:
    - batas harian > 0 (enforced by AntiBanLimits.ge=1)
    - delay min < max (enforced by AntiBanDelays model_validator)

    Requirements: 12.2, 12.3
    """
    updates = body.model_dump(exclude_unset=True)
    now = datetime.now(tz=timezone.utc)

    for key, value in updates.items():
        if value is None:
            continue

        # Serialize nested models to dict
        if hasattr(value, "model_dump"):
            value = value.model_dump()

        # Upsert ke tabel settings
        result = await db.execute(select(Settings).where(Settings.key == key))
        row = result.scalar_one_or_none()

        if row is None:
            row = Settings(key=key, value=value)
            db.add(row)
        else:
            row.value = value
            row.updated_at = now

    await db.flush()
    return {"status": "ok", "updated_keys": list(updates.keys())}
