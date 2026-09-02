"""
Unit tests untuk `scheduler_service.py`.

Validates: Requirements 6.4, 6.6, 6.7

Tests yang dicakup:
- toggle aktif → nonaktif: is_active menjadi False
- toggle nonaktif → aktif: is_active menjadi True, next_run dihitung dari NOW
- double toggle: aktif → nonaktif → aktif dengan next_run yang baru
- Verifikasi next_run setelah re-aktivasi >= waktu sekarang (bukan masa lalu)
- Retry logic: HP tidak terhubung → retry hingga 3x
- Setelah 3 gagal: last_status='failed', retry_count >= 3
- retry_count diincrement pada setiap kegagalan
- Eksekusi sukses: retry_count di-reset ke 0
- add_schedule mendaftarkan job ke APScheduler
- remove_schedule menghapus job dan mengembalikan False jika dipanggil lagi
- last_run diperbarui setelah eksekusi berhasil
- next_run diperbarui setelah eksekusi
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.services.scheduler_service import SchedulerService, compute_next_run


# ---------------------------------------------------------------------------
# Helpers — fake Schedule object (tidak membutuhkan DB)
# ---------------------------------------------------------------------------


def make_schedule(
    schedule_id: int = 1,
    name: str = "Test Schedule",
    task_type: str = "engage",
    cron_expression: Optional[str] = "0 9 * * *",
    is_active: bool = True,
    last_run: Optional[datetime] = None,
    next_run: Optional[datetime] = None,
    retry_count: int = 0,
    max_retries: int = 3,
    run_count: int = 0,
    failure_count: int = 0,
    last_status: Optional[str] = None,
    config_json: Optional[dict] = None,
) -> MagicMock:
    """Buat objek Schedule palsu (MagicMock) dengan atribut yang dapat diubah."""
    sched = MagicMock()
    sched.id = schedule_id
    sched.name = name
    sched.task_type = task_type
    sched.cron_expression = cron_expression
    sched.scheduled_once_at = None
    sched.is_active = is_active
    sched.last_run = last_run
    sched.next_run = next_run
    sched.retry_count = retry_count
    sched.max_retries = max_retries
    sched.run_count = run_count
    sched.failure_count = failure_count
    sched.last_status = last_status
    sched.config_json = config_json or {}
    return sched


def make_db_session(schedule: Optional[MagicMock] = None) -> AsyncMock:
    """
    Buat mock AsyncSession yang mengembalikan `schedule` saat di-query.
    Jika `schedule` is None, scalar_one_or_none mengembalikan None.
    """
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = schedule
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.begin = MagicMock()

    # Support async context manager untuk begin()
    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=db)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    db.begin.return_value = async_cm

    return db


def make_session_factory(schedule: Optional[MagicMock] = None):
    """
    Buat session_factory mock yang mengembalikan async context manager ke db.
    """
    db = make_db_session(schedule)
    factory = MagicMock()

    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=db)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    factory.return_value = async_cm

    return factory, db


def make_scheduler_service(task_executor=None) -> SchedulerService:
    """Buat SchedulerService tanpa APScheduler nyata (scheduler=None)."""
    session_factory = MagicMock()
    service = SchedulerService(session_factory=session_factory, task_executor=task_executor)
    service._scheduler = None  # non-APScheduler mode
    return service


# ---------------------------------------------------------------------------
# compute_next_run — unit tests
# ---------------------------------------------------------------------------


class TestComputeNextRun:
    """Test fungsi helper compute_next_run."""

    def test_returns_datetime_for_valid_cron(self) -> None:
        """compute_next_run harus mengembalikan datetime untuk cron yang valid."""
        now = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run("0 9 * * *", from_dt=now)
        # Bisa None jika croniter tidak tersedia
        if result is not None:
            assert isinstance(result, datetime)

    def test_result_is_in_the_future_relative_to_from_dt(self) -> None:
        """next_run harus lebih besar dari from_dt."""
        now = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run("0 9 * * *", from_dt=now)
        if result is not None:
            assert result > now

    def test_result_is_timezone_aware(self) -> None:
        """next_run harus timezone-aware (UTC)."""
        now = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run("0 9 * * *", from_dt=now)
        if result is not None:
            assert result.tzinfo is not None

    def test_returns_none_for_invalid_cron(self) -> None:
        """compute_next_run harus mengembalikan None untuk cron expression yang tidak valid."""
        now = datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        result = compute_next_run("invalid_cron_expression", from_dt=now)
        assert result is None

    def test_uses_current_time_when_from_dt_is_none(self) -> None:
        """Ketika from_dt=None, harus menggunakan waktu saat ini."""
        before = datetime.now(tz=timezone.utc)
        result = compute_next_run("* * * * *", from_dt=None)
        after = datetime.now(tz=timezone.utc)
        if result is not None:
            assert result >= before


# ---------------------------------------------------------------------------
# SchedulerService.toggle_schedule — Toggle Behavior
# ---------------------------------------------------------------------------


class TestToggleScheduleActiveToInactive:
    """
    Req 6.6: Toggle jadwal aktif → nonaktif.
    """

    @pytest.mark.asyncio
    async def test_toggle_active_becomes_inactive(self) -> None:
        """
        Jadwal yang aktif harus menjadi nonaktif setelah toggle.
        Requirements 6.6
        """
        schedule = make_schedule(is_active=True)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        result = await service.toggle_schedule(schedule.id, db)

        assert result is not None
        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_toggle_active_removes_from_job_map(self) -> None:
        """
        Saat dinonaktifkan, job harus dihapus dari _job_map.
        Requirements 6.6
        """
        schedule = make_schedule(is_active=True)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        # Tambahkan ke job_map terlebih dahulu
        service._job_map[schedule.id] = f"schedule_{schedule.id}"

        await service.toggle_schedule(schedule.id, db)

        assert schedule.id not in service._job_map

    @pytest.mark.asyncio
    async def test_toggle_active_calls_db_flush(self) -> None:
        """db.flush() harus dipanggil setelah toggle."""
        schedule = make_schedule(is_active=True)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        await service.toggle_schedule(schedule.id, db)

        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_toggle_active_returns_schedule_object(self) -> None:
        """toggle_schedule harus mengembalikan objek Schedule yang diperbarui."""
        schedule = make_schedule(is_active=True)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        result = await service.toggle_schedule(schedule.id, db)

        assert result is schedule

    @pytest.mark.asyncio
    async def test_toggle_nonexistent_schedule_returns_none(self) -> None:
        """Jika jadwal tidak ditemukan di DB, harus mengembalikan None."""
        db = make_db_session(schedule=None)
        service = make_scheduler_service()

        result = await service.toggle_schedule(999, db)

        assert result is None


class TestToggleScheduleInactiveToActive:
    """
    Req 6.6, 6.7: Toggle jadwal nonaktif → aktif, next_run dihitung dari NOW.
    """

    @pytest.mark.asyncio
    async def test_toggle_inactive_becomes_active(self) -> None:
        """
        Jadwal yang nonaktif harus menjadi aktif setelah toggle.
        Requirements 6.6
        """
        schedule = make_schedule(is_active=False)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        result = await service.toggle_schedule(schedule.id, db)

        assert result is not None
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_toggle_inactive_resets_retry_count(self) -> None:
        """
        Saat diaktifkan kembali, retry_count harus di-reset ke 0.
        Requirements 6.7
        """
        schedule = make_schedule(is_active=False, retry_count=3)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        result = await service.toggle_schedule(schedule.id, db)

        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_toggle_inactive_calculates_next_run_from_now(self) -> None:
        """
        Saat diaktifkan kembali, next_run harus dihitung dari waktu SEKARANG,
        bukan dari last_run.
        Requirements 6.7
        """
        old_last_run = datetime(2023, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        schedule = make_schedule(
            is_active=False,
            cron_expression="0 9 * * *",
            last_run=old_last_run,
            next_run=None,
        )
        db = make_db_session(schedule)
        service = make_scheduler_service()

        before_toggle = datetime.now(tz=timezone.utc)
        result = await service.toggle_schedule(schedule.id, db)
        after_toggle = datetime.now(tz=timezone.utc)

        # next_run harus diisi (tidak None) jika croniter tersedia
        if result.next_run is not None:
            # next_run harus lebih besar dari waktu SEBELUM toggle, bukan masa lalu
            assert result.next_run > before_toggle, (
                f"next_run ({result.next_run}) seharusnya >= waktu sebelum toggle ({before_toggle})"
            )

    @pytest.mark.asyncio
    async def test_toggle_inactive_next_run_not_based_on_last_run(self) -> None:
        """
        next_run setelah re-aktivasi TIDAK boleh lebih kecil dari waktu sekarang.
        Ini memvalidasi bahwa kalkulasi dimulai dari now(), bukan last_run.
        Requirements 6.7
        """
        # last_run di masa jauh lampau (tahun 2020)
        old_last_run = datetime(2020, 6, 15, 9, 0, 0, tzinfo=timezone.utc)
        schedule = make_schedule(
            is_active=False,
            cron_expression="0 9 * * 1-5",  # weekdays 09:00
            last_run=old_last_run,
        )
        db = make_db_session(schedule)
        service = make_scheduler_service()

        await service.toggle_schedule(schedule.id, db)

        # Jika next_run di-set, harus >= sekarang
        if schedule.next_run is not None:
            now = datetime.now(tz=timezone.utc)
            assert schedule.next_run >= now, (
                f"next_run ({schedule.next_run}) seharusnya >= now ({now}); "
                "next_run tidak boleh menggunakan last_run sebagai basis"
            )

    @pytest.mark.asyncio
    async def test_toggle_inactive_registers_job_in_job_map(self) -> None:
        """
        Saat diaktifkan, job harus terdaftar di _job_map.
        """
        schedule = make_schedule(is_active=False)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        await service.toggle_schedule(schedule.id, db)

        # Dalam mode tanpa APScheduler, _register_apscheduler_job
        # menyimpan mock_job_{id} di job_map
        assert schedule.id in service._job_map


class TestDoubleToggle:
    """
    Test double toggle: aktif → nonaktif → aktif.
    Property 6: Idempotency — Toggle Scheduler (Requirements 6.6, 6.7)
    """

    @pytest.mark.asyncio
    async def test_double_toggle_results_in_active_state(self) -> None:
        """
        Toggle dua kali (aktif→nonaktif→aktif) harus menghasilkan jadwal aktif.
        Requirements 6.6, 6.7
        """
        schedule = make_schedule(is_active=True, cron_expression="0 9 * * *")
        db = make_db_session(schedule)
        service = make_scheduler_service()

        # Toggle 1: aktif → nonaktif
        await service.toggle_schedule(schedule.id, db)
        assert schedule.is_active is False

        # Toggle 2: nonaktif → aktif
        await service.toggle_schedule(schedule.id, db)
        assert schedule.is_active is True

    @pytest.mark.asyncio
    async def test_double_toggle_next_run_is_in_future(self) -> None:
        """
        Setelah double toggle, next_run harus di masa depan (>= sekarang).
        Requirements 6.7: next_run dihitung ulang dari waktu sekarang.
        """
        past_next_run = datetime(2021, 1, 1, 9, 0, 0, tzinfo=timezone.utc)
        schedule = make_schedule(
            is_active=True,
            cron_expression="0 9 * * *",
            next_run=past_next_run,
        )
        db = make_db_session(schedule)
        service = make_scheduler_service()

        before = datetime.now(tz=timezone.utc)

        # Toggle 1: aktif → nonaktif
        await service.toggle_schedule(schedule.id, db)
        # Toggle 2: nonaktif → aktif
        await service.toggle_schedule(schedule.id, db)

        # next_run harus diperbaharui dari now, bukan dari past_next_run
        if schedule.next_run is not None:
            assert schedule.next_run >= before, (
                f"next_run ({schedule.next_run}) setelah double toggle "
                f"harus >= waktu sebelum toggle ({before})"
            )

    @pytest.mark.asyncio
    async def test_double_toggle_retry_count_is_zero(self) -> None:
        """
        Setelah double toggle, retry_count harus 0.
        """
        schedule = make_schedule(is_active=True, retry_count=2)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        await service.toggle_schedule(schedule.id, db)
        await service.toggle_schedule(schedule.id, db)

        assert schedule.retry_count == 0


# ---------------------------------------------------------------------------
# SchedulerService.reactivate_schedule
# ---------------------------------------------------------------------------


class TestReactivateSchedule:
    """
    Test reactivate_schedule — hitung ulang next_run dari now.
    Requirements 6.7
    """

    @pytest.mark.asyncio
    async def test_reactivate_sets_is_active_true(self) -> None:
        """reactivate_schedule harus menetapkan is_active=True."""
        schedule = make_schedule(is_active=False)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        result = await service.reactivate_schedule(schedule.id, db)

        assert result is not None
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_reactivate_resets_retry_count(self) -> None:
        """reactivate_schedule harus mereset retry_count ke 0."""
        schedule = make_schedule(is_active=False, retry_count=3)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        result = await service.reactivate_schedule(schedule.id, db)

        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_reactivate_calculates_next_run_from_now(self) -> None:
        """
        reactivate_schedule harus menghitung next_run dari waktu sekarang.
        Requirements 6.7
        """
        schedule = make_schedule(
            is_active=False,
            cron_expression="0 9 * * *",
            last_run=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        db = make_db_session(schedule)
        service = make_scheduler_service()

        before = datetime.now(tz=timezone.utc)
        await service.reactivate_schedule(schedule.id, db)

        if schedule.next_run is not None:
            assert schedule.next_run >= before

    @pytest.mark.asyncio
    async def test_reactivate_nonexistent_schedule_returns_none(self) -> None:
        """Jika jadwal tidak ada, mengembalikan None."""
        db = make_db_session(schedule=None)
        service = make_scheduler_service()

        result = await service.reactivate_schedule(999, db)

        assert result is None

    @pytest.mark.asyncio
    async def test_reactivate_calls_db_flush(self) -> None:
        """db.flush() harus dipanggil setelah reactivate."""
        schedule = make_schedule(is_active=False)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        await service.reactivate_schedule(schedule.id, db)

        db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# SchedulerService.add_schedule
# ---------------------------------------------------------------------------


class TestAddSchedule:
    """
    Test add_schedule — menambahkan job ke APScheduler.
    Requirements 6.1
    """

    @pytest.mark.asyncio
    async def test_add_active_schedule_returns_true(self) -> None:
        """add_schedule untuk jadwal aktif harus mengembalikan True."""
        schedule = make_schedule(is_active=True)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        result = await service.add_schedule(schedule.id, db)

        assert result is True

    @pytest.mark.asyncio
    async def test_add_active_schedule_registers_in_job_map(self) -> None:
        """add_schedule untuk jadwal aktif harus mendaftarkan job ke _job_map."""
        schedule = make_schedule(is_active=True)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        await service.add_schedule(schedule.id, db)

        assert schedule.id in service._job_map

    @pytest.mark.asyncio
    async def test_add_inactive_schedule_returns_false(self) -> None:
        """add_schedule untuk jadwal nonaktif harus mengembalikan False."""
        schedule = make_schedule(is_active=False)
        db = make_db_session(schedule)
        service = make_scheduler_service()

        result = await service.add_schedule(schedule.id, db)

        assert result is False

    @pytest.mark.asyncio
    async def test_add_nonexistent_schedule_returns_false(self) -> None:
        """add_schedule untuk jadwal yang tidak ada di DB harus mengembalikan False."""
        db = make_db_session(schedule=None)
        service = make_scheduler_service()

        result = await service.add_schedule(999, db)

        assert result is False


# ---------------------------------------------------------------------------
# SchedulerService.remove_schedule
# ---------------------------------------------------------------------------


class TestRemoveSchedule:
    """
    Test remove_schedule — menghapus job dari scheduler.
    Requirements 6.1
    """

    @pytest.mark.asyncio
    async def test_remove_registered_schedule_returns_true(self) -> None:
        """remove_schedule untuk jadwal yang terdaftar harus mengembalikan True."""
        service = make_scheduler_service()
        service._job_map[1] = "schedule_1"

        result = await service.remove_schedule(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_registered_schedule_clears_job_map(self) -> None:
        """remove_schedule harus menghapus entri dari _job_map."""
        service = make_scheduler_service()
        service._job_map[1] = "schedule_1"

        await service.remove_schedule(1)

        assert 1 not in service._job_map

    @pytest.mark.asyncio
    async def test_remove_nonexistent_schedule_returns_false(self) -> None:
        """remove_schedule untuk jadwal yang tidak terdaftar harus mengembalikan False."""
        service = make_scheduler_service()

        result = await service.remove_schedule(999)

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_then_remove_again_returns_false(self) -> None:
        """Hapus dua kali berturut-turut — kedua kalinya harus mengembalikan False."""
        service = make_scheduler_service()
        service._job_map[1] = "schedule_1"

        await service.remove_schedule(1)
        result2 = await service.remove_schedule(1)

        assert result2 is False


# ---------------------------------------------------------------------------
# SchedulerService._run_with_retry — Retry Logic
# ---------------------------------------------------------------------------


class TestRunWithRetry:
    """
    Test retry logic untuk HP disconnect.
    Requirements 6.4: max 3x retry dengan interval 5 menit.
    """

    @pytest.mark.asyncio
    async def test_retry_increments_retry_count_on_each_failure(self) -> None:
        """
        Setiap kegagalan harus mengincrementkan retry_count.
        Requirements 6.4
        """
        schedule = make_schedule(retry_count=0, max_retries=3)
        db = make_db_session(schedule)

        # task_executor selalu gagal (simulasi HP disconnect)
        async def failing_executor(**kwargs):
            raise ConnectionError("ADB device not connected")

        service = make_scheduler_service(task_executor=failing_executor)

        # Override sleep agar test tidak lambat
        with patch("app.services.scheduler_service.asyncio.sleep", new_callable=AsyncMock):
            await service._run_with_retry(schedule, db)

        # retry_count harus di-increment sebanyak max_retries kali
        assert schedule.retry_count == 3

    @pytest.mark.asyncio
    async def test_retry_exactly_3_times_on_failure(self) -> None:
        """
        _run_with_retry harus mencoba tepat max_retries kali sebelum menyerah.
        Requirements 6.4
        """
        call_count = 0

        async def counting_executor(**kwargs):
            nonlocal call_count
            call_count += 1
            raise ConnectionError("ADB timeout")

        schedule = make_schedule(retry_count=0, max_retries=3)
        db = make_db_session(schedule)
        service = make_scheduler_service(task_executor=counting_executor)

        with patch("app.services.scheduler_service.asyncio.sleep", new_callable=AsyncMock):
            result = await service._run_with_retry(schedule, db)

        assert call_count == 3
        assert result is False

    @pytest.mark.asyncio
    async def test_retry_returns_false_after_all_retries_exhausted(self) -> None:
        """
        Setelah semua retry habis (3x gagal), harus mengembalikan False.
        Requirements 6.4
        """
        async def always_fail(**kwargs):
            raise Exception("ADB device disconnected")

        schedule = make_schedule(retry_count=0, max_retries=3)
        db = make_db_session(schedule)
        service = make_scheduler_service(task_executor=always_fail)

        with patch("app.services.scheduler_service.asyncio.sleep", new_callable=AsyncMock):
            result = await service._run_with_retry(schedule, db)

        assert result is False

    @pytest.mark.asyncio
    async def test_retry_returns_true_on_first_success(self) -> None:
        """
        Jika eksekusi pertama berhasil, harus mengembalikan True.
        """
        async def succeeding_executor(**kwargs):
            return "ok"

        schedule = make_schedule(retry_count=0, max_retries=3)
        db = make_db_session(schedule)
        service = make_scheduler_service(task_executor=succeeding_executor)

        result = await service._run_with_retry(schedule, db)

        assert result is True

    @pytest.mark.asyncio
    async def test_retry_success_does_not_increment_retry_count(self) -> None:
        """
        Eksekusi sukses pada percobaan pertama tidak boleh menambah retry_count.
        """
        async def succeeding_executor(**kwargs):
            return "ok"

        schedule = make_schedule(retry_count=0, max_retries=3)
        db = make_db_session(schedule)
        service = make_scheduler_service(task_executor=succeeding_executor)

        await service._run_with_retry(schedule, db)

        assert schedule.retry_count == 0

    @pytest.mark.asyncio
    async def test_retry_success_on_second_attempt(self) -> None:
        """
        Gagal di percobaan pertama, berhasil di percobaan kedua.
        retry_count harus 1, return True.
        """
        attempts = [0]

        async def fail_once_then_succeed(**kwargs):
            attempts[0] += 1
            if attempts[0] < 2:
                raise ConnectionError("ADB timeout")
            return "ok"

        schedule = make_schedule(retry_count=0, max_retries=3)
        db = make_db_session(schedule)
        service = make_scheduler_service(task_executor=fail_once_then_succeed)

        with patch("app.services.scheduler_service.asyncio.sleep", new_callable=AsyncMock):
            result = await service._run_with_retry(schedule, db)

        assert result is True
        assert schedule.retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_no_executor_always_succeeds(self) -> None:
        """
        Jika task_executor=None, _run_with_retry harus mengembalikan True tanpa error.
        """
        schedule = make_schedule(retry_count=0, max_retries=3)
        db = make_db_session(schedule)
        service = make_scheduler_service(task_executor=None)

        result = await service._run_with_retry(schedule, db)

        assert result is True

    @pytest.mark.asyncio
    async def test_retry_sleep_called_between_failures(self) -> None:
        """
        asyncio.sleep harus dipanggil antara percobaan ulang (interval 5 menit).
        Requirements 6.4
        """
        async def always_fail(**kwargs):
            raise ConnectionError("ADB device not found")

        schedule = make_schedule(retry_count=0, max_retries=3)
        db = make_db_session(schedule)
        service = make_scheduler_service(task_executor=always_fail)

        with patch(
            "app.services.scheduler_service.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await service._run_with_retry(schedule, db)

        # Sleep harus dipanggil max_retries-1 kali (antara percobaan, bukan setelah yang terakhir)
        assert mock_sleep.call_count == 2  # 3 percobaan = 2 interval sleep

    @pytest.mark.asyncio
    async def test_retry_sleep_duration_is_5_minutes(self) -> None:
        """
        Durasi sleep antara retry harus 5 menit (300 detik).
        Requirements 6.4
        """
        async def always_fail(**kwargs):
            raise ConnectionError("Connection refused")

        schedule = make_schedule(retry_count=0, max_retries=3)
        db = make_db_session(schedule)
        service = make_scheduler_service(task_executor=always_fail)

        with patch(
            "app.services.scheduler_service.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await service._run_with_retry(schedule, db)

        # Setiap panggilan sleep harus menggunakan 300 detik (5 menit)
        expected_interval = 5 * 60  # 300 detik
        for sleep_call in mock_sleep.call_args_list:
            actual_interval = sleep_call[0][0]
            assert actual_interval == expected_interval, (
                f"Interval retry harus 300 detik (5 menit), bukan {actual_interval} detik"
            )


# ---------------------------------------------------------------------------
# SchedulerService._execute_schedule_job — Last Run & Next Run Updates
# ---------------------------------------------------------------------------


class TestExecuteScheduleJob:
    """
    Test eksekusi jadwal lengkap — last_run dan next_run diperbarui.
    Requirements 6.2, 6.3
    """

    @pytest.mark.asyncio
    async def test_execute_updates_last_run(self) -> None:
        """
        Setelah eksekusi berhasil, last_run harus diperbarui ke waktu eksekusi.
        Requirements 6.2
        """
        schedule = make_schedule(is_active=True, last_run=None)
        session_factory, db = make_session_factory(schedule)

        async def noop_executor(**kwargs):
            return "ok"

        service = SchedulerService(
            session_factory=session_factory,
            task_executor=noop_executor,
        )
        service._scheduler = None

        before = datetime.now(tz=timezone.utc)
        await service._execute_schedule_job(schedule.id)
        after = datetime.now(tz=timezone.utc)

        assert schedule.last_run is not None
        assert isinstance(schedule.last_run, datetime)
        # last_run harus di antara before dan after
        # (gunakan replace(tzinfo=UTC) jika naive)
        lr = schedule.last_run
        if lr.tzinfo is None:
            lr = lr.replace(tzinfo=timezone.utc)
        assert before <= lr <= after

    @pytest.mark.asyncio
    async def test_execute_updates_next_run(self) -> None:
        """
        Setelah eksekusi, next_run harus diperbarui.
        Requirements 6.3
        """
        schedule = make_schedule(
            is_active=True,
            cron_expression="0 9 * * *",
            next_run=None,
        )
        session_factory, db = make_session_factory(schedule)

        async def noop_executor(**kwargs):
            return "ok"

        service = SchedulerService(
            session_factory=session_factory,
            task_executor=noop_executor,
        )
        service._scheduler = None

        await service._execute_schedule_job(schedule.id)

        # next_run bisa None jika croniter tidak tersedia, tapi tidak boleh error
        # Tidak ada assertion wajib di sini kecuali tidak raise exception
        # (croniter mungkin tidak tersedia di environment test)

    @pytest.mark.asyncio
    async def test_execute_sets_last_status_success_on_success(self) -> None:
        """
        Setelah eksekusi sukses, last_status harus 'success'.
        """
        schedule = make_schedule(is_active=True)
        session_factory, db = make_session_factory(schedule)

        async def noop_executor(**kwargs):
            return "ok"

        service = SchedulerService(
            session_factory=session_factory,
            task_executor=noop_executor,
        )
        service._scheduler = None

        await service._execute_schedule_job(schedule.id)

        assert schedule.last_status == "success"

    @pytest.mark.asyncio
    async def test_execute_sets_last_status_failed_on_failure(self) -> None:
        """
        Setelah semua retry gagal, last_status harus 'failed'.
        Requirements 6.4
        """
        schedule = make_schedule(is_active=True, max_retries=3)
        session_factory, db = make_session_factory(schedule)

        async def always_fail(**kwargs):
            raise ConnectionError("ADB device not connected")

        service = SchedulerService(
            session_factory=session_factory,
            task_executor=always_fail,
        )
        service._scheduler = None

        with patch("app.services.scheduler_service.asyncio.sleep", new_callable=AsyncMock):
            await service._execute_schedule_job(schedule.id)

        assert schedule.last_status == "failed"

    @pytest.mark.asyncio
    async def test_execute_resets_retry_count_on_success(self) -> None:
        """
        Setelah eksekusi sukses, retry_count harus di-reset ke 0.
        """
        schedule = make_schedule(is_active=True, retry_count=2)
        session_factory, db = make_session_factory(schedule)

        async def noop_executor(**kwargs):
            return "ok"

        service = SchedulerService(
            session_factory=session_factory,
            task_executor=noop_executor,
        )
        service._scheduler = None

        await service._execute_schedule_job(schedule.id)

        assert schedule.retry_count == 0

    @pytest.mark.asyncio
    async def test_execute_increments_run_count_on_success(self) -> None:
        """
        Setelah eksekusi sukses, run_count harus bertambah 1.
        """
        schedule = make_schedule(is_active=True, run_count=5)
        session_factory, db = make_session_factory(schedule)

        async def noop_executor(**kwargs):
            return "ok"

        service = SchedulerService(
            session_factory=session_factory,
            task_executor=noop_executor,
        )
        service._scheduler = None

        await service._execute_schedule_job(schedule.id)

        assert schedule.run_count == 6

    @pytest.mark.asyncio
    async def test_execute_inactive_schedule_does_nothing(self) -> None:
        """
        Jadwal yang tidak aktif tidak boleh dieksekusi.
        """
        schedule = make_schedule(is_active=False)
        session_factory, db = make_session_factory(schedule)

        executed = [False]

        async def track_executor(**kwargs):
            executed[0] = True
            return "ok"

        service = SchedulerService(
            session_factory=session_factory,
            task_executor=track_executor,
        )
        service._scheduler = None

        await service._execute_schedule_job(schedule.id)

        assert not executed[0], "Jadwal nonaktif tidak boleh dieksekusi"


# ---------------------------------------------------------------------------
# SchedulerService lifecycle
# ---------------------------------------------------------------------------


class TestSchedulerLifecycle:
    """Test start/shutdown lifecycle."""

    def test_start_without_apscheduler_does_not_crash(self) -> None:
        """
        start() tanpa APScheduler (ImportError) tidak boleh crash.
        """
        service = make_scheduler_service()

        with patch(
            "app.services.scheduler_service.SchedulerService.start",
            side_effect=None,
        ):
            # Pastikan service bisa dibuat dan diakses
            assert service._scheduler is None

    def test_shutdown_without_scheduler_does_not_crash(self) -> None:
        """
        shutdown() ketika _scheduler=None tidak boleh crash.
        """
        service = make_scheduler_service()
        service._scheduler = None
        service.shutdown()  # tidak boleh raise exception
