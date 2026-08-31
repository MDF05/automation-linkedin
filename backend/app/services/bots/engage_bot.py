"""
Engage Bot — Module C: Auto Interaksi dengan Audiens LinkedIn.

Komponen ini:
- Scroll beranda LinkedIn dan ambil screenshot setiap 3–5 detik (Requirements 4.1)
- Panggil OCR untuk mengekstrak teks dari screenshot (Requirements 4.2)
- Skip post jika teks < 10 karakter (Requirements 4.8)
- Skip post jika URL sudah ada di interactions dalam 7 hari (Requirements 4.9)
- Filter topik jika konfigurasi aktif (Requirements 4.10)
- Generate komentar via AI 20–200 karakter (Requirements 4.3, 4.4)
- Ketik dan kirim komentar via ADB, catat ke Interaction (Requirements 4.5, 4.6)
- Cek batas harian via anti_ban sebelum setiap komentar (Requirements 4.7)
- Anti-ban: delay 3–10 menit antar komentar (Requirements 4.7)
- Deteksi CAPTCHA dan hentikan sesi jika terdeteksi (Requirements 9.6)

Requirements: 4.1–4.10
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot_log import BotLog
from app.models.interaction import Interaction
from app.services import anti_ban
from app.services import log_service
from app.services.ai_service import AIRequest
from app.services.ocr_service import OCRInsufficientTextError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Koordinat relatif UI LinkedIn (disesuaikan dengan LINKEDIN_UI_MAP)
# ---------------------------------------------------------------------------

# Tombol komentar di bawah sebuah post
_COMMENT_BTN = (0.15, 0.88)

# Area input komentar (setelah tap tombol comment)
_COMMENT_INPUT = (0.5, 0.75)

# Tombol kirim/send komentar
_COMMENT_SEND_BTN = (0.9, 0.75)

# ---------------------------------------------------------------------------
# Timing constants — Requirements 4.1, 4.7
# ---------------------------------------------------------------------------

# Interval screenshot (detik) — Requirements 4.1
_SCREENSHOT_INTERVAL_MIN = 3.0
_SCREENSHOT_INTERVAL_MAX = 5.0

# Interval antar komentar (menit) — Requirements 4.7
_BETWEEN_COMMENTS_MIN_MIN = 3.0
_BETWEEN_COMMENTS_MAX_MIN = 10.0

# Batas panjang komentar — Requirements 4.4
_COMMENT_MIN_LEN = 20
_COMMENT_MAX_LEN = 200

# Jendela deduplikasi URL interaksi (hari) — Requirements 4.9
_INTERACTION_DEDUP_DAYS = 7

# Delay antar tap/navigasi (detik) — Requirements 9.1
_NAV_DELAY_MIN = 2.0
_NAV_DELAY_MAX = 5.0
_TAP_DELAY_MIN = 1.0
_TAP_DELAY_MAX = 3.0

# System prompt untuk AI generate komentar — Requirements 4.3, 4.4
_COMMENT_SYSTEM_PROMPT = (
    "Kamu adalah asisten yang membantu memberikan komentar LinkedIn yang natural, "
    "relevan, dan profesional. Buat komentar yang singkat dan kontekstual. "
    f"Panjang komentar HARUS antara {_COMMENT_MIN_LEN}–{_COMMENT_MAX_LEN} karakter. "
    "Jangan gunakan hashtag atau emoji berlebihan. Tulis hanya teks komentar, "
    "tanpa tanda kutip atau penjelasan tambahan."
)


# ---------------------------------------------------------------------------
# EngageBot
# ---------------------------------------------------------------------------


class EngageBot:
    """
    Bot untuk berinteraksi otomatis dengan feed LinkedIn via ADB.

    Urutan eksekusi sesi:
    1. Cek batas harian komentar via anti_ban
    2. Buka aplikasi LinkedIn
    3. Loop hingga durasi habis atau batas harian tercapai:
       a. Delay acak 3–5 detik (interval screenshot)
       b. Scroll feed via simulate_human_scroll atau adb swipe
       c. Ambil screenshot
       d. Ekstrak teks via OCR
       e. Skip jika teks < 10 karakter
       f. Skip jika topik tidak cocok (filter aktif)
       g. Skip jika URL sudah ada dalam 7 hari
       h. Generate komentar via AI (20–200 karakter)
       i. Cek batas harian sebelum posting
       j. Ketik dan kirim komentar via ADB
       k. Simpan ke tabel Interaction
       l. Log ke BotLog
       m. Delay 3–10 menit (anti-ban)

    Requirements: 4.1–4.10
    """

    def __init__(
        self,
        adb_service: Any,
        ai_service: Any,
        ocr_service: Any,
        log_service_module: Any = None,
        websocket_manager: Optional[Any] = None,
    ) -> None:
        """
        Inisialisasi EngageBot.

        Args:
            adb_service:        Instance ADBService untuk kontrol HP Android.
            ai_service:         Provider AI dengan method .generate(AIRequest).
                                Bisa berupa ProviderChain atau BaseAIProvider.
            ocr_service:        Module atau objek OCR dengan .extract_text(path).
            log_service_module: Module log_service (opsional, default import global).
            websocket_manager:  Instance WebSocket ConnectionManager (opsional).
        """
        self._adb = adb_service
        self._ai = ai_service
        self._ocr = ocr_service
        self._log_svc = log_service_module or log_service
        self._ws = websocket_manager
        self._stop_requested = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """
        Minta loop sesi untuk berhenti di iterasi berikutnya.

        Berguna untuk penghentian graceful dari luar (misalnya via API endpoint
        atau handler disconnect WebSocket).
        """
        self._stop_requested = True
        logger.info("EngageBot: stop() dipanggil — loop akan berhenti setelah iterasi ini.")

    async def run_engage_session(
        self,
        duration_minutes: int,
        db: AsyncSession,
        topic_keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Jalankan sesi engage otomatis selama `duration_minutes` menit.

        Args:
            duration_minutes: Durasi maksimum sesi dalam menit.
            db:               AsyncSession SQLAlchemy yang aktif.
            topic_keywords:   Daftar kata kunci topik filter (Requirements 4.10).
                              Jika None atau kosong, semua topik diproses.

        Returns:
            Dict ringkasan sesi: jumlah komentar terkirim, skip, error, dll.

        Requirements: 4.1–4.10
        """
        self._stop_requested = False
        task_id = str(uuid.uuid4())
        session_start = datetime.now(tz=timezone.utc)
        session_end = session_start + timedelta(minutes=duration_minutes)

        stats: Dict[str, Any] = {
            "task_id": task_id,
            "comments_sent": 0,
            "skipped_short_text": 0,
            "skipped_topic_filter": 0,
            "skipped_duplicate_url": 0,
            "skipped_daily_limit": 0,
            "errors": 0,
            "captcha_detected": False,
            "started_at": session_start.isoformat(),
            "ended_at": None,
        }

        logger.info(
            "EngageBot: memulai sesi engage (task=%s, durasi=%d menit)",
            task_id, duration_minutes,
        )

        try:
            # ----------------------------------------------------------
            # Step 0: Cek batas harian sebelum mulai — Requirements 4.7
            # ----------------------------------------------------------
            can_comment = await anti_ban.check_daily_limit_from_db("comment", db)
            if not can_comment:
                logger.warning(
                    "EngageBot: batas harian komentar sudah tercapai, sesi dibatalkan."
                )
                await self._log(
                    db=db, task_id=task_id,
                    action="scroll_feed",
                    status="skipped",
                    message="Batas harian komentar sudah tercapai sebelum sesi dimulai",
                    module="C",
                )
                stats["skipped_daily_limit"] += 1
                return stats

            # ----------------------------------------------------------
            # Step 1: Buka LinkedIn — Requirements 4.1
            # ----------------------------------------------------------
            await self._open_linkedin(task_id=task_id, db=db)

            # ----------------------------------------------------------
            # Main loop — berjalan hingga durasi habis atau stop diminta
            # ----------------------------------------------------------
            while datetime.now(tz=timezone.utc) < session_end and not self._stop_requested:
                try:
                    await self._engage_iteration(
                        task_id=task_id,
                        db=db,
                        topic_keywords=topic_keywords,
                        stats=stats,
                        session_end=session_end,
                    )
                except _DailyLimitReached:
                    logger.info(
                        "EngageBot: batas harian tercapai, menghentikan sesi (task=%s).",
                        task_id,
                    )
                    stats["skipped_daily_limit"] += 1
                    break
                except _CaptchaDetected:
                    logger.warning(
                        "EngageBot: CAPTCHA terdeteksi! Menghentikan semua aksi (task=%s).",
                        task_id,
                    )
                    stats["captcha_detected"] = True
                    await self._log(
                        db=db, task_id=task_id,
                        action="detect_captcha",
                        status="failed",
                        message="CAPTCHA / security challenge terdeteksi di layar LinkedIn",
                        module="C",
                    )
                    await self._emit_progress(
                        task_id=task_id,
                        step="detect_captcha",
                        message="CAPTCHA terdeteksi! Sesi dihentikan.",
                        status="failed",
                    )
                    break
                except Exception as exc:
                    stats["errors"] += 1
                    logger.error(
                        "EngageBot: error pada iterasi (task=%s): %s",
                        task_id, exc, exc_info=True,
                    )
                    # Lanjutkan ke iterasi berikutnya agar satu error tidak menghentikan sesi
                    await asyncio.sleep(anti_ban.get_random_delay(5.0, 15.0))

        except Exception as exc:
            stats["errors"] += 1
            logger.error(
                "EngageBot: error fatal sesi (task=%s): %s",
                task_id, exc, exc_info=True,
            )
            await self._log(
                db=db, task_id=task_id,
                action="scroll_feed",
                status="failed",
                message=f"Error fatal sesi engage: {exc}",
                error_detail=str(exc),
                stack_trace=traceback.format_exc(),
                module="C",
            )

        finally:
            stats["ended_at"] = datetime.now(tz=timezone.utc).isoformat()
            logger.info(
                "EngageBot: sesi selesai (task=%s) — "
                "komentar=%d, skip=%d+%d+%d, error=%d, captcha=%s",
                task_id,
                stats["comments_sent"],
                stats["skipped_short_text"],
                stats["skipped_topic_filter"],
                stats["skipped_duplicate_url"],
                stats["errors"],
                stats["captcha_detected"],
            )

        return stats

    # ------------------------------------------------------------------
    # Private — Core iteration
    # ------------------------------------------------------------------

    async def _engage_iteration(
        self,
        task_id: str,
        db: AsyncSession,
        topic_keywords: Optional[List[str]],
        stats: Dict[str, Any],
        session_end: datetime,
    ) -> None:
        """
        Satu iterasi loop engage: scroll → screenshot → OCR → filter → comment.

        Raises:
            _DailyLimitReached: Batas harian komentar tercapai.
            _CaptchaDetected:   CAPTCHA terdeteksi di layar.
        """
        # ── a. Delay acak interval screenshot (3–5 detik) — Requirements 4.1 ──
        interval = anti_ban.get_random_delay(
            _SCREENSHOT_INTERVAL_MIN, _SCREENSHOT_INTERVAL_MAX
        )
        await asyncio.sleep(interval)

        # Cek stop dan durasi setelah delay
        if self._stop_requested or datetime.now(tz=timezone.utc) >= session_end:
            return

        # ── b. Scroll feed manusiawi — Requirements 9.4, 9.5 ──────────────────
        await self._scroll_feed(task_id=task_id, db=db)

        # ── c. Ambil screenshot — Requirements 4.1 ────────────────────────────
        screenshot_path = await self._take_screenshot(task_id=task_id, db=db)

        # ── CAPTCHA check — Requirements 9.6 ──────────────────────────────────
        try:
            captcha_found = await anti_ban.detect_captcha_from_screenshot(screenshot_path)
            if captcha_found:
                raise _CaptchaDetected()
        except _CaptchaDetected:
            raise
        except Exception:
            pass  # graceful degradation: OCR gagal bukan alasan hentikan sesi

        # ── d. Ekstrak teks via OCR — Requirements 4.2 ────────────────────────
        ocr_text = await self._extract_ocr_text(
            task_id=task_id, db=db,
            screenshot_path=screenshot_path, stats=stats,
        )
        if ocr_text is None:
            # Teks terlalu pendek, sudah dicatat dan stat di-update di helper
            return

        # ── e. Skip jika teks < 10 karakter (sudah ditangani di helper) ───────
        # (handled inside _extract_ocr_text)

        # ── f. Filter topik — Requirements 4.10 ───────────────────────────────
        if topic_keywords and not self._matches_topic(ocr_text, topic_keywords):
            logger.debug(
                "EngageBot: skip — tidak ada keyword topik dalam teks (task=%s)", task_id
            )
            stats["skipped_topic_filter"] += 1
            await self._log(
                db=db, task_id=task_id,
                action="read_ocr",
                status="skipped",
                message="Post dilewati: tidak ada keyword topik yang cocok",
                screenshot_path=screenshot_path,
                module="C",
            )
            return

        # ── g. Cek duplikasi URL dalam 7 hari — Requirements 4.9 ──────────────
        # Gunakan screenshot_path sebagai proxy URL karena URL post LinkedIn
        # tidak selalu dapat diekstrak via ADB; di implementasi nyata, gunakan
        # URL yang diekstrak dari metadata post atau OCR teks URL.
        post_url = self._extract_post_url(ocr_text, screenshot_path)
        if await self._is_duplicate_url(post_url, db):
            logger.debug(
                "EngageBot: skip — URL sudah ada di interactions 7 hari (task=%s)", task_id
            )
            stats["skipped_duplicate_url"] += 1
            await self._log(
                db=db, task_id=task_id,
                action="read_ocr",
                status="skipped",
                message=f"Post dilewati: URL sudah ada dalam {_INTERACTION_DEDUP_DAYS} hari terakhir",
                screenshot_path=screenshot_path,
                module="C",
            )
            return

        # ── h. Generate komentar via AI — Requirements 4.3, 4.4 ───────────────
        comment_text = await self._generate_comment(
            task_id=task_id, db=db,
            post_text=ocr_text, screenshot_path=screenshot_path,
        )
        if comment_text is None:
            stats["errors"] += 1
            return

        # ── i. Cek batas harian sebelum posting — Requirements 4.7 ────────────
        can_comment = await anti_ban.check_daily_limit_from_db("comment", db)
        if not can_comment:
            raise _DailyLimitReached()

        # ── j. Ketik dan kirim komentar via ADB — Requirements 4.5 ────────────
        await self._post_comment(
            task_id=task_id, db=db,
            comment_text=comment_text,
            post_url=post_url,
            post_text=ocr_text,
            screenshot_path=screenshot_path,
        )
        stats["comments_sent"] += 1

        # ── m. Delay anti-ban 3–10 menit antar komentar — Requirements 4.7 ────
        if not self._stop_requested and datetime.now(tz=timezone.utc) < session_end:
            wait_s = anti_ban.get_random_delay(
                _BETWEEN_COMMENTS_MIN_MIN * 60,
                _BETWEEN_COMMENTS_MAX_MIN * 60,
            )
            logger.info(
                "EngageBot: menunggu %.0f detik sebelum komentar berikutnya (task=%s)",
                wait_s, task_id,
            )
            await self._log(
                db=db, task_id=task_id,
                action="anti_ban_delay",
                status="success",
                message=f"Anti-ban delay {wait_s:.0f} detik sebelum komentar berikutnya",
                module="C",
            )
            await asyncio.sleep(wait_s)

    # ------------------------------------------------------------------
    # Private — Individual steps
    # ------------------------------------------------------------------

    async def _open_linkedin(self, task_id: str, db: AsyncSession) -> None:
        """Buka aplikasi LinkedIn di HP."""
        await self._emit_progress(
            task_id=task_id,
            step="open_linkedin",
            message="Membuka aplikasi LinkedIn...",
        )
        await self._adb.open_app("com.linkedin.android")
        await self._log(
            db=db, task_id=task_id,
            action="open_linkedin",
            status="success",
            message="Aplikasi LinkedIn berhasil dibuka untuk sesi engage",
            module="C",
        )
        # Tunggu LinkedIn selesai load
        delay = anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX)
        await asyncio.sleep(delay)

    async def _scroll_feed(self, task_id: str, db: AsyncSession) -> None:
        """Scroll feed LinkedIn dengan pola scroll manusiawi."""
        try:
            await anti_ban.simulate_human_scroll(adb_service=self._adb)
        except Exception as exc:
            # Fallback: scroll sederhana via adb jika simulate_human_scroll gagal
            logger.warning(
                "EngageBot: simulate_human_scroll gagal (%s), fallback adb swipe", exc
            )
            try:
                width, height = await self._adb.get_screen_resolution()
                x = int(0.5 * width)
                y_start = int(0.7 * height)
                y_end = int(0.3 * height)
                await self._adb.execute_swipe(x, y_start, x, y_end, 600)
            except Exception as swipe_exc:
                logger.warning(
                    "EngageBot: fallback swipe juga gagal: %s", swipe_exc
                )

        await self._log(
            db=db, task_id=task_id,
            action="scroll_feed",
            status="success",
            message="Scroll feed LinkedIn dilakukan",
            module="C",
        )

    async def _take_screenshot(self, task_id: str, db: AsyncSession) -> str:
        """
        Ambil screenshot layar HP.

        Returns:
            Path relatif ke file screenshot.
        """
        screenshot_path = await self._adb.take_screenshot()
        await self._log(
            db=db, task_id=task_id,
            action="screenshot",
            status="success",
            message=f"Screenshot diambil: {screenshot_path}",
            screenshot_path=screenshot_path,
            module="C",
        )
        return screenshot_path

    async def _extract_ocr_text(
        self,
        task_id: str,
        db: AsyncSession,
        screenshot_path: str,
        stats: Dict[str, Any],
    ) -> Optional[str]:
        """
        Ekstrak teks dari screenshot via OCR.

        Returns:
            Teks hasil OCR, atau None jika teks < 10 karakter (post diskip).

        Requirements: 4.2, 4.8
        """
        try:
            # Gunakan OCR service yang di-inject (module atau objek)
            if hasattr(self._ocr, "extract_text"):
                ocr_result = self._ocr.extract_text(screenshot_path)
            else:
                # Fallback: panggil langsung sebagai callable/module function
                from app.services import ocr_service
                ocr_result = ocr_service.extract_text(screenshot_path)

            text = ocr_result.text if hasattr(ocr_result, "text") else str(ocr_result)

            await self._log(
                db=db, task_id=task_id,
                action="read_ocr",
                status="success",
                message=f"OCR berhasil: {len(text)} karakter diekstrak",
                screenshot_path=screenshot_path,
                module="C",
            )
            return text

        except OCRInsufficientTextError as exc:
            # Requirements 4.8: teks < 10 karakter → skip
            logger.debug(
                "EngageBot: skip — teks OCR terlalu pendek (task=%s): %s", task_id, exc
            )
            stats["skipped_short_text"] += 1
            await self._log(
                db=db, task_id=task_id,
                action="read_ocr",
                status="skipped",
                message=f"Post dilewati: teks OCR terlalu pendek — {exc}",
                screenshot_path=screenshot_path,
                module="C",
            )
            return None

        except Exception as exc:
            logger.warning(
                "EngageBot: OCR gagal untuk screenshot %s (task=%s): %s",
                screenshot_path, task_id, exc,
            )
            stats["errors"] += 1
            await self._log(
                db=db, task_id=task_id,
                action="read_ocr",
                status="failed",
                message=f"OCR gagal: {exc}",
                error_detail=str(exc),
                screenshot_path=screenshot_path,
                module="C",
            )
            return None

    async def _generate_comment(
        self,
        task_id: str,
        db: AsyncSession,
        post_text: str,
        screenshot_path: str,
    ) -> Optional[str]:
        """
        Generate komentar LinkedIn via AI service.

        Returns:
            String komentar (20–200 karakter), atau None jika AI gagal.

        Requirements: 4.3, 4.4
        """
        await self._emit_progress(
            task_id=task_id,
            step="generate_comment",
            message="Menghasilkan komentar via AI...",
        )

        prompt = (
            f"Berikan satu komentar yang relevan dan natural untuk post LinkedIn berikut:\n\n"
            f"{post_text[:500]}\n\n"
            f"Komentar harus antara {_COMMENT_MIN_LEN}–{_COMMENT_MAX_LEN} karakter."
        )

        ai_request = AIRequest(
            prompt=prompt,
            system_prompt=_COMMENT_SYSTEM_PROMPT,
            max_tokens=100,
            temperature=0.8,
            module="C",
            task_id=task_id,
        )

        try:
            ai_response = await self._ai.generate(ai_request)
            if not ai_response.success:
                raise RuntimeError(ai_response.error or "AI generate gagal")

            comment = ai_response.content.strip()

            # Pastikan panjang komentar dalam range 20–200 karakter — Requirements 4.4
            if len(comment) < _COMMENT_MIN_LEN:
                logger.warning(
                    "EngageBot: komentar AI terlalu pendek (%d karakter), skip (task=%s)",
                    len(comment), task_id,
                )
                await self._log(
                    db=db, task_id=task_id,
                    action="generate_comment",
                    status="skipped",
                    message=f"Komentar AI terlalu pendek ({len(comment)} karakter, min {_COMMENT_MIN_LEN})",
                    screenshot_path=screenshot_path,
                    module="C",
                )
                return None

            # Potong jika melebihi batas maksimum
            if len(comment) > _COMMENT_MAX_LEN:
                comment = comment[:_COMMENT_MAX_LEN].rsplit(" ", 1)[0]
                logger.debug(
                    "EngageBot: komentar dipotong ke %d karakter (task=%s)",
                    len(comment), task_id,
                )

            await self._log(
                db=db, task_id=task_id,
                action="generate_comment",
                status="success",
                message=f"Komentar dihasilkan ({len(comment)} karakter, provider={ai_response.provider})",
                screenshot_path=screenshot_path,
                module="C",
            )
            return comment

        except Exception as exc:
            logger.error(
                "EngageBot: gagal generate komentar (task=%s): %s", task_id, exc
            )
            await self._log(
                db=db, task_id=task_id,
                action="generate_comment",
                status="failed",
                message=f"Gagal generate komentar: {exc}",
                error_detail=str(exc),
                screenshot_path=screenshot_path,
                module="C",
            )
            return None

    async def _post_comment(
        self,
        task_id: str,
        db: AsyncSession,
        comment_text: str,
        post_url: str,
        post_text: str,
        screenshot_path: str,
    ) -> None:
        """
        Ketik dan kirim komentar via ADB, lalu simpan ke tabel Interaction.

        Requirements: 4.5, 4.6
        """
        await self._emit_progress(
            task_id=task_id,
            step="post_comment",
            message=f"Mengirim komentar ({len(comment_text)} karakter)...",
        )

        # Dapatkan resolusi layar untuk konversi koordinat
        try:
            width, height = await self._adb.get_screen_resolution()
        except Exception:
            width, height = 1080, 1920

        # Tap tombol komentar
        comment_btn_x = int(_COMMENT_BTN[0] * width)
        comment_btn_y = int(_COMMENT_BTN[1] * height)
        await self._adb.execute_tap(comment_btn_x, comment_btn_y)
        await asyncio.sleep(anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX))

        # Tap area input komentar
        input_x = int(_COMMENT_INPUT[0] * width)
        input_y = int(_COMMENT_INPUT[1] * height)
        await self._adb.execute_tap(input_x, input_y)
        await asyncio.sleep(anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX))

        # Input teks komentar
        await self._adb.execute_input_text(comment_text)
        await asyncio.sleep(anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX))

        # Ambil screenshot setelah mengetik (Requirements 1.6)
        try:
            post_screenshot = await self._adb.take_screenshot()
        except Exception:
            post_screenshot = screenshot_path

        # Tap tombol kirim
        send_x = int(_COMMENT_SEND_BTN[0] * width)
        send_y = int(_COMMENT_SEND_BTN[1] * height)
        await self._adb.execute_tap(send_x, send_y)
        await asyncio.sleep(anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX))

        await self._log(
            db=db, task_id=task_id,
            action="post_comment",
            status="success",
            message=f"Komentar berhasil dikirim: {comment_text[:80]}...",
            screenshot_path=post_screenshot,
            module="C",
        )

        # ── Simpan ke tabel Interaction — Requirements 4.6 ────────────────────
        interaction = Interaction(
            target_post_url=post_url,
            target_post_text=post_text[:500] if post_text else None,
            action_type="comment",
            content_sent=comment_text,
            status="success",
            screenshot_path=post_screenshot,
        )
        db.add(interaction)
        await db.flush()

        await self._emit_progress(
            task_id=task_id,
            step="post_comment",
            message="Komentar berhasil dikirim dan dicatat",
            status="success",
        )
        logger.info(
            "EngageBot: komentar berhasil dikirim (task=%s, interaction_id=%s)",
            task_id, interaction.id,
        )

    # ------------------------------------------------------------------
    # Private — Helper utilities
    # ------------------------------------------------------------------

    def _matches_topic(self, text: str, keywords: List[str]) -> bool:
        """
        Cek apakah teks mengandung setidaknya satu keyword topik.

        Requirements: 4.10
        """
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def _extract_post_url(self, ocr_text: str, screenshot_path: str) -> str:
        """
        Ekstrak atau buat identifier URL unik untuk post yang sedang dilihat.

        Dalam implementasi nyata, URL LinkedIn dapat diekstrak dari UI via
        deep-link atau ADB content query. Di sini kita gunakan screenshot_path
        sebagai fallback identifier unik per iterasi.

        Pola URL LinkedIn yang mungkin muncul di OCR teks:
        'linkedin.com/feed/update/urn:li:activity:...'
        """
        import re
        url_match = re.search(
            r"linkedin\.com/(?:feed/update|posts)/[\w:%-]+",
            ocr_text,
        )
        if url_match:
            return f"https://www.{url_match.group(0)}"
        # Fallback: gunakan screenshot path sebagai pseudo-URL unik
        return f"screenshot://{screenshot_path}"

    async def _is_duplicate_url(self, post_url: str, db: AsyncSession) -> bool:
        """
        Cek apakah URL post sudah ada di tabel interactions dalam 7 hari terakhir.

        Requirements: 4.9
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_INTERACTION_DEDUP_DAYS)
        result = await db.execute(
            select(Interaction.id).where(
                Interaction.target_post_url == post_url,
                Interaction.created_at >= cutoff,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    # ------------------------------------------------------------------
    # Private — Logging & WebSocket helpers
    # ------------------------------------------------------------------

    async def _log(
        self,
        db: AsyncSession,
        task_id: str,
        action: str,
        status: str,
        message: str,
        error_detail: Optional[str] = None,
        stack_trace: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        module: Optional[str] = None,
    ) -> BotLog:
        """Catat satu langkah ke tabel bot_logs via log_service."""
        return await self._log_svc.create_log(
            db,
            action=action,
            status=status,
            task_id=task_id,
            message=message,
            error_detail=error_detail,
            stack_trace=stack_trace,
            screenshot_path=screenshot_path,
            module=module,
        )

    async def _emit_progress(
        self,
        task_id: str,
        step: str,
        message: str,
        status: str = "running",
    ) -> None:
        """
        Emit WebSocket progress event jika websocket_manager tersedia.

        Requirements: 2.10 (WebSocket real-time progress)
        """
        if self._ws is None:
            return

        payload: Dict[str, Any] = {
            "type": "bot_progress",
            "task_id": task_id,
            "step": step,
            "status": status,
            "message": message,
            "module": "C",
        }

        try:
            if hasattr(self._ws, "broadcast"):
                await self._ws.broadcast("bot_progress", payload)
        except Exception as exc:
            logger.warning("EngageBot: gagal emit WebSocket progress: %s", exc)


# ---------------------------------------------------------------------------
# Internal sentinel exceptions (untuk flow control dalam loop)
# ---------------------------------------------------------------------------


class _DailyLimitReached(Exception):
    """Sinyal internal: batas harian komentar sudah tercapai."""


class _CaptchaDetected(Exception):
    """Sinyal internal: CAPTCHA atau security challenge terdeteksi."""
