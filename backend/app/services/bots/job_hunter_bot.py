"""
Job Hunter Bot — Module D: Cari dan Lamar Lowongan Kerja di LinkedIn.

Komponen ini:
- Membuka LinkedIn Jobs via ADB dan memasukkan kriteria pencarian (Requirements 5.1, 5.2)
- Mengekstrak daftar lowongan via OCR (Requirements 5.3)
- Menyimpan lowongan ke tabel job_applications, skip duplikat by job_url (Requirements 5.4)
- Melamar via Easy Apply, isi form, upload CV (Requirements 5.5)
- Skip jika form membutuhkan field yang tidak ada di config CV (Requirements 5.8)
- Update status='applied' dengan applied_at dan screenshot (Requirements 5.6)
- Cek batas harian apply via anti_ban (Requirements 5.7)
- Catat semua langkah ke BotLog via log_service (Requirements 7.1)
- Emit WebSocket progress event per langkah (Requirements 2.10)

Requirements: 5.1–5.9
"""

from __future__ import annotations

import asyncio
import logging
import re
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot_log import BotLog
from app.models.job_application import JobApplication
from app.services import anti_ban
from app.services import log_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LinkedIn Jobs UI coordinates (relative 0.0–1.0)
# ---------------------------------------------------------------------------

_JOBS_TAB_BTN       = (0.6, 0.95)    # Jobs tab di bottom navigation
_JOBS_SEARCH_BAR    = (0.5, 0.12)    # Search bar di halaman Jobs
_JOBS_FILTER_BTN    = (0.9, 0.12)    # Tombol filter di sebelah search bar
_EASY_APPLY_BTN     = (0.5, 0.55)    # Tombol Easy Apply di halaman detail lowongan
_FORM_NEXT_BTN      = (0.85, 0.92)   # Tombol Next/Continue di form Easy Apply
_FORM_SUBMIT_BTN    = (0.85, 0.92)   # Tombol Submit/Apply di form
_SCROLL_UP_AREA     = (0.5, 0.3)
_SCROLL_DOWN_AREA   = (0.5, 0.7)

# Timing
_NAV_DELAY_MIN = 2.0
_NAV_DELAY_MAX = 5.0
_TAP_DELAY_MIN = 1.0
_TAP_DELAY_MAX = 3.0
_MAX_SCROLL_PAGES = 5   # Maks halaman scroll untuk ekstrak lowongan

# CV fields yang dibutuhkan Easy Apply — dibandingkan dengan config
_REQUIRED_CV_FIELDS = ["name", "email", "phone", "resume_path"]

# Kata kunci yang mengindikasikan field form yang tidak dapat diisi otomatis
_UNSUPPORTED_FORM_KEYWORDS = [
    "cover letter", "surat lamaran",
    "portfolio url", "github", "linkedin url",
    "salary expectation", "gaji yang diharapkan",
    "years of experience", "pengalaman",
    "work authorization", "visa",
]


# ---------------------------------------------------------------------------
# JobHunterBot
# ---------------------------------------------------------------------------


class JobHunterBot:
    """
    Bot untuk mencari dan melamar lowongan kerja di LinkedIn secara otomatis.

    Urutan eksekusi:
    1. Buka LinkedIn Jobs via ADB
    2. Input kriteria pencarian + terapkan filter
    3. Scroll halaman hasil, ekstrak lowongan via OCR
    4. Simpan setiap lowongan ke JobApplication (status='found'), skip duplikat
    5. Untuk tiap lowongan dengan Easy Apply:
       a. Cek batas harian apply
       b. Buka halaman lowongan
       c. Deteksi tombol Easy Apply via OCR
       d. Isi form dengan data CV dari config
       e. Submit lamaran
       f. Update status='applied' + catat screenshot
    6. Return ringkasan sesi

    Requirements: 5.1–5.9
    """

    def __init__(
        self,
        adb_service: Any,
        ocr_service: Any,
        log_service_module: Any = None,
        websocket_manager: Optional[Any] = None,
        cv_fields: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Inisialisasi JobHunterBot.

        Args:
            adb_service:        Instance ADBService untuk kontrol HP Android.
            ocr_service:        Module/objek OCR dengan .extract_text(path).
            log_service_module: Module log_service (opsional).
            websocket_manager:  Instance WebSocket ConnectionManager (opsional).
            cv_fields:          Dict data CV: {'name', 'email', 'phone', 'resume_path', ...}.
                                Digunakan untuk mengisi form Easy Apply.
        """
        self._adb = adb_service
        self._ocr = ocr_service
        self._log_svc = log_service_module or log_service
        self._ws = websocket_manager
        self._cv = cv_fields or {}
        self._stop_requested = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Minta loop untuk berhenti gracefully di iterasi berikutnya."""
        self._stop_requested = True
        logger.info("JobHunterBot: stop() dipanggil.")

    async def search_jobs(
        self,
        criteria: Dict[str, Any],
        db: AsyncSession,
        session_id: Optional[str] = None,
    ) -> List[JobApplication]:
        """
        Cari lowongan di LinkedIn Jobs sesuai kriteria, simpan ke database.

        Args:
            criteria:   Dict kriteria dari JobCriteria schema:
                        {'titles': [...], 'skills': [...], 'location': '...', 'job_type': '...'}
            db:         AsyncSession SQLAlchemy.
            session_id: UUID sesi untuk grouping hasil. Auto-generated jika None.

        Returns:
            List JobApplication yang berhasil disimpan (status='found').

        Requirements: 5.1–5.4
        """
        task_id = str(uuid.uuid4())
        session_id = session_id or str(uuid.uuid4())
        found_jobs: List[JobApplication] = []

        titles: List[str] = criteria.get("titles", [])
        location: Optional[str] = criteria.get("location")

        logger.info(
            "JobHunterBot: memulai pencarian (task=%s, titles=%s, location=%s)",
            task_id, titles, location,
        )

        try:
            # Step 1: Buka LinkedIn Jobs
            await self._open_linkedin_jobs(task_id=task_id, db=db)

            # Step 2: Untuk setiap judul posisi yang dicari
            for title in titles:
                if self._stop_requested:
                    break

                await self._search_by_keyword(
                    task_id=task_id,
                    db=db,
                    keyword=title,
                    location=location,
                    job_type=criteria.get("job_type"),
                )

                # Step 3: Scroll dan ekstrak lowongan
                new_jobs = await self._extract_and_save_jobs(
                    task_id=task_id,
                    db=db,
                    session_id=session_id,
                )
                found_jobs.extend(new_jobs)

        except Exception as exc:
            logger.error(
                "JobHunterBot: error saat pencarian (task=%s): %s",
                task_id, exc, exc_info=True,
            )
            await self._log(
                db=db, task_id=task_id,
                action="search_jobs",
                status="failed",
                message=f"Error pencarian: {exc}",
                error_detail=str(exc),
                stack_trace=traceback.format_exc(),
                module="D",
            )

        logger.info(
            "JobHunterBot: pencarian selesai (task=%s) — %d lowongan ditemukan",
            task_id, len(found_jobs),
        )
        return found_jobs

    async def apply_job(
        self,
        job_application_id: int,
        db: AsyncSession,
    ) -> JobApplication:
        """
        Lamar satu lowongan via Easy Apply.

        Args:
            job_application_id: ID entri JobApplication di database.
            db:                 AsyncSession SQLAlchemy.

        Returns:
            Objek JobApplication yang sudah diperbarui (status='applied' atau 'skipped_*').

        Requirements: 5.5–5.8
        """
        task_id = str(uuid.uuid4())

        # Load job application
        result = await db.execute(
            select(JobApplication).where(JobApplication.id == job_application_id)
        )
        job: Optional[JobApplication] = result.scalar_one_or_none()

        if job is None:
            raise ValueError(f"JobApplication id={job_application_id} tidak ditemukan")

        if job.status == "applied":
            logger.info(
                "JobHunterBot: lowongan id=%d sudah dilamar, skip.",
                job_application_id,
            )
            return job

        logger.info(
            "JobHunterBot: melamar %s @ %s (task=%s)",
            job.job_title, job.company, task_id,
        )

        try:
            # Cek batas harian — Requirements 5.7
            can_apply = await anti_ban.check_daily_limit_from_db("apply", db)
            if not can_apply:
                logger.warning("JobHunterBot: batas harian apply tercapai, skip id=%d", job_application_id)
                job.status = "skipped"
                job.notes = "Batas harian apply tercapai"
                await db.flush()
                await self._log(
                    db=db, task_id=task_id,
                    action="easy_apply",
                    status="skipped",
                    message="Batas harian apply tercapai",
                    module="D",
                )
                return job

            # Buka halaman lowongan
            await self._open_job_page(task_id=task_id, db=db, job=job)

            # Screenshot dan cek Easy Apply via OCR
            screenshot_path = await self._take_screenshot(task_id=task_id, db=db)
            ocr_text = await self._extract_text(screenshot_path)

            if not self._has_easy_apply(ocr_text):
                job.status = "skipped_no_easy_apply"
                job.notes = "Tombol Easy Apply tidak ditemukan"
                job.screenshot_path = screenshot_path
                await db.flush()
                await self._log(
                    db=db, task_id=task_id,
                    action="easy_apply",
                    status="skipped",
                    message="Tombol Easy Apply tidak ditemukan via OCR",
                    module="D",
                )
                return job

            # Tap Easy Apply
            await self._tap_easy_apply(task_id=task_id, db=db)

            # Screenshot form dan cek apakah dapat diisi otomatis
            form_screenshot = await self._take_screenshot(task_id=task_id, db=db)
            form_text = await self._extract_text(form_screenshot)

            if self._has_unsupported_fields(form_text):
                # Tutup form (back)
                await self._adb.press_back()
                job.status = "skipped_incomplete_form"
                job.notes = "Form Easy Apply memerlukan input yang tidak tersedia di config CV"
                job.screenshot_path = form_screenshot
                await db.flush()
                await self._log(
                    db=db, task_id=task_id,
                    action="fill_form",
                    status="skipped",
                    message="Skipped: form butuh input yang tidak ada di CV config",
                    module="D",
                )
                logger.info(
                    "JobHunterBot: skip id=%d — form incomplete (task=%s)",
                    job_application_id, task_id,
                )
                return job

            # Isi dan submit form
            fields_filled = await self._fill_and_submit_form(
                task_id=task_id, db=db, job=job,
            )

            # Update status applied — Requirements 5.6
            confirm_screenshot = await self._take_screenshot(task_id=task_id, db=db)
            job.status = "applied"
            job.applied_at = datetime.now(tz=timezone.utc)
            job.screenshot_path = confirm_screenshot
            job.form_fields_filled = fields_filled
            await db.flush()

            await self._log(
                db=db, task_id=task_id,
                action="easy_apply",
                status="success",
                message=f"Berhasil melamar: {job.job_title} @ {job.company}",
                screenshot_path=confirm_screenshot,
                module="D",
            )
            await self._emit_progress(
                task_id=task_id,
                step="easy_apply",
                message=f"Lamaran berhasil: {job.job_title} @ {job.company}",
                status="success",
            )
            logger.info(
                "JobHunterBot: berhasil apply id=%d (task=%s)",
                job_application_id, task_id,
            )
            return job

        except Exception as exc:
            logger.error(
                "JobHunterBot: error apply id=%d (task=%s): %s",
                job_application_id, task_id, exc, exc_info=True,
            )
            try:
                job.status = "skipped"
                job.notes = f"Error: {exc}"
                await db.flush()
            except Exception:
                pass
            await self._log(
                db=db, task_id=task_id,
                action="easy_apply",
                status="failed",
                message=f"Error melamar: {exc}",
                error_detail=str(exc),
                stack_trace=traceback.format_exc(),
                module="D",
            )
            raise

    # ------------------------------------------------------------------
    # Private — Navigation & Search
    # ------------------------------------------------------------------

    async def _open_linkedin_jobs(self, task_id: str, db: AsyncSession) -> None:
        """Buka aplikasi LinkedIn dan navigasi ke tab Jobs."""
        await self._emit_progress(task_id=task_id, step="open_jobs", message="Membuka LinkedIn Jobs...")
        await self._adb.open_app("com.linkedin.android")
        await asyncio.sleep(anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX))

        # Tap Jobs tab
        width, height = await self._adb.get_screen_resolution()
        x = int(_JOBS_TAB_BTN[0] * width)
        y = int(_JOBS_TAB_BTN[1] * height)
        await self._adb.execute_tap(x, y)
        await asyncio.sleep(anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX))

        await self._log(
            db=db, task_id=task_id,
            action="open_jobs",
            status="success",
            message="LinkedIn Jobs berhasil dibuka",
            module="D",
        )

    async def _search_by_keyword(
        self,
        task_id: str,
        db: AsyncSession,
        keyword: str,
        location: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> None:
        """Input kata kunci pencarian ke search bar Jobs."""
        await self._emit_progress(
            task_id=task_id, step="search_jobs",
            message=f"Mencari: {keyword} di {location or 'semua lokasi'}",
        )

        width, height = await self._adb.get_screen_resolution()

        # Tap search bar
        x = int(_JOBS_SEARCH_BAR[0] * width)
        y = int(_JOBS_SEARCH_BAR[1] * height)
        await self._adb.execute_tap(x, y)
        await asyncio.sleep(anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX))

        # Input keyword
        await self._adb.execute_input_text(keyword)
        await asyncio.sleep(anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX))

        # Tekan Enter (KEYCODE_ENTER = 66)
        await self._adb.press_key(66) if hasattr(self._adb, "press_key") else None
        await asyncio.sleep(anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX))

        await self._log(
            db=db, task_id=task_id,
            action="search_jobs",
            status="success",
            message=f"Pencarian dilakukan: keyword='{keyword}', location='{location}'",
            module="D",
        )

    async def _open_job_page(
        self,
        task_id: str,
        db: AsyncSession,
        job: JobApplication,
    ) -> None:
        """Buka halaman detail lowongan (tap item di list hasil pencarian)."""
        await self._emit_progress(
            task_id=task_id, step="open_jobs",
            message=f"Membuka lowongan: {job.job_title} @ {job.company}",
        )
        # Tap di tengah layar untuk membuka item pertama yang dipilih
        width, height = await self._adb.get_screen_resolution()
        await self._adb.execute_tap(int(0.5 * width), int(0.4 * height))
        await asyncio.sleep(anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX))

        await self._log(
            db=db, task_id=task_id,
            action="open_jobs",
            status="success",
            message=f"Halaman lowongan dibuka: {job.job_title}",
            module="D",
        )

    async def _tap_easy_apply(self, task_id: str, db: AsyncSession) -> None:
        """Tap tombol Easy Apply."""
        await self._emit_progress(task_id=task_id, step="easy_apply", message="Tap tombol Easy Apply...")
        width, height = await self._adb.get_screen_resolution()
        x = int(_EASY_APPLY_BTN[0] * width)
        y = int(_EASY_APPLY_BTN[1] * height)
        await self._adb.execute_tap(x, y)
        await asyncio.sleep(anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX))

        await self._log(
            db=db, task_id=task_id,
            action="easy_apply",
            status="running",
            message="Tombol Easy Apply di-tap",
            module="D",
        )

    # ------------------------------------------------------------------
    # Private — Job Extraction via OCR
    # ------------------------------------------------------------------

    async def _extract_and_save_jobs(
        self,
        task_id: str,
        db: AsyncSession,
        session_id: str,
    ) -> List[JobApplication]:
        """
        Scroll halaman hasil pencarian, ekstrak lowongan via OCR, simpan ke DB.

        Requirements: 5.3, 5.4
        """
        saved: List[JobApplication] = []

        for page in range(_MAX_SCROLL_PAGES):
            if self._stop_requested:
                break

            # Screenshot halaman saat ini
            screenshot_path = await self._take_screenshot(task_id=task_id, db=db)

            # Ekstrak teks halaman
            try:
                page_text = await self._extract_text(screenshot_path)
            except Exception as exc:
                logger.warning("JobHunterBot: OCR gagal halaman %d: %s", page, exc)
                await self._scroll_down()
                continue

            # Parse jobs dari teks OCR
            raw_jobs = self._parse_jobs_from_text(page_text, session_id)

            for job_data in raw_jobs:
                job_url = job_data.get("job_url", "")
                if not job_url:
                    continue

                # Cek duplikat by job_url — Requirements 5.4
                existing = await db.execute(
                    select(JobApplication).where(JobApplication.job_url == job_url)
                )
                if existing.scalar_one_or_none() is not None:
                    logger.debug("JobHunterBot: duplikat job_url skipped: %s", job_url)
                    continue

                # Simpan lowongan baru
                job = JobApplication(
                    job_title=job_data.get("job_title", "Unknown Position"),
                    company=job_data.get("company", "Unknown Company"),
                    location=job_data.get("location"),
                    job_url=job_url,
                    status="found",
                    has_easy_apply=job_data.get("has_easy_apply", False),
                    job_type=job_data.get("job_type"),
                    search_session_id=session_id,
                    screenshot_path=screenshot_path,
                )
                db.add(job)
                await db.flush()
                saved.append(job)

                await self._log(
                    db=db, task_id=task_id,
                    action="extract_jobs",
                    status="success",
                    message=f"Lowongan disimpan: {job.job_title} @ {job.company}",
                    screenshot_path=screenshot_path,
                    module="D",
                )

            # Scroll ke bawah untuk hasil berikutnya
            await self._scroll_down()
            await asyncio.sleep(anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX))

        logger.info(
            "JobHunterBot: %d lowongan baru diekstrak (task=%s, session=%s)",
            len(saved), task_id, session_id,
        )
        return saved

    def _parse_jobs_from_text(
        self, text: str, session_id: str
    ) -> List[Dict[str, Any]]:
        """
        Parse teks OCR dari halaman hasil pencarian Jobs menjadi list dict lowongan.

        Strategi: cari pola baris berulang yang mengandung judul + perusahaan.
        Karena OCR dari screenshot mobile dapat bervariasi, kita gunakan heuristik
        sederhana berbasis baris teks.

        Returns:
            List dict dengan key: job_title, company, location, job_url, has_easy_apply.
        """
        jobs: List[Dict[str, Any]] = []
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Heuristik: baris yang mengandung "Easy Apply" atau job-like keywords
            has_easy = "easy apply" in line.lower() or "lamar mudah" in line.lower()

            # Baris judul biasanya diikuti nama perusahaan pada baris berikutnya
            if len(line) > 5 and i + 1 < len(lines):
                title = line
                company = lines[i + 1] if i + 1 < len(lines) else "Unknown"
                location = lines[i + 2] if i + 2 < len(lines) else None

                # Buat URL pseudo berdasarkan title + company (proxy karena ADB tidak
                # mengakses URL asli secara langsung; di produksi gunakan deep-link)
                job_url = self._build_job_url_key(title, company, session_id)

                jobs.append({
                    "job_title": title,
                    "company": company,
                    "location": location,
                    "job_url": job_url,
                    "has_easy_apply": has_easy,
                })
                i += 3
            else:
                i += 1

        return jobs

    def _build_job_url_key(self, title: str, company: str, session_id: str) -> str:
        """
        Buat identifier unik pseudo-URL untuk menghindari duplikat.

        Format: linkedin://jobs/{sanitized_title}/{sanitized_company}/{session_id[:8]}
        """
        def sanitize(s: str) -> str:
            return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

        return f"linkedin://jobs/{sanitize(title)}/{sanitize(company)}/{session_id[:8]}"

    # ------------------------------------------------------------------
    # Private — Form Filling
    # ------------------------------------------------------------------

    async def _fill_and_submit_form(
        self,
        task_id: str,
        db: AsyncSession,
        job: JobApplication,
    ) -> Dict[str, str]:
        """
        Isi form Easy Apply dengan data dari CV config dan submit.

        Returns:
            Dict field yang berhasil diisi.

        Requirements: 5.5
        """
        await self._emit_progress(
            task_id=task_id, step="fill_form",
            message="Mengisi form Easy Apply...",
        )

        fields_filled: Dict[str, str] = {}
        width, height = await self._adb.get_screen_resolution()

        # Isi nama
        if self._cv.get("name"):
            await self._adb.execute_input_text(self._cv["name"])
            await asyncio.sleep(anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX))
            fields_filled["name"] = self._cv["name"]

        # Isi email
        if self._cv.get("email"):
            await self._adb.execute_input_text(self._cv["email"])
            await asyncio.sleep(anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX))
            fields_filled["email"] = self._cv["email"]

        # Isi nomor telepon
        if self._cv.get("phone"):
            await self._adb.execute_input_text(self._cv["phone"])
            await asyncio.sleep(anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX))
            fields_filled["phone"] = self._cv["phone"]

        await self._log(
            db=db, task_id=task_id,
            action="fill_form",
            status="success",
            message=f"Form diisi: {list(fields_filled.keys())}",
            module="D",
        )

        # Tap Next / Submit
        x = int(_FORM_SUBMIT_BTN[0] * width)
        y = int(_FORM_SUBMIT_BTN[1] * height)
        await self._adb.execute_tap(x, y)
        await asyncio.sleep(anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX))

        await self._log(
            db=db, task_id=task_id,
            action="easy_apply",
            status="running",
            message="Form Easy Apply disubmit",
            module="D",
        )

        return fields_filled

    # ------------------------------------------------------------------
    # Private — OCR helpers
    # ------------------------------------------------------------------

    def _has_easy_apply(self, text: str) -> bool:
        """Cek apakah layar menampilkan tombol Easy Apply."""
        text_lower = text.lower()
        return "easy apply" in text_lower or "lamar mudah" in text_lower

    def _has_unsupported_fields(self, form_text: str) -> bool:
        """
        Cek apakah form Easy Apply memerlukan field yang tidak dapat diisi otomatis.

        Requirements: 5.8
        """
        text_lower = form_text.lower()
        return any(kw in text_lower for kw in _UNSUPPORTED_FORM_KEYWORDS)

    async def _extract_text(self, screenshot_path: str) -> str:
        """Ekstrak teks dari screenshot via OCR service."""
        try:
            if hasattr(self._ocr, "extract_text"):
                result = self._ocr.extract_text(screenshot_path)
            else:
                from app.services import ocr_service
                result = ocr_service.extract_text(screenshot_path)
            return result.text if hasattr(result, "text") else str(result)
        except Exception as exc:
            logger.warning("JobHunterBot: OCR gagal: %s", exc)
            return ""

    async def _take_screenshot(self, task_id: str, db: AsyncSession) -> str:
        """Ambil screenshot layar dan log hasilnya."""
        path = await self._adb.take_screenshot()
        await self._log(
            db=db, task_id=task_id,
            action="screenshot",
            status="success",
            message=f"Screenshot: {path}",
            screenshot_path=path,
            module="D",
        )
        return path

    async def _scroll_down(self) -> None:
        """Scroll ke bawah untuk melihat lebih banyak hasil."""
        try:
            width, height = await self._adb.get_screen_resolution()
            x = int(0.5 * width)
            y_start = int(_SCROLL_DOWN_AREA[1] * height)
            y_end = int(_SCROLL_UP_AREA[1] * height)
            await self._adb.execute_swipe(x, y_start, x, y_end, 800)
        except Exception as exc:
            logger.warning("JobHunterBot: scroll gagal: %s", exc)

    # ------------------------------------------------------------------
    # Private — Logging & WebSocket
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
        module: str = "D",
    ) -> BotLog:
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
        """Emit WebSocket bot_progress event jika manager tersedia."""
        if self._ws is None:
            return
        payload: Dict[str, Any] = {
            "type": "bot_progress",
            "task_id": task_id,
            "step": step,
            "status": status,
            "message": message,
        }
        try:
            if hasattr(self._ws, "broadcast"):
                await self._ws.broadcast("bot_progress", payload)
        except Exception as exc:
            logger.warning("JobHunterBot: WebSocket emit gagal: %s", exc)
