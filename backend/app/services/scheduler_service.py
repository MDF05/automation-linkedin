"""
Scheduler Service — Penjadwalan tugas otomatis menggunakan APScheduler.

Komponen ini:
- add_schedule(schedule) — tambah jadwal ke APScheduler (Requirements 6.1)
- remove_schedule(schedule_id) — hapus jadwal dari APScheduler (Requirements 6.1)
- toggle_schedule(schedule_id) — aktifkan/nonaktifkan jadwal (Requirements 6.6)
- reactivate_schedule(schedule_id) — hitung ulang next_run dari sekarang (Requirements 6.7)
- Update last_run dan next_run setelah setiap eksekusi (Requirements 6.2, 6.3)
- Retry logic: max 3x dengan interval 5 menit jika HP tidak terhubung (Requirements 6.4)

Requirements: 6.1–6.7
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Retry config — Requirements 6.4
_RETRY_INTERVAL_MINUTES = 5
_MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Helpers — cron next_run calculation
# ---------------------------------------------------------------------------


def compute_next_run(cron_expression: str, from_dt: Optional[datetime] = None) -> Optional[datetime]:
    """
    Hitung waktu eksekusi berikutnya berdasarkan cron expression.

    Menggunakan croniter jika tersedia, fallback ke None jika tidak.

    Args:
        cron_expression: String cron seperti "0 9 * * 1-5" (setiap hari kerja jam 09:00).
        from_dt:         Waktu referensi. Default ke utcnow() jika None.

    Returns:
        datetime timezone-aware UTC dari eksekusi berikutnya, atau None jika error.

    Requirements: 6.2, 6.3, 6.7
    """
    base_dt = from_dt or datetime.now(tz=timezone.utc)

    try:
        from croniter import croniter  # type: ignore[import]
        # croniter membutuhkan naive datetime sebagai start
        naive_base = base_dt.replace(tzinfo=None)
        cron = croniter(cron_expression, naive_base)
        next_dt_naive = cron.get_next(datetime)
        return next_dt_naive.replace(tzinfo=timezone.utc)
    except Exception as exc:
        logger.warning("compute_next_run: gagal hitung next_run untuk '%s': %s", cron_expression, exc)
        return None


# ---------------------------------------------------------------------------
# SchedulerService
# ---------------------------------------------------------------------------


class SchedulerService:
    """
    Layanan penjadwalan tugas menggunakan APScheduler AsyncIOScheduler.

    Mendukung:
    - Jadwal cron berulang (cron_expression)
    - Jadwal satu kali (scheduled_once_at)
    - Toggle aktif/nonaktif
    - Retry otomatis hingga max_retries jika HP tidak terhubung

    Requirements: 6.1–6.7
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        task_executor: Optional[Callable] = None,
    ) -> None:
        """
        Inisialisasi SchedulerService.

        Args:
            session_factory: Factory untuk membuat AsyncSession baru per eksekusi.
            task_executor:   Callable(task_type, config) → Any. Dipanggil saat jadwal terpicu.
                             Jika None, hanya update last_run/next_run tanpa eksekusi task.
        """
        self._session_factory = session_factory
        self._task_executor = task_executor
        self._scheduler: Optional[Any] = None
        self._job_map: Dict[int, str] = {}  # schedule.id → APScheduler job_id

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Mulai APScheduler AsyncIOScheduler."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import]
            self._scheduler = AsyncIOScheduler(timezone="UTC")
            self._scheduler.start()
            logger.info("SchedulerService: APScheduler dimulai.")
        except ImportError:
            logger.warning("SchedulerService: APScheduler tidak tersedia — scheduler dinonaktifkan.")
            self._scheduler = None

    def shutdown(self) -> None:
        """Hentikan APScheduler."""
        if self._scheduler is not None:
            try:
                self._scheduler.shutdown(wait=False)
                logger.info("SchedulerService: APScheduler dihentikan.")
            except Exception as exc:
                logger.warning("SchedulerService: error saat shutdown: %s", exc)

    # ------------------------------------------------------------------
    # Public API — Schedule CRUD
    # ------------------------------------------------------------------

    async def add_schedule(self, schedule_id: int, db: AsyncSession) -> bool:
        """
        Muat jadwal dari DB dan daftarkan ke APScheduler.

        Args:
            schedule_id: ID jadwal di tabel schedules.
            db:          AsyncSession untuk query.

        Returns:
            True jika berhasil didaftarkan, False jika jadwal tidak aktif atau error.

        Requirements: 6.1
        """
        from app.models.schedule import Schedule

        result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()

        if schedule is None:
            logger.warning("add_schedule: jadwal id=%d tidak ditemukan", schedule_id)
            return False

        if not schedule.is_active:
            logger.info("add_schedule: jadwal id=%d tidak aktif, skip", schedule_id)
            return False

        return self._register_apscheduler_job(schedule)

    def _register_apscheduler_job(self, schedule: Any) -> bool:
        """
        Daftarkan jadwal ke APScheduler.

        Returns True jika berhasil, False jika APScheduler tidak tersedia.
        """
        if self._scheduler is None:
            # Tanpa APScheduler, simpan di map untuk simulasi
            self._job_map[schedule.id] = f"mock_job_{schedule.id}"
            return True

        try:
            from apscheduler.triggers.cron import CronTrigger  # type: ignore[import]
            from apscheduler.triggers.date import DateTrigger  # type: ignore[import]

            job_id = f"schedule_{schedule.id}"

            # Hapus job lama jika ada
            if self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)

            # Pilih trigger berdasarkan jenis jadwal
            if schedule.cron_expression:
                trigger = CronTrigger.from_crontab(schedule.cron_expression, timezone="UTC")
            elif schedule.scheduled_once_at:
                trigger = DateTrigger(run_date=schedule.scheduled_once_at, timezone="UTC")
            else:
                logger.warning(
                    "_register_apscheduler_job: jadwal id=%d tidak memiliki trigger", schedule.id
                )
                return False

            self._scheduler.add_job(
                func=self._execute_schedule_job,
                trigger=trigger,
                id=job_id,
                kwargs={"schedule_id": schedule.id},
                replace_existing=True,
                misfire_grace_time=60,
            )
            self._job_map[schedule.id] = job_id
            logger.info(
                "SchedulerService: jadwal id=%d '%s' terdaftar (trigger=%s)",
                schedule.id, schedule.name,
                schedule.cron_expression or schedule.scheduled_once_at,
            )
            return True

        except Exception as exc:
            logger.error("_register_apscheduler_job: error id=%d: %s", schedule.id, exc)
            return False

    async def remove_schedule(self, schedule_id: int) -> bool:
        """
        Hapus jadwal dari APScheduler.

        Requirements: 6.1
        """
        job_id = self._job_map.pop(schedule_id, None)
        if job_id is None:
            return False

        if self._scheduler is not None:
            try:
                if self._scheduler.get_job(job_id):
                    self._scheduler.remove_job(job_id)
            except Exception as exc:
                logger.warning("remove_schedule: error id=%d: %s", schedule_id, exc)
                return False

        logger.info("SchedulerService: jadwal id=%d dihapus dari scheduler", schedule_id)
        return True

    async def toggle_schedule(
        self, schedule_id: int, db: AsyncSession
    ) -> Optional[Any]:
        """
        Toggle aktif/nonaktif jadwal.

        Jika jadwal diaktifkan kembali setelah nonaktif, hitung ulang next_run
        dari waktu sekarang (bukan dari last_run) — Requirements 6.7.

        Args:
            schedule_id: ID jadwal.
            db:          AsyncSession.

        Returns:
            Objek Schedule yang sudah diperbarui, atau None jika tidak ditemukan.

        Requirements: 6.6, 6.7
        """
        from app.models.schedule import Schedule

        result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()

        if schedule is None:
            logger.warning("toggle_schedule: jadwal id=%d tidak ditemukan", schedule_id)
            return None

        was_active = schedule.is_active
        schedule.is_active = not was_active

        if schedule.is_active:
            # Diaktifkan kembali — hitung next_run dari sekarang (Requirements 6.7)
            if schedule.cron_expression:
                schedule.next_run = compute_next_run(
                    schedule.cron_expression,
                    from_dt=datetime.now(tz=timezone.utc),
                )
            schedule.retry_count = 0  # reset retry counter
            # Daftarkan ke APScheduler
            self._register_apscheduler_job(schedule)
            logger.info(
                "SchedulerService: jadwal id=%d diaktifkan, next_run=%s",
                schedule_id, schedule.next_run,
            )
        else:
            # Dinonaktifkan — hapus dari APScheduler (Requirements 6.6)
            await self.remove_schedule(schedule_id)
            logger.info("SchedulerService: jadwal id=%d dinonaktifkan", schedule_id)

        await db.flush()
        return schedule

    async def reactivate_schedule(
        self, schedule_id: int, db: AsyncSession
    ) -> Optional[Any]:
        """
        Aktifkan kembali jadwal dan hitung ulang next_run dari waktu sekarang.

        Requirements: 6.7
        """
        from app.models.schedule import Schedule

        result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()

        if schedule is None:
            return None

        schedule.is_active = True
        schedule.retry_count = 0

        # Hitung next_run dari sekarang — Requirements 6.7
        if schedule.cron_expression:
            schedule.next_run = compute_next_run(
                schedule.cron_expression,
                from_dt=datetime.now(tz=timezone.utc),
            )

        self._register_apscheduler_job(schedule)
        await db.flush()

        logger.info(
            "SchedulerService: jadwal id=%d diaktifkan ulang, next_run=%s",
            schedule_id, schedule.next_run,
        )
        return schedule

    # ------------------------------------------------------------------
    # Private — Job execution
    # ------------------------------------------------------------------

    async def _execute_schedule_job(self, schedule_id: int) -> None:
        """
        Callback yang dipanggil APScheduler saat waktu eksekusi tiba.

        - Update last_run dan next_run
        - Jalankan task_executor jika tersedia
        - Retry hingga max_retries jika HP tidak terhubung (Requirements 6.4)

        Requirements: 6.2, 6.3, 6.4
        """
        from app.models.bot_log import BotLog
        from app.models.schedule import Schedule

        async with self._session_factory() as db:
            async with db.begin():
                result = await db.execute(
                    select(Schedule).where(Schedule.id == schedule_id)
                )
                schedule = result.scalar_one_or_none()

                if schedule is None or not schedule.is_active:
                    return

                logger.info(
                    "SchedulerService: menjalankan jadwal id=%d '%s'",
                    schedule_id, schedule.name,
                )

                # Update last_run sebelum eksekusi — Requirements 6.2
                now = datetime.now(tz=timezone.utc)
                schedule.last_run = now

                # Hitung next_run — Requirements 6.3
                if schedule.cron_expression:
                    schedule.next_run = compute_next_run(schedule.cron_expression, from_dt=now)

                success = await self._run_with_retry(schedule, db)

                if success:
                    schedule.last_status = "success"
                    schedule.run_count = (schedule.run_count or 0) + 1
                    schedule.retry_count = 0
                else:
                    schedule.last_status = "failed"
                    schedule.failure_count = (schedule.failure_count or 0) + 1

    async def _run_with_retry(self, schedule: Any, db: AsyncSession) -> bool:
        """
        Eksekusi task dengan retry logic hingga max_retries.

        Requirements: 6.4
        """
        max_retries = schedule.max_retries or _MAX_RETRIES
        retry_interval_s = _RETRY_INTERVAL_MINUTES * 60

        for attempt in range(max_retries):
            try:
                if self._task_executor is not None:
                    await self._task_executor(
                        task_type=schedule.task_type,
                        config=schedule.config_json or {},
                        schedule_id=schedule.id,
                        db=db,
                    )
                return True

            except Exception as exc:
                err_msg = str(exc)
                is_device_error = any(kw in err_msg.lower() for kw in [
                    "adb", "timeout", "device", "connection", "disconnected"
                ])

                logger.warning(
                    "SchedulerService: jadwal id=%d attempt %d/%d gagal: %s",
                    schedule.id, attempt + 1, max_retries, exc,
                )

                schedule.retry_count = (schedule.retry_count or 0) + 1

                if attempt < max_retries - 1:
                    # Tunggu sebelum retry — Requirements 6.4
                    logger.info(
                        "SchedulerService: retry jadwal id=%d dalam %d menit...",
                        schedule.id, _RETRY_INTERVAL_MINUTES,
                    )
                    await asyncio.sleep(retry_interval_s)
                else:
                    # Semua retry habis
                    logger.error(
                        "SchedulerService: jadwal id=%d gagal setelah %d percobaan",
                        schedule.id, max_retries,
                    )

        return False
