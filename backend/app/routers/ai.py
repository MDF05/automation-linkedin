"""
AI Router — API endpoints untuk monitoring penggunaan AI provider.

Requirements: 8.1, 8.2
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.ai_usage import AiUsage
from app.schemas.ai_usage import AiUsageSummary, AiUsageProviderSummary

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/usage", response_model=AiUsageSummary)
async def get_ai_usage_summary(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/ai/usage

    Ringkasan penggunaan AI per provider dalam N hari terakhir.

    Requirements: 8.2
    """
    from app.core.config import get_settings

    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    settings = get_settings()

    # Aggregate per provider
    result = await db.execute(
        select(
            AiUsage.provider,
            func.coalesce(func.sum(AiUsage.prompt_tokens + AiUsage.completion_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AiUsage.cost_estimate), Decimal("0")).label("total_cost"),
            func.count(AiUsage.id).label("call_count"),
            func.sum(
                func.cast(AiUsage.success, type_=func.Integer() if False else AiUsage.success.__class__)
            ).label("success_count"),
        )
        .where(AiUsage.created_at >= since)
        .group_by(AiUsage.provider)
    )
    rows = result.all()

    providers = []
    total_cost = Decimal("0")
    total_calls = 0
    limits = settings.ai_usage_limits

    for row in rows:
        provider_name = row.provider
        total_tok = int(row.total_tokens or 0)
        cost = Decimal(str(row.total_cost or 0))
        call_count = int(row.call_count or 0)
        # Count successes separately
        success_result = await db.execute(
            select(func.count(AiUsage.id))
            .where(AiUsage.provider == provider_name, AiUsage.success == True, AiUsage.created_at >= since)
        )
        success_count = success_result.scalar_one() or 0
        failure_count = call_count - success_count

        limit = limits.get(provider_name)
        usage_pct: float | None = None
        if limit and limit > 0:
            usage_pct = round((total_tok / limit) * 100, 2)

        providers.append(AiUsageProviderSummary(
            provider=provider_name,
            total_tokens=total_tok,
            cost_estimate_usd=cost,
            limit=limit,
            usage_percent=usage_pct,
            call_count=call_count,
            success_count=success_count,
            failure_count=failure_count,
        ))
        total_cost += cost
        total_calls += call_count

    return AiUsageSummary(
        period_days=days,
        providers=providers,
        total_cost_usd=total_cost,
        total_calls=total_calls,
    )
