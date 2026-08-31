"""
DeepSeek AI Provider

Implementasi ``BaseAIProvider`` menggunakan DeepSeek API (OpenAI-compatible).
Menggunakan httpx untuk async HTTP requests.

Requirements: 8.1, 8.3
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from app.core.config import get_settings
from app.services.ai_service import AIRequest, AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)

# DeepSeek-V3 pricing (USD per token)
_INPUT_COST_PER_TOKEN = 0.14 / 1_000_000   # $0.14 per 1M input tokens
_OUTPUT_COST_PER_TOKEN = 0.28 / 1_000_000  # $0.28 per 1M output tokens

_DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
_DEFAULT_MODEL = "deepseek-chat"


class DeepSeekProvider(BaseAIProvider):
    """
    Provider AI yang menggunakan DeepSeek API.

    API endpoint: POST https://api.deepseek.com/v1/chat/completions
    Format request/response: OpenAI-compatible

    Konfigurasi:
      - API key: ``settings.deepseek_api_key``
      - Token limit: ``settings.ai_usage_limit_deepseek``

    Requirements: 8.1, 8.3
    """

    provider_name: str = "deepseek"

    def __init__(self, timeout: float = 60.0) -> None:
        self._settings = get_settings()
        self._timeout = timeout

    async def generate(self, request: AIRequest) -> AIResponse:
        """
        Kirim request ke DeepSeek API dan kembalikan AIResponse.

        Semua error ditangani secara internal — tidak melempar exception.
        Biaya diestimasi berdasarkan token usage yang dilaporkan API.

        Args:
            request: Parameter AI request.

        Returns:
            AIResponse dengan token usage, estimasi biaya, dan konten respons.
        """
        api_key = self._settings.deepseek_api_key
        if not api_key:
            return AIResponse(
                content="",
                provider=self.provider_name,
                prompt_tokens=0,
                completion_tokens=0,
                cost_estimate=0.0,
                success=False,
                error="DeepSeek API key tidak dikonfigurasi",
            )

        # Bangun pesan dari request
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": _DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        t_start = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    _DEEPSEEK_API_URL,
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

        except httpx.TimeoutException as exc:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            logger.warning("DeepSeekProvider: request timeout: %s", exc)
            return AIResponse(
                content="",
                provider=self.provider_name,
                prompt_tokens=0,
                completion_tokens=0,
                cost_estimate=0.0,
                success=False,
                error=f"Request timeout: {exc}",
                latency_ms=latency_ms,
            )
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            logger.warning(
                "DeepSeekProvider: HTTP error %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
            return AIResponse(
                content="",
                provider=self.provider_name,
                prompt_tokens=0,
                completion_tokens=0,
                cost_estimate=0.0,
                success=False,
                error=f"HTTP {exc.response.status_code}: {exc.response.text}",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            logger.warning("DeepSeekProvider: unexpected error: %s", exc)
            return AIResponse(
                content="",
                provider=self.provider_name,
                prompt_tokens=0,
                completion_tokens=0,
                cost_estimate=0.0,
                success=False,
                error=str(exc),
                latency_ms=latency_ms,
            )

        latency_ms = int((time.monotonic() - t_start) * 1000)

        # Parse response (OpenAI-compatible format)
        try:
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            prompt_tokens: int = usage.get("prompt_tokens", 0)
            completion_tokens: int = usage.get("completion_tokens", 0)
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("DeepSeekProvider: parse error: %s — data=%s", exc, data)
            return AIResponse(
                content="",
                provider=self.provider_name,
                prompt_tokens=0,
                completion_tokens=0,
                cost_estimate=0.0,
                success=False,
                error=f"Gagal parse response: {exc}",
                latency_ms=latency_ms,
            )

        cost_estimate = (
            prompt_tokens * _INPUT_COST_PER_TOKEN
            + completion_tokens * _OUTPUT_COST_PER_TOKEN
        )

        return AIResponse(
            content=content,
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_estimate=cost_estimate,
            success=True,
            latency_ms=latency_ms,
        )

    async def is_available(self) -> bool:
        """
        Return True jika API key dikonfigurasi (tidak None/kosong).

        Requirements: 8.3
        """
        api_key = self._settings.deepseek_api_key
        return bool(api_key and api_key.strip())

    def get_token_limit(self) -> int:
        """
        Kembalikan batas token/bulan dari konfigurasi.

        Requirements: 8.3
        """
        return self._settings.ai_usage_limit_deepseek
