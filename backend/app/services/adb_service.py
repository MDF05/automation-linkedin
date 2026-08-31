"""
ADB Service — Komunikasi dengan HP Android via Android Debug Bridge.

Komponen ini mengirim perintah ke HP Android dan menyediakan:
- Deteksi perangkat yang terhubung (Requirements 1.1)
- Verifikasi instalasi LinkedIn (Requirements 1.3)
- Eksekusi aksi layar: tap, swipe, input teks (Requirements 1.3)
- Screenshot layar HP (Requirements 1.6)
- Navigasi aplikasi: open, back, home (Requirements 1.3)
- Timeout 30 detik untuk setiap perintah ADB (Requirements 1.4)

Design reference: services/adb/client.py dari design.md
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class ADBError(Exception):
    """Base exception untuk semua error ADB."""


class ADBTimeoutError(ADBError):
    """
    Raised ketika perintah ADB tidak selesai dalam batas waktu yang dikonfigurasi.

    Requirements: 1.4 — IF perintah ADB gagal dieksekusi dalam 30 detik,
    THEN ADB_Service SHALL menandai eksekusi sebagai timeout.
    """


class ADBDeviceNotFoundError(ADBError):
    """Raised ketika tidak ada perangkat yang terhubung atau device_id tidak ditemukan."""


class ADBCommandError(ADBError):
    """Raised ketika perintah ADB selesai tetapi mengembalikan exit code non-zero."""


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class ADBResult:
    """Hasil dari eksekusi perintah ADB."""

    success: bool
    output: str
    error: str
    return_code: int = 0


@dataclass
class DeviceInfo:
    """Informasi perangkat Android yang terhubung."""

    device_id: str
    state: str  # "device", "offline", "unauthorized", dsb.
    model: Optional[str] = None
    android_version: Optional[str] = None
    linkedin_installed: bool = False
    last_checked: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


# ---------------------------------------------------------------------------
# Koordinat relatif UI LinkedIn (dari design.md)
# ---------------------------------------------------------------------------

LINKEDIN_UI_MAP = {
    "new_post_button": (0.5, 0.92),
    "post_input": (0.5, 0.35),
    "publish_button": (0.85, 0.08),
    "comment_button": (0.15, 0.88),
    "jobs_search_bar": (0.5, 0.12),
}

LINKEDIN_PACKAGE = "com.linkedin.android"

# ---------------------------------------------------------------------------
# ADB Service
# ---------------------------------------------------------------------------


class ADBService:
    """
    Layanan ADB untuk mengontrol HP Android.

    Semua operasi bersifat async dan menggunakan asyncio.create_subprocess_exec
    untuk menjalankan perintah ADB. Timeout dikonfigurasi via Settings.adb_timeout.

    Requirements: 1.1, 1.3, 1.4, 1.6
    """

    def __init__(self, device_id: Optional[str] = None) -> None:
        """
        Inisialisasi ADB Service.

        Args:
            device_id: ID perangkat target. Jika None, menggunakan perangkat pertama.
        """
        self._device_id = device_id
        self._settings = get_settings()

    @property
    def timeout(self) -> int:
        """Timeout perintah ADB dalam detik (dari config)."""
        return self._settings.adb_timeout

    @property
    def screenshots_dir(self) -> Path:
        """Direktori untuk menyimpan screenshot."""
        return Path(self._settings.screenshots_dir)

    # ------------------------------------------------------------------
    # Internal runner
    # ------------------------------------------------------------------

    async def _run_command(
        self,
        cmd: List[str],
        timeout: Optional[int] = None,
    ) -> ADBResult:
        """
        Jalankan perintah ADB dan tunggu hasilnya dengan timeout.

        Args:
            cmd:     List token perintah, misal ['adb', 'devices'].
            timeout: Timeout dalam detik. Jika None, gunakan self.timeout.

        Returns:
            ADBResult dengan success, output, error, dan return_code.

        Raises:
            ADBTimeoutError: Jika perintah tidak selesai dalam batas waktu.

        Requirements: 1.4
        """
        effective_timeout = timeout if timeout is not None else self.timeout

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=float(effective_timeout)
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            raise ADBTimeoutError(
                f"Perintah ADB '{' '.join(cmd)}' timeout setelah {effective_timeout} detik"
            )

        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        success = proc.returncode == 0

        return ADBResult(
            success=success,
            output=output,
            error=error,
            return_code=proc.returncode or 0,
        )

    def _build_cmd(self, *args: str) -> List[str]:
        """Bangun daftar perintah ADB dengan device_id jika ada."""
        base = ["adb"]
        if self._device_id:
            base += ["-s", self._device_id]
        return base + list(args)

    # ------------------------------------------------------------------
    # Device Discovery — Requirements 1.1
    # ------------------------------------------------------------------

    async def get_connected_devices(self) -> List[DeviceInfo]:
        """
        List semua perangkat Android yang terhubung via `adb devices`.

        Returns:
            List DeviceInfo untuk setiap perangkat yang terdeteksi.

        Raises:
            ADBTimeoutError: Jika `adb devices` tidak selesai dalam timeout.

        Requirements: 1.1
        """
        result = await self._run_command(["adb", "devices", "-l"])

        devices: List[DeviceInfo] = []
        lines = result.output.strip().splitlines()

        # Baris pertama adalah header "List of devices attached"
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue

            # Format: "<device_id>  <state>  [model:<model> ...]"
            parts = line.split()
            if len(parts) < 2:
                continue

            device_id = parts[0]
            state = parts[1]

            # Ekstrak model dari info tambahan jika ada
            model: Optional[str] = None
            model_match = re.search(r"model:(\S+)", line)
            if model_match:
                model = model_match.group(1).replace("_", " ")

            devices.append(DeviceInfo(device_id=device_id, state=state, model=model))

        return devices

    # ------------------------------------------------------------------
    # LinkedIn Verification — Requirements 1.3
    # ------------------------------------------------------------------

    async def is_linkedin_installed(self, device_id: Optional[str] = None) -> bool:
        """
        Verifikasi apakah aplikasi LinkedIn terpasang di perangkat.

        Args:
            device_id: ID perangkat target. Override self._device_id jika diberikan.

        Returns:
            True jika LinkedIn terpasang, False jika tidak.

        Raises:
            ADBTimeoutError: Jika perintah timeout.

        Requirements: 1.3
        """
        target_id = device_id or self._device_id
        cmd_base = ["adb"]
        if target_id:
            cmd_base += ["-s", target_id]
        cmd = cmd_base + ["shell", "pm", "list", "packages", LINKEDIN_PACKAGE]

        result = await self._run_command(cmd)
        return LINKEDIN_PACKAGE in result.output

    # ------------------------------------------------------------------
    # Screen Actions — Requirements 1.3
    # ------------------------------------------------------------------

    async def execute_tap(self, x: int, y: int) -> ADBResult:
        """
        Ketuk layar pada koordinat pixel (x, y).

        Args:
            x: Koordinat X dalam pixel.
            y: Koordinat Y dalam pixel.

        Returns:
            ADBResult dari perintah tap.

        Raises:
            ADBTimeoutError: Jika perintah timeout.

        Requirements: 1.3
        """
        cmd = self._build_cmd("shell", "input", "tap", str(x), str(y))
        return await self._run_command(cmd)

    async def execute_swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 500,
    ) -> ADBResult:
        """
        Geser layar dari (x1, y1) ke (x2, y2) dalam durasi tertentu.

        Args:
            x1, y1:      Koordinat awal dalam pixel.
            x2, y2:      Koordinat akhir dalam pixel.
            duration_ms: Durasi swipe dalam milidetik.

        Returns:
            ADBResult dari perintah swipe.

        Raises:
            ADBTimeoutError: Jika perintah timeout.

        Requirements: 1.3
        """
        cmd = self._build_cmd(
            "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration_ms),
        )
        return await self._run_command(cmd)

    async def execute_input_text(self, text: str) -> ADBResult:
        """
        Input teks ke field yang sedang aktif.

        Untuk teks pendek (<= 50 karakter) gunakan `input text`.
        Untuk teks panjang (> 50 karakter) gunakan clipboard via `clipper.set`.

        Args:
            text: Teks yang akan diinput.

        Returns:
            ADBResult dari perintah input.

        Raises:
            ADBTimeoutError: Jika perintah timeout.

        Requirements: 1.3
        """
        if len(text) <= 50:
            # Escape karakter spesial untuk shell
            escaped = text.replace(" ", "%s").replace("'", "\\'")
            cmd = self._build_cmd("shell", "input", "text", escaped)
            return await self._run_command(cmd)
        else:
            # Teks panjang: gunakan clipboard
            return await self._input_via_clipboard(text)

    async def _input_via_clipboard(self, text: str) -> ADBResult:
        """
        Input teks panjang via clipboard menggunakan clipper broadcast.

        Sesuai design.md: adb shell am broadcast -a clipper.set -e text '<text>'
        kemudian tekan KEYCODE_PASTE (279).

        Requirements: 1.3 (clipboard untuk teks > 50 chars dari design.md)
        """
        escaped = text.replace("'", "\\'")
        clip_cmd = self._build_cmd(
            "shell", "am", "broadcast",
            "-a", "clipper.set",
            "-e", "text", f"'{escaped}'",
        )
        result = await self._run_command(clip_cmd)
        if not result.success:
            return result

        # Sedikit jeda agar clipboard terisi
        await asyncio.sleep(0.3)

        # Tekan KEYCODE_PASTE
        paste_cmd = self._build_cmd("shell", "input", "keyevent", "279")
        return await self._run_command(paste_cmd)

    # ------------------------------------------------------------------
    # Screenshot — Requirements 1.6
    # ------------------------------------------------------------------

    async def take_screenshot(self) -> str:
        """
        Ambil screenshot layar HP dan simpan ke direktori screenshots.

        Returns:
            Path relatif ke file screenshot yang disimpan,
            misal: 'static/screenshots/screenshot_<uuid>.png'.

        Raises:
            ADBTimeoutError: Jika perintah timeout.
            ADBCommandError: Jika screenshot gagal diambil.

        Requirements: 1.6
        """
        # Buat direktori jika belum ada
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        filename = f"screenshot_{uuid.uuid4().hex}.png"
        device_path = f"/sdcard/{filename}"
        local_path = self.screenshots_dir / filename

        # Ambil screenshot di perangkat
        screencap_cmd = self._build_cmd("shell", "screencap", "-p", device_path)
        result = await self._run_command(screencap_cmd)
        if not result.success:
            raise ADBCommandError(
                f"Gagal mengambil screenshot: {result.error}"
            )

        # Tarik file ke lokal
        pull_cmd = self._build_cmd("pull", device_path, str(local_path))
        pull_result = await self._run_command(pull_cmd)
        if not pull_result.success:
            raise ADBCommandError(
                f"Gagal mengunduh screenshot dari perangkat: {pull_result.error}"
            )

        # Hapus file sementara di perangkat
        rm_cmd = self._build_cmd("shell", "rm", "-f", device_path)
        await self._run_command(rm_cmd)  # best-effort, abaikan error

        # Kembalikan path relatif dari root statis
        rel_path = os.path.join("static", "screenshots", filename)
        return rel_path

    # ------------------------------------------------------------------
    # App Navigation — Requirements 1.3
    # ------------------------------------------------------------------

    async def open_app(self, package: str = LINKEDIN_PACKAGE) -> ADBResult:
        """
        Buka aplikasi berdasarkan nama package.

        Args:
            package: Nama package Android, default ke LinkedIn.

        Returns:
            ADBResult dari perintah monkey.

        Raises:
            ADBTimeoutError: Jika perintah timeout.

        Requirements: 1.3
        """
        cmd = self._build_cmd(
            "shell", "monkey",
            "-p", package,
            "-c", "android.intent.category.LAUNCHER",
            "1",
        )
        return await self._run_command(cmd)

    async def press_back(self) -> ADBResult:
        """
        Tekan tombol Back (KEYCODE_BACK = 4).

        Returns:
            ADBResult dari perintah keyevent.

        Raises:
            ADBTimeoutError: Jika perintah timeout.

        Requirements: 1.3
        """
        cmd = self._build_cmd("shell", "input", "keyevent", "4")
        return await self._run_command(cmd)

    async def press_home(self) -> ADBResult:
        """
        Tekan tombol Home (KEYCODE_HOME = 3).

        Returns:
            ADBResult dari perintah keyevent.

        Raises:
            ADBTimeoutError: Jika perintah timeout.

        Requirements: 1.3
        """
        cmd = self._build_cmd("shell", "input", "keyevent", "3")
        return await self._run_command(cmd)

    # ------------------------------------------------------------------
    # Device Info Helpers
    # ------------------------------------------------------------------

    async def get_device_model(self) -> str:
        """Ambil model perangkat dari property Android."""
        cmd = self._build_cmd("shell", "getprop", "ro.product.model")
        result = await self._run_command(cmd)
        return result.output.strip() if result.success else "Unknown"

    async def get_android_version(self) -> str:
        """Ambil versi Android dari property."""
        cmd = self._build_cmd("shell", "getprop", "ro.build.version.release")
        result = await self._run_command(cmd)
        return result.output.strip() if result.success else "Unknown"

    async def get_screen_resolution(self) -> tuple[int, int]:
        """
        Ambil resolusi layar perangkat dalam pixel.

        Returns:
            Tuple (width, height) dalam pixel.
        """
        cmd = self._build_cmd("shell", "wm", "size")
        result = await self._run_command(cmd)

        # Format: "Physical size: 1080x1920"
        match = re.search(r"(\d+)x(\d+)", result.output)
        if match:
            return int(match.group(1)), int(match.group(2))
        return 1080, 1920  # default umum

    def relative_to_pixel(
        self, rel_x: float, rel_y: float, width: int, height: int
    ) -> tuple[int, int]:
        """
        Konversi koordinat relatif (0.0-1.0) ke koordinat pixel aktual.

        Args:
            rel_x, rel_y: Koordinat relatif dari LINKEDIN_UI_MAP.
            width, height: Resolusi layar dalam pixel.

        Returns:
            Tuple (pixel_x, pixel_y).
        """
        return int(rel_x * width), int(rel_y * height)
