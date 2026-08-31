"""
Anti-Ban Controller — Simulasi perilaku manusia untuk menghindari deteksi bot LinkedIn.

Komponen ini:
- Menerapkan delay acak antar aksi (Requirements 9.1)
- Membatasi aksi harian per modul dari DB + config (Requirements 9.2, 9.3)
- Mensimulasikan scroll manusia dengan kecepatan bervariasi via ADB (Requirements 9.4, 9.5)
- Mendeteksi halaman CAPTCHA/security challenge via OCR screenshot (Requirements 9.6)
- Memastikan interval antar sesi minimal 30 menit (Requirements 9.7)

Design reference: services/anti_ban/ dari design.md
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import date, datetime, time, timezone
from typing import Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CAPTCHA detection keywords (Indonesian + English)
# From design.md Anti-Ban Strategy section
# ---------------------------------------------------------------------------

CAPTCHA_KEYWORDS: list[str] = [
    "verify",
    "verifikasi",
    "captcha",
    "robot",
    "security check",
    "pemeriksaan keamanan",
    "prove you're human",
    "unusual activity",
]


# ---------------------------------------------------------------------------
# Default daily limits (from design.md settings table)
# ---------------------------------------------------------------------------

DEFAULT_DAILY_LIMITS: Dict[str, int] = {
    "post": 3,
    "comment": 15,
    "apply": 20,
}


# ---------------------------------------------------------------------------
# Public API — Pure Functions
# ---------------------------------------------------------------------------


def get_random_delay(min_s: float, max_s: float) -> float:
    """
    Kembalikan nilai delay acak dalam range [min_s, max_s] detik.

    Args:
        min_s: Batas bawah delay dalam detik (inklusif).
        max_s: Batas atas delay dalam detik (inklusif).

    Returns:
        Nilai float delay acak dalam range yang diberikan.

    Raises:
        ValueError: Jika min_s > max_s.

    Requirements: 9.1
    """
    if min_s > max_s:
        raise ValueError(
            f"min_s ({min_s}) harus <= max_s ({max_s})"
        )
    return random.uniform(min_s, max_s)


def check_daily_limit(module: str, count_today: int, limits: Dict[str, int]) -> bool:
    """
    Cek apakah aksi pada modul tertentu masih diizinkan hari ini (pure function).

    Fungsi ini bersifat pure (tidak mengakses DB) sehingga mudah di-unit-test.
    Pemanggil bertanggung jawab menyediakan count_today dari DB dan limits dari config.

    Args:
        module:      Nama modul — 'post', 'comment', atau 'apply'.
        count_today: Jumlah aksi yang sudah dilakukan hari ini untuk modul ini.
        limits:      Dict berisi batas harian, misal {"post": 3, "comment": 15, "apply": 20}.

    Returns:
        True jika masih diizinkan (count_today < limit), False jika batas sudah tercapai.

    Requirements: 9.2, 9.3
    """
    limit = limits.get(module)
    if limit is None:
        # Modul tidak dikenal atau tidak dikonfigurasi — izinkan secara default
        return True
    return count_today < limit


def detect_captcha(text: str) -> bool:
    """
    Deteksi apakah teks yang diekstrak dari layar mengandung indikasi CAPTCHA
    atau security challenge LinkedIn.

    Menggunakan keyword matching case-insensitive terhadap daftar CAPTCHA_KEYWORDS
    yang telah didefinisikan (dari design.md).

    Args:
        text: Teks yang diekstrak oleh OCR dari screenshot layar HP.

    Returns:
        True jika CAPTCHA/security challenge terdeteksi, False jika tidak.

    Requirements: 9.6
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CAPTCHA_KEYWORDS)


# ---------------------------------------------------------------------------
# Async — DB-backed daily limit check
# ---------------------------------------------------------------------------


async def check_daily_limit_from_db(
    module: str,
    db: AsyncSession,
    limits: Optional[Dict[str, int]] = None,
) -> bool:
    """
    Cek batas harian aksi per modul langsung dari database.

    Mengambil count hari ini dari tabel yang relevan (posts, interactions,
    job_applications) dan membandingkan dengan limit dari config/settings.

    Args:
        module:  Nama modul — 'post', 'comment', atau 'apply'.
        db:      AsyncSession SQLAlchemy.
        limits:  Override limits dict. Jika None, gunakan DEFAULT_DAILY_LIMITS
                 yang di-merge dengan nilai dari config.

    Returns:
        True jika masih diizinkan, False jika batas sudah tercapai.

    Requirements: 9.2, 9.3
    """
    # Impor model di sini untuk menghindari circular imports
    from app.models.interaction import Interaction
    from app.models.job_application import JobApplication
    from app.models.post import Post

    settings = get_settings()

    # Bangun effective limits dari config atau override
    if limits is None:
        limits = {
            "post": settings.anti_ban_posts_per_day,
            "comment": settings.anti_ban_comments_per_day,
            "apply": settings.anti_ban_applies_per_day,
        }

    # Waktu awal hari ini (UTC)
    today_start = datetime.combine(
        date.today(), time.min, tzinfo=timezone.utc
    )

    count: int = 0

    if module == "post":
        result = await db.execute(
            select(func.count(Post.id)).where(
                Post.status == "posted",
                Post.posted_at >= today_start,
            )
        )
        count = result.scalar_one() or 0

    elif module == "comment":
        result = await db.execute(
            select(func.count(Interaction.id)).where(
                Interaction.action_type == "comment",
                Interaction.status == "success",
                Interaction.created_at >= today_start,
            )
        )
        count = result.scalar_one() or 0

    elif module == "apply":
        result = await db.execute(
            select(func.count(JobApplication.id)).where(
                JobApplication.status == "applied",
                JobApplication.applied_at >= today_start,
            )
        )
        count = result.scalar_one() or 0

    else:
        # Modul tidak dikenal — izinkan secara default
        return True

    return check_daily_limit(module, count, limits)


# ---------------------------------------------------------------------------
# Async — Scroll simulation (dengan atau tanpa ADB)
# ---------------------------------------------------------------------------

# Kecepatan scroll pattern (duration swipe dalam ms)
_SCROLL_PATTERNS = {
    "slow_read": {
        "swipe_count": (3, 7),
        "duration_ms": (800, 1500),
        "pause_s": (1.5, 4.0),
        # Peluang idle (Requirements 9.5)
        "idle_chance": 0.4,
        "idle_s": (5.0, 30.0),
    },
    "skim": {
        "swipe_count": (8, 15),
        "duration_ms": (300, 600),
        "pause_s": (0.3, 1.0),
        "idle_chance": 0.1,
        "idle_s": (5.0, 15.0),
    },
    "deep_read": {
        "swipe_count": (2, 4),
        "duration_ms": (1200, 2000),
        "pause_s": (5.0, 15.0),
        "idle_chance": 0.6,
        "idle_s": (10.0, 30.0),
    },
}

# Koordinat swipe relatif untuk scroll feed (center-screen down-to-up)
_SWIPE_X = 0.5
_SWIPE_START_Y = 0.7
_SWIPE_END_Y = 0.3


async def simulate_human_scroll(
    device_id: Optional[str] = None,
    adb_service: Optional[object] = None,
    pattern: Optional[str] = None,
    _fast_mode: bool = False,  # dipercepat untuk unit test
) -> None:
    """
    Simulasikan pola scroll manusia dengan kecepatan bervariasi dan aksi idle acak.

    Mendukung dua mode:
    - Dengan ADB: jika `adb_service` diberikan, eksekusi swipe nyata via ADB.
    - Tanpa ADB: fallback ke asyncio.sleep untuk simulasi waktu (testing/dry-run).

    Tiga pola scroll tersedia (dipilih acak jika pattern tidak ditentukan):
    - ``slow_read``  — 3–7 swipe lambat, sering berhenti (baca sungguhan)
    - ``skim``       — 8–15 swipe cepat, jarang berhenti (scan cepat)
    - ``deep_read``  — 2–4 swipe sangat lambat, berhenti lama (baca detail)

    Idle acak (5–30 detik) disisipkan berdasarkan probabilitas per pola untuk
    mensimulasikan perilaku "membaca" pada feed.

    Args:
        device_id:   ID perangkat Android (digunakan oleh adb_service jika perlu).
        adb_service: Instance ADBService. Jika None, simulasi via asyncio.sleep.
        pattern:     Nama pola scroll ('slow_read', 'skim', 'deep_read').
                     Jika None, dipilih secara acak.
        _fast_mode:  True untuk mempercepat delay (digunakan dalam unit test).

    Requirements: 9.4, 9.5
    """
    # Pilih pola
    chosen_pattern = pattern or random.choice(list(_SCROLL_PATTERNS.keys()))
    cfg = _SCROLL_PATTERNS.get(chosen_pattern, _SCROLL_PATTERNS["skim"])

    swipe_count = random.randint(*cfg["swipe_count"])
    speed_factor = 0.01 if _fast_mode else 1.0  # percepat 100x untuk test

    # Resolusi default (1080x1920) untuk konversi koordinat relatif
    width, height = 1080, 1920
    if adb_service is not None:
        try:
            width, height = await adb_service.get_screen_resolution()
        except Exception:
            pass  # gunakan default jika gagal

    for i in range(swipe_count):
        duration_ms = random.randint(*cfg["duration_ms"])

        if adb_service is not None:
            # Konversi koordinat relatif → pixel
            x = int(_SWIPE_X * width)
            y_start = int(_SWIPE_START_Y * height)
            y_end = int(_SWIPE_END_Y * height)
            try:
                await adb_service.execute_swipe(x, y_start, x, y_end, duration_ms)
            except Exception as exc:
                logger.warning(
                    "simulate_human_scroll: swipe gagal (step %d/%d): %s",
                    i + 1, swipe_count, exc,
                )
        else:
            # Dry-run: tidur selama durasi swipe (dipersimulasikan)
            await asyncio.sleep(duration_ms / 1000.0 * speed_factor)

        # Jeda antar swipe (baca konten)
        pause_s = random.uniform(*cfg["pause_s"])
        await asyncio.sleep(pause_s * speed_factor)

        # Aksi idle acak — Requirements 9.5
        if random.random() < cfg["idle_chance"]:
            idle_s = random.uniform(*cfg["idle_s"])
            logger.debug(
                "simulate_human_scroll: idle %.1fs (pola=%s, step=%d/%d)",
                idle_s, chosen_pattern, i + 1, swipe_count,
            )
            await asyncio.sleep(idle_s * speed_factor)


# ---------------------------------------------------------------------------
# Async — CAPTCHA detection dari screenshot (OCR)
# ---------------------------------------------------------------------------


async def detect_captcha_from_screenshot(
    screenshot_path: str,
) -> bool:
    """
    Deteksi halaman CAPTCHA / security challenge dari file screenshot via OCR.

    Pipeline:
    1. Baca screenshot dari path
    2. Ekstrak teks menggunakan ocr_service.extract_text()
    3. Periksa teks menggunakan detect_captcha() (keyword matching)

    Args:
        screenshot_path: Path ke file screenshot (str atau Path).

    Returns:
        True jika CAPTCHA/security challenge terdeteksi, False jika tidak.
        Juga False jika OCR gagal (graceful degradation — jangan stop bot karena
        error OCR, hanya stop jika CAPTCHA benar-benar terdeteksi).

    Requirements: 9.6
    """
    from app.services.ocr_service import OCREngineUnavailableError, extract_text

    try:
        ocr_result = extract_text(screenshot_path)
        return detect_captcha(ocr_result.text)
    except OCREngineUnavailableError:
        logger.warning(
            "detect_captcha_from_screenshot: OCR tidak tersedia, "
            "CAPTCHA tidak dapat dideteksi dari %s",
            screenshot_path,
        )
        return False
    except Exception as exc:
        logger.warning(
            "detect_captcha_from_screenshot: gagal memproses %s — %s",
            screenshot_path, exc,
        )
        return False


# ---------------------------------------------------------------------------
# Async — Session gap enforcement (Requirements 9.7)
# ---------------------------------------------------------------------------


async def enforce_session_gap(
    last_session_end: Optional[datetime] = None,
    gap_minutes: Optional[int] = None,
) -> float:
    """
    Pastikan interval minimal antar sesi engage berturut-turut.

    Jika sesi terakhir selesai kurang dari `gap_minutes` yang lalu,
    fungsi ini akan tidur selama sisa waktu tunggu.

    Args:
        last_session_end: Waktu selesainya sesi engage sebelumnya (timezone-aware UTC).
                          Jika None, tidak ada tunggu.
        gap_minutes:      Interval minimum dalam menit.
                          Jika None, ambil dari config (default 30 menit).

    Returns:
        Jumlah detik yang ditunggu (0.0 jika tidak perlu tunggu).

    Requirements: 9.7
    """
    if last_session_end is None:
        return 0.0

    settings = get_settings()
    effective_gap_s = (gap_minutes or settings.anti_ban_session_gap_minutes) * 60.0

    now = datetime.now(tz=timezone.utc)
    elapsed_s = (now - last_session_end).total_seconds()
    remaining_s = effective_gap_s - elapsed_s

    if remaining_s > 0:
        logger.info(
            "enforce_session_gap: menunggu %.0f detik sebelum sesi berikutnya "
            "(gap minimum %d menit)",
            remaining_s,
            gap_minutes or settings.anti_ban_session_gap_minutes,
        )
        await asyncio.sleep(remaining_s)
        return remaining_s

    return 0.0
