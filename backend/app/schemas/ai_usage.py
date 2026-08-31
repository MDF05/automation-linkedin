"""
Pydantic schemas for AiUsage entities.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AIProvider(str, Enum):
    deepseek = "deepseek"
    groq = "groq"
    chatgpt_web = "chatgpt_web"
    claude_web = "claude_web"
    perplexity_web = "perplexity_web"


class AiUsageRead(BaseModel):
    """Schema untuk membaca satu entri penggunaan AI dari database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: Optional[int] = None  # computed column di PostgreSQL
    cost_estimate: Decimal
    module: Optional[str] = None
    task_id: Optional[str] = None
    success: bool
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: datetime


class AiUsageProviderSummary(BaseModel):
    """Ringkasan penggunaan per provider AI."""

    provider: str
    total_tokens: int
    cost_estimate_usd: Decimal
    limit: Optional[int] = None
    usage_percent: Optional[float] = None
    call_count: int
    success_count: int
    failure_count: int


class AiUsageSummary(BaseModel):
    """Ringkasan penggunaan AI dalam periode tertentu."""

    period_days: int = Field(..., ge=1)
    providers: List[AiUsageProviderSummary] = []
    total_cost_usd: Decimal = Decimal("0")
    total_calls: int = 0
