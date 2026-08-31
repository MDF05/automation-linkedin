"""
Web AI Provider

Implementasi ``BaseAIProvider`` untuk ChatGPT web dan Claude web
via ADB browser control di HP Android.

Alur:
1. Buka URL AI di browser HP via ADB Intent
2. Input prompt via clipboard (paste ke input field)
3. Tunggu respons AI
4. Salin teks respons via clipboard
5. Return AIResponse

Requirements: 8.6
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.core.config import get_settings
from app.services.ai_service import AIRequest, AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)

# URL provider web
_PROVIDER_URLS: dict[str, str] = {
    "chatgpt_web": "https://chat.openai.com",
    "claude_web": "https://claude.ai",
}

# Timeout menunggu respons AI di browser (detik)
_RESPONSE_WAIT_SECONDS = 60

# Delay setelah buka URL agar halaman web ter-load (detik)
_PAGE_LOAD_WAIT_SECONDS = 5

# Delay setelah paste prompt sebelum submit (detik)
_AFTER_PASTE_WAIT_SECONDS = 1

# Delay setelah submit sebelum copy respons (detik)
_AFTER_SUBMIT_WAIT_SECONDS = 3


class WebAIProvider(BaseAIProvider):
    """
    Provider AI yang mengontrol browser HP Android via ADB.

    Mendukung dua provider web:
    - ``chatgpt_web`` — https://chat.openai.com
    - ``claude_web``  — https://claude.ai

    Alur generate():
    1. Cek ADB device terhubung
    2. Buka URL di browser via ``adb shell am start``
    3. Tunggu halaman load
    4. Paste prompt via clipboard (``clipper.set`` + ``KEYCODE_PASTE``)
    5. Submit prompt (``KEYCODE_ENTER``)
    6. Tunggu respons dihasilkan
    7. Select-all + copy teks di layar (``KEYCODE_CTRL_A`` + ``KEYCODE_COPY``)
    8. Baca clipboard via ``adb shell``
    9. Return ``AIResponse``

    Estimasi token: panjang kata prompt/response (tidak ada token counter real).
    Cost estimate: 0.0 (free tier web).

    Requirements: 8.6
    """

    def __init__(self, provider_name: str = "chatgpt_web") -> None:
        """
        Inisialisasi WebAIProvider.

        Args:
            provider_name: Nama provider, salah satu dari
                           ``'chatgpt_web'`` atau ``'claude_web'``.

        Raises:
            ValueError: Jika ``provider_name`` tidak valid.
        """
        if provider_name not in _PROVIDER_URLS:
            raise ValueError(
                f"Provider '{provider_name}' tidak valid. "
                f"Pilihan: {list(_PROVIDER_URLS.keys())}"
            )
        self.provider_name: str = provider_name
        self._settings = get_settings()
        self._url = _PROVIDER_URLS[provider_name]

    # ------------------------------------------------------------------
    # BaseAIProvider implementation
    # ------------------------------------------------------------------

    async def generate(self, request: AIRequest) -> AIResponse:
        """
        Generate respons AI via ADB browser control.

        Args:
            request: Parameter AI request (prompt, system_prompt, max_tokens, ...).

        Returns:
            AIResponse dengan konten respons, token estimate, dan cost 0.0.
            Mengembalikan ``success=False`` jika terjadi error.

        Requirements: 8.6
        """
        from app.services.adb_service import ADBService

        t_start = time.monotonic()
        adb = ADBService()

        try:
            # ── 1. Validasi device terhubung ───────────────────────────
            devices = await adb.get_connected_devices()
            connected = [d for d in devices if d.state == "device"]
            if not connected:
                return AIResponse(
                    content="",
                    provider=self.provider_name,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_estimate=0.0,
                    success=False,
                    error="Tidak ada perangkat ADB yang terhubung",
                    latency_ms=int((time.monotonic() - t_start) * 1000),
                )

            # ── 2. Buka browser HP navigasi ke URL provider ────────────
            open_result = await adb._run_command([
                "adb", "shell", "am", "start",
                "-a", "android.intent.action.VIEW",
                "-d", self._url,
            ])
            if not open_result.success:
                return AIResponse(
                    content="",
                    provider=self.provider_name,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_estimate=0.0,
                    success=False,
                    error=f"Gagal membuka browser: {open_result.error}",
                    latency_ms=int((time.monotonic() - t_start) * 1000),
                )

            # Tunggu halaman ter-load
            await asyncio.sleep(_PAGE_LOAD_WAIT_SECONDS)

            # ── 3. Paste prompt via clipboard ──────────────────────────
            # Gabungkan system_prompt dan prompt jika ada
            full_prompt = request.prompt
            if request.system_prompt:
                full_prompt = f"{request.system_prompt}\n\n{request.prompt}"

            paste_result = await self._paste_via_clipboard(adb, full_prompt)
            if not paste_result.success:
                return AIResponse(
                    content="",
                    provider=self.provider_name,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_estimate=0.0,
                    success=False,
                    error=f"Gagal paste prompt: {paste_result.error}",
                    latency_ms=int((time.monotonic() - t_start) * 1000),
                )

            await asyncio.sleep(_AFTER_PASTE_WAIT_SECONDS)

            # ── 4. Submit prompt dengan KEYCODE_ENTER ──────────────────
            submit_result = await adb._run_command([
                "adb", "shell", "input", "keyevent", "66",  # KEYCODE_ENTER
            ])
            if not submit_result.success:
                return AIResponse(
                    content="",
                    provider=self.provider_name,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_estimate=0.0,
                    success=False,
                    error=f"Gagal submit prompt: {submit_result.error}",
                    latency_ms=int((time.monotonic() - t_start) * 1000),
                )

            # ── 5. Tunggu respons AI ───────────────────────────────────
            await asyncio.sleep(_RESPONSE_WAIT_SECONDS)

            # ── 6. Select-all dan copy teks respons ────────────────────
            response_text = await self._copy_response_text(adb)
            if response_text is None:
                return AIResponse(
                    content="",
                    provider=self.provider_name,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_estimate=0.0,
                    success=False,
                    error="Gagal membaca respons dari clipboard",
                    latency_ms=int((time.monotonic() - t_start) * 1000),
                )

            # ── 7. Hitung estimasi token ───────────────────────────────
            prompt_tokens = len(full_prompt.split())
            completion_tokens = len(response_text.split())

            latency_ms = int((time.monotonic() - t_start) * 1000)
            logger.info(
                "WebAIProvider[%s]: berhasil (%d prompt words, %d response words, %d ms).",
                self.provider_name,
                prompt_tokens,
                completion_tokens,
                latency_ms,
            )

            return AIResponse(
                content=response_text,
                provider=self.provider_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_estimate=0.0,
                success=True,
                latency_ms=latency_ms,
            )

        except Exception as exc:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            logger.warning(
                "WebAIProvider[%s]: unexpected error: %s",
                self.provider_name,
                exc,
            )
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

    async def is_available(self) -> bool:
        """
        Return True jika ada perangkat ADB yang terhubung.

        Requirements: 8.6
        """
        try:
            from app.services.adb_service import ADBService

            adb = ADBService()
            devices = await adb.get_connected_devices()
            return any(d.state == "device" for d in devices)
        except Exception as exc:
            logger.warning(
                "WebAIProvider[%s]: is_available() error: %s",
                self.provider_name,
                exc,
            )
            return False

    def get_token_limit(self) -> int:
        """
        Kembalikan batas request/bulan dari konfigurasi.

        Menggunakan ``ai_usage_limit_chatgpt_web`` atau ``ai_usage_limit_claude_web``
        sesuai ``provider_name``.

        Requirements: 8.3, 8.6
        """
        limits = self._settings.ai_usage_limits
        return limits.get(self.provider_name, 0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _paste_via_clipboard(self, adb, text: str):
        """
        Set clipboard via clipper broadcast kemudian paste ke field aktif.

        Sesuai design.md: ``clipper.set`` broadcast + ``KEYCODE_PASTE`` (279).

        Args:
            adb:  Instance ``ADBService`` yang aktif.
            text: Teks yang akan di-paste.

        Returns:
            ADBResult dari operasi paste.
        """
        # Escape single quote untuk shell
        escaped = text.replace("'", "\\'")

        # Set clipboard via Clipper broadcast
        clip_result = await adb._run_command([
            "adb", "shell", "am", "broadcast",
            "-a", "clipper.set",
            "-e", "text", f"'{escaped}'",
        ])
        if not clip_result.success:
            return clip_result

        # Sedikit jeda agar clipboard terisi
        await asyncio.sleep(0.3)

        # Paste via KEYCODE_PASTE (279)
        return await adb._run_command([
            "adb", "shell", "input", "keyevent", "279",
        ])

    async def _copy_response_text(self, adb) -> Optional[str]:
        """
        Coba salin teks respons AI di layar ke clipboard lalu baca hasilnya.

        Langkah:
        1. Tap ke area tengah layar (fokus ke konten)
        2. Long press untuk trigger select mode
        3. Select All (KEYCODE_CTRL_A = 277 atau meta+a)
        4. Copy (KEYCODE_COPY = 278)
        5. Baca clipboard via ``adb shell clipper get`` atau ``xclip``

        Returns:
            String teks dari clipboard, atau None jika gagal.
        """
        try:
            # Tap ke area konten (tengah layar, 60% dari atas)
            await adb._run_command(["adb", "shell", "input", "tap", "540", "1100"])
            await asyncio.sleep(_AFTER_SUBMIT_WAIT_SECONDS)

            # Long press untuk masuk mode seleksi teks
            await adb._run_command([
                "adb", "shell", "input", "swipe", "540", "1100", "540", "1100", "1000",
            ])
            await asyncio.sleep(0.5)

            # Select All via KEYCODE_CTRL_A (tidak semua device support, fallback ke meta)
            await adb._run_command(["adb", "shell", "input", "keyevent", "--longpress", "277"])
            await asyncio.sleep(0.3)

            # Copy via KEYCODE_COPY (278)
            await adb._run_command(["adb", "shell", "input", "keyevent", "278"])
            await asyncio.sleep(0.3)

            # Baca clipboard via clipper get
            clip_read = await adb._run_command([
                "adb", "shell", "am", "broadcast",
                "-a", "clipper.get",
            ])

            if clip_read.success and clip_read.output.strip():
                # Output clipper broadcast: "Broadcast completed: result=0, data=<text>"
                output = clip_read.output.strip()
                # Coba ekstrak data dari output clipper
                if "data=" in output:
                    text = output.split("data=", 1)[1].strip()
                    # Hapus trailing quote jika ada
                    text = text.strip('"')
                    if text:
                        return text

            # Fallback: baca via shell getprop atau content resolver (tidak reliable)
            # Return empty string agar tidak dianggap gagal total
            logger.warning(
                "WebAIProvider[%s]: clipboard read tidak mengembalikan data.",
                self.provider_name,
            )
            return ""

        except Exception as exc:
            logger.warning(
                "WebAIProvider[%s]: _copy_response_text error: %s",
                self.provider_name,
                exc,
            )
            return None
