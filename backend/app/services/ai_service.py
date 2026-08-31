"""
AI Service — Base interface dan Provider Chain.

Komponen ini menyediakan:
- ``AIRequest`` / ``AIResponse`` — dataclass untuk request/response ke provider AI
- ``BaseAIProvider`` — abstract base class yang harus diimplementasikan oleh setiap provider
- ``AllProvidersExhaustedError`` — exception yang dilempar saat semua provider gagal (Requirements 8.4)
- ``ProviderChain`` — iterasi provider berdasarkan prioritas dengan fallback otomatis,
  mencatat setiap call ke tabel ``ai_usage``, dan broadcast warning saat kuota 80% (Requirements 8.1, 8.3, 8.5)

Design reference: "AI Provider Chain" flowchart dan "Service Interfaces" di design.md
Requirements: 8.1, 8.4, 8.5
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AllProvidersExhaustedError(Exception):
    """
    Dilempar ketika semua provider AI yang dikonfigurasi telah dicoba dan
    semuanya gagal atau tidak tersedia.

    Requirements: 8.4
    """

    def __init__(
        self,
        providers_tried: Optional[List[str]] = None,
        message: Optional[str] = None,
    ) -> None:
        self.providers_tried: List[str] = providers_tried or []
        default_msg = (
            f"Semua provider AI tidak dapat digunakan: {self.providers_tried}. "
            "Periksa konfigurasi dan kuota provider."
        )
        super().__init__(message or default_msg)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AIRequest:
    """
    Parameter untuk satu request ke provider AI.

    Attributes:
        prompt:        Teks utama yang akan diproses oleh AI.
        system_prompt: Instruksi sistem opsional untuk mengatur perilaku AI.
        max_tokens:    Batas maksimum token output (default 2048).
        temperature:   Kreativitas respons (0.0 = deterministik, 1.0 = kreatif, default 0.7).
        module:        Kode modul pemanggil ('A', 'B', 'C', 'D') — disimpan ke ai_usage.
        task_id:       UUID task untuk korelasi dengan bot_logs.
    """

    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.7
    module: Optional[str] = None
    task_id: Optional[str] = None


@dataclass
class AIResponse:
    """
    Hasil dari satu call ke provider AI.

    Attributes:
        content:           Teks respons dari AI.
        provider:          Nama provider yang menghasilkan respons ini.
        prompt_tokens:     Jumlah token pada prompt.
        completion_tokens: Jumlah token pada respons.
        cost_estimate:     Estimasi biaya dalam USD.
        success:           True jika call berhasil.
        error:             Pesan error jika success=False.
        latency_ms:        Latensi eksekusi dalam milidetik.
    """

    content: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cost_estimate: float
    success: bool
    error: Optional[str] = None
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# Abstract Base Provider
# ---------------------------------------------------------------------------


class BaseAIProvider(ABC):
    """
    Abstract base class yang harus diimplementasikan oleh setiap provider AI.

    Setiap provider konkret (DeepSeek, Groq, ChatGPT web, Claude web, dll.)
    mewarisi kelas ini dan mengimplementasikan tiga method abstract:
    - ``generate()``       — Kirim request dan kembalikan AIResponse
    - ``is_available()``   — Cek apakah provider dapat dihubungi
    - ``get_token_limit()`` — Kembalikan batas token/bulan untuk provider ini

    Attribute ``provider_name`` wajib di-set di subclass sebagai class variable.
    """

    #: Nama unik provider (misal: 'deepseek', 'groq', 'chatgpt_web').
    #: Harus sesuai dengan nilai yang valid di tabel ai_usage.
    provider_name: str = ""

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """
        Kirim ``request`` ke provider AI dan kembalikan ``AIResponse``.

        Implementasi harus menangani semua error internal dan mengembalikan
        ``AIResponse(success=False, error=...)`` jika terjadi kesalahan,
        bukan melempar exception langsung.

        Args:
            request: Parameter request (prompt, system_prompt, max_tokens, temperature).

        Returns:
            ``AIResponse`` dengan detail hasil, termasuk token usage dan biaya.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Periksa apakah provider dapat dihubungi (misalnya: API key tersedia,
        endpoint responsif, atau browser HP sudah siap).

        Returns:
            True jika provider siap digunakan, False jika tidak.
        """
        ...

    @abstractmethod
    def get_token_limit(self) -> int:
        """
        Kembalikan batas token atau request bulanan yang dikonfigurasi untuk
        provider ini.

        Nilai ini digunakan oleh ``ProviderChain`` untuk menghitung persentase
        penggunaan dan memutuskan apakah perlu fallback.

        Returns:
            Batas token/request per bulan (integer >= 0).
        """
        ...


# ---------------------------------------------------------------------------
# Provider Chain
# ---------------------------------------------------------------------------


class ProviderChain:
    """
    Iterasi provider AI berdasarkan urutan prioritas dengan fallback otomatis.

    Alur eksekusi (sesuai flowchart "AI Provider Chain" di design.md):
    1. Ambil urutan provider dari ``settings.ai_provider_chain``
    2. Coba setiap provider secara berurutan:
       a. Jika ``provider.is_available()`` → False: lewati, coba provider berikutnya
       b. Jika penggunaan provider >= 80% dari batas: broadcast warning, lewati
       c. Jika ``provider.generate()`` berhasil: catat ke ``ai_usage``, return response
       d. Jika ``provider.generate()`` gagal: catat ke ``ai_usage``, coba provider berikutnya
    3. Jika semua provider gagal: raise ``AllProvidersExhaustedError``

    Setiap call (berhasil atau gagal) selalu dicatat ke tabel ``ai_usage`` (Requirements 8.1).

    Args:
        providers:           List instance ``BaseAIProvider``, diurutkan sesuai prioritas.
        db:                  ``AsyncSession`` SQLAlchemy untuk menyimpan entri ``ai_usage``
                             dan membaca penggunaan historis.
        usage_warning_cb:    Callback opsional ``(provider_name, usage_percent, threshold)``
                             yang dipanggil saat kuota provider mendekati batas (>= 80%).
                             Digunakan untuk broadcast WebSocket event ``ai:usage_warning``.
    """

    def __init__(
        self,
        providers: List[BaseAIProvider],
        db: AsyncSession,
        usage_warning_cb: Optional[Callable[[str, float, float], None]] = None,
    ) -> None:
        self._providers = providers
        self._db = db
        self._usage_warning_cb = usage_warning_cb
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(self, request: AIRequest) -> AIResponse:
        """
        Coba setiap provider dalam urutan prioritas hingga salah satu berhasil.

        Args:
            request: Parameter AI request (prompt, system_prompt, max_tokens, ...).

        Returns:
            ``AIResponse`` dari provider pertama yang berhasil.

        Raises:
            AllProvidersExhaustedError: Jika semua provider gagal atau tidak tersedia.

        Requirements: 8.1, 8.4, 8.5
        """
        providers_tried: List[str] = []

        for provider in self._providers:
            name = provider.provider_name

            # ── Cek ketersediaan provider ──────────────────────────────
            try:
                available = await provider.is_available()
            except Exception as exc:
                logger.warning(
                    "ProviderChain: is_available() gagal untuk '%s': %s", name, exc
                )
                available = False

            if not available:
                logger.info("ProviderChain: provider '%s' tidak tersedia, skip.", name)
                continue

            # ── Cek kuota penggunaan (>= 80% → warning + skip) ─────────
            usage_pct = await self._get_usage_percent(name)
            threshold = self._settings.ai_usage_warning_threshold  # default 0.80

            if usage_pct >= threshold:
                logger.warning(
                    "ProviderChain: provider '%s' telah menggunakan %.1f%% kuota "
                    "(threshold %.0f%%), skip.",
                    name,
                    usage_pct * 100,
                    threshold * 100,
                )
                # Broadcast warning ke dashboard via callback (jika disediakan)
                if self._usage_warning_cb is not None:
                    try:
                        self._usage_warning_cb(name, usage_pct, threshold)
                    except Exception as cb_exc:
                        logger.warning(
                            "ProviderChain: usage_warning_cb error: %s", cb_exc
                        )
                continue

            # ── Eksekusi generate ───────────────────────────────────────
            providers_tried.append(name)
            t_start = time.monotonic()

            try:
                response = await provider.generate(request)
            except Exception as exc:
                # Provider melempar exception tidak terduga — perlakukan sebagai failure
                elapsed_ms = int((time.monotonic() - t_start) * 1000)
                response = AIResponse(
                    content="",
                    provider=name,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_estimate=0.0,
                    success=False,
                    error=str(exc),
                    latency_ms=elapsed_ms,
                )
                logger.warning(
                    "ProviderChain: provider '%s' melempar exception: %s", name, exc
                )

            # Pastikan latency_ms terisi
            if response.latency_ms == 0:
                response.latency_ms = int((time.monotonic() - t_start) * 1000)

            # ── Catat ke ai_usage (selalu, berhasil maupun gagal) ───────
            await self._log_usage(response, request)

            if response.success:
                logger.info(
                    "ProviderChain: provider '%s' berhasil (%d tokens, %.0f ms).",
                    name,
                    response.prompt_tokens + response.completion_tokens,
                    response.latency_ms,
                )
                return response

            logger.warning(
                "ProviderChain: provider '%s' gagal: %s. Mencoba provider berikutnya.",
                name,
                response.error,
            )

        # Semua provider gagal atau tidak tersedia
        raise AllProvidersExhaustedError(providers_tried=providers_tried)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _log_usage(self, response: AIResponse, request: AIRequest) -> None:
        """
        Simpan satu entri ``AiUsage`` ke database untuk setiap call AI.

        Dipanggil setelah setiap ``provider.generate()``, baik berhasil maupun gagal,
        untuk memastikan Property 8 (every AI call produces exactly one ai_usage entry).

        Requirements: 8.1
        """
        from app.models.ai_usage import AiUsage

        entry = AiUsage(
            provider=response.provider,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            cost_estimate=Decimal(str(round(response.cost_estimate, 6))),
            module=request.module,
            task_id=request.task_id,
            success=response.success,
            error_message=response.error,
            latency_ms=response.latency_ms,
        )

        try:
            self._db.add(entry)
            await self._db.flush()  # persist dalam transaksi aktif tanpa commit penuh
        except Exception as exc:
            logger.error(
                "ProviderChain: gagal menyimpan ai_usage untuk provider '%s': %s",
                response.provider,
                exc,
            )

    async def _get_usage_percent(self, provider_name: str) -> float:
        """
        Hitung persentase penggunaan token bulan ini untuk ``provider_name``
        relatif terhadap batas yang dikonfigurasi.

        Menggunakan query SUM pada tabel ``ai_usage`` untuk bulan kalender berjalan.

        Returns:
            Float 0.0–1.0+ (bisa melebihi 1.0 jika sudah melewati batas).
            Mengembalikan 0.0 jika provider tidak memiliki batas atau query gagal.
        """
        from datetime import date

        from sqlalchemy import func, select

        from app.models.ai_usage import AiUsage

        limit = self._settings.ai_usage_limits.get(provider_name, 0)
        if limit <= 0:
            # Tidak ada batas atau batas tidak dikonfigurasi → anggap aman
            return 0.0

        # Awal bulan berjalan (UTC)
        today = date.today()
        month_start_str = f"{today.year}-{today.month:02d}-01"

        try:
            result = await self._db.execute(
                select(func.coalesce(func.sum(
                    AiUsage.prompt_tokens + AiUsage.completion_tokens
                ), 0)).where(
                    AiUsage.provider == provider_name,
                    AiUsage.success.is_(True),
                    AiUsage.created_at >= month_start_str,
                )
            )
            tokens_used: int = result.scalar_one() or 0
            return tokens_used / limit
        except Exception as exc:
            logger.warning(
                "ProviderChain: gagal membaca usage untuk '%s': %s — anggap 0%%",
                provider_name,
                exc,
            )
            return 0.0
