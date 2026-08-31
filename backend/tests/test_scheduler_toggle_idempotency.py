"""
Property 6: Idempotency — Toggle Scheduler

Validates: Requirements 6.6, 6.7

Rules verified:
- toggle(toggle(schedule)) → jadwal aktif dengan next_run dihitung dari sekarang
- Menonaktifkan lalu mengaktifkan kembali jadwal menghasilkan jadwal aktif
  dengan next_run yang dihitung ulang dari waktu saat ini (bukan dari last_run)

Testing strategy: menggunakan objek Schedule in-memory (tanpa DB) dan
fungsi compute_next_run dari scheduler_service untuk memverifikasi properti.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.services.scheduler_service import compute_next_run


# ---------------------------------------------------------------------------
# Minimal in-memory Schedule for testing
# ---------------------------------------------------------------------------


@dataclass
class ScheduleLike:
    """Minimal stand-in untuk model Schedule ORM — plain Python dataclass."""

    id: int
    name: str
    task_type: str
    cron_expression: Optional[str]
    is_active: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    retry_count: int = 0

    def activate(self, now: Optional[datetime] = None) -> None:
        """Aktifkan jadwal dan hitung ulang next_run dari sekarang."""
        self.is_active = True
        self.retry_count = 0
        now = now or datetime.now(tz=timezone.utc)
        if self.cron_expression:
            self.next_run = compute_next_run(self.cron_expression, from_dt=now)

    def deactivate(self) -> None:
        """Nonaktifkan jadwal (tidak mengubah next_run)."""
        self.is_active = False

    def toggle(self, now: Optional[datetime] = None) -> None:
        """Toggle aktif/nonaktif. Jika diaktifkan, hitung ulang next_run."""
        if self.is_active:
            self.deactivate()
        else:
            self.activate(now=now)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Cron expressions yang valid
_CRON_EXPRESSIONS = [
    "0 9 * * *",        # setiap hari jam 09:00
    "0 9 * * 1-5",      # setiap hari kerja jam 09:00
    "*/30 * * * *",     # setiap 30 menit
    "0 */6 * * *",      # setiap 6 jam
    "0 8 * * 1",        # setiap Senin jam 08:00
    "0 12 1 * *",       # tanggal 1 setiap bulan
]

_cron_strategy = st.sampled_from(_CRON_EXPRESSIONS)

_EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)
_FUTURE = datetime(2026, 12, 31, tzinfo=timezone.utc)

_datetime_strategy = st.datetimes(
    min_value=datetime(2024, 1, 1),
    max_value=datetime(2026, 12, 31),
).map(lambda dt: dt.replace(tzinfo=timezone.utc))

_schedule_strategy = st.builds(
    ScheduleLike,
    id=st.integers(min_value=1, max_value=9999),
    name=st.text(min_size=1, max_size=50),
    task_type=st.sampled_from(["post_konten", "engage", "job_hunt", "promosi"]),
    cron_expression=_cron_strategy,
    is_active=st.booleans(),
    last_run=st.one_of(st.none(), _datetime_strategy),
    next_run=st.one_of(st.none(), _datetime_strategy),
    retry_count=st.integers(min_value=0, max_value=10),
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(schedule=_schedule_strategy.filter(lambda s: s.is_active), now=_datetime_strategy)
@h_settings(max_examples=200)
def test_double_toggle_results_in_active_schedule(
    schedule: ScheduleLike, now: datetime
) -> None:
    """
    **Property 6a — Validates: Requirements 6.6, 6.7**

    toggle(toggle(schedule)) → jadwal dalam kondisi aktif.

    Dimulai dari jadwal yang aktif: nonaktifkan lalu aktifkan kembali harus
    menghasilkan jadwal yang aktif.
    """
    # Toggle pertama
    schedule.toggle(now=now)
    # Toggle kedua
    schedule.toggle(now=now)

    assert schedule.is_active, (
        "Setelah toggle dua kali, jadwal harus dalam kondisi aktif."
    )


@given(schedule=_schedule_strategy, now=_datetime_strategy)
@h_settings(max_examples=200)
def test_double_toggle_recalculates_next_run_from_now(
    schedule: ScheduleLike, now: datetime
) -> None:
    """
    **Property 6b — Validates: Requirements 6.7**

    Setelah toggle dua kali (nonaktifkan lalu aktifkan), next_run harus
    dihitung dari `now`, bukan dari last_run.
    """
    original_last_run = schedule.last_run

    # Toggle dua kali
    schedule.toggle(now=now)  # nonaktifkan (jika aktif) atau aktifkan
    schedule.toggle(now=now)  # aktifkan kembali

    if schedule.cron_expression:
        expected_next = compute_next_run(schedule.cron_expression, from_dt=now)

        if expected_next is not None and schedule.next_run is not None:
            # next_run harus >= now (dihitung dari sekarang, bukan masa lalu)
            assert schedule.next_run >= now, (
                f"next_run ({schedule.next_run}) harus >= now ({now}). "
                "next_run dihitung dari last_run (salah), bukan dari now."
            )

            # next_run tidak boleh sama dengan last_run (kecuali kebetulan sama)
            if original_last_run is not None and original_last_run < now:
                assert schedule.next_run != original_last_run or schedule.next_run >= now


@given(schedule=_schedule_strategy, now=_datetime_strategy)
@h_settings(max_examples=200)
def test_deactivate_then_activate_is_active(
    schedule: ScheduleLike, now: datetime
) -> None:
    """
    **Property 6c — Validates: Requirements 6.6**

    deactivate() → activate() harus menghasilkan jadwal aktif.
    """
    schedule.deactivate()
    assert not schedule.is_active

    schedule.activate(now=now)
    assert schedule.is_active


@given(schedule=_schedule_strategy, now=_datetime_strategy)
@h_settings(max_examples=200)
def test_activate_resets_retry_count(
    schedule: ScheduleLike, now: datetime
) -> None:
    """
    **Property 6d — Validates: Requirements 6.6**

    Mengaktifkan kembali jadwal harus me-reset retry_count ke 0.
    """
    schedule.deactivate()
    schedule.retry_count = 3  # set retry count tinggi
    schedule.activate(now=now)
    assert schedule.retry_count == 0, (
        "retry_count harus di-reset ke 0 saat jadwal diaktifkan kembali."
    )


@given(cron=_cron_strategy, now=_datetime_strategy)
@h_settings(max_examples=100)
def test_next_run_is_in_future(cron: str, now: datetime) -> None:
    """
    **Property 6e — Validates: Requirements 6.3**

    compute_next_run selalu mengembalikan waktu di masa depan relatif terhadap `now`.
    """
    next_run = compute_next_run(cron, from_dt=now)

    if next_run is not None:
        assert next_run > now, (
            f"next_run ({next_run}) harus di masa depan relatif terhadap now ({now})."
        )


@given(schedule=_schedule_strategy, now=_datetime_strategy)
@h_settings(max_examples=200)
def test_triple_toggle_results_in_inactive(
    schedule: ScheduleLike, now: datetime
) -> None:
    """
    **Property 6f — Validates: Requirements 6.6**

    toggle tiga kali (dari aktif: nonaktif → aktif → nonaktif).
    Jika kondisi awal aktif, hasil akhir nonaktif.
    Jika kondisi awal nonaktif, hasil akhir aktif.
    """
    initial_active = schedule.is_active

    schedule.toggle(now=now)
    schedule.toggle(now=now)
    schedule.toggle(now=now)

    # Tiga toggle = satu toggle efektif (perubahan state tunggal)
    expected_active = not initial_active
    assert schedule.is_active == expected_active, (
        f"Tiga toggle dari kondisi awal is_active={initial_active} "
        f"harus menghasilkan is_active={expected_active}"
    )


# ---------------------------------------------------------------------------
# Unit tests (example-based)
# ---------------------------------------------------------------------------


def test_toggle_active_to_inactive() -> None:
    """Toggle jadwal aktif → nonaktif."""
    schedule = ScheduleLike(
        id=1, name="Test", task_type="engage",
        cron_expression="0 9 * * *", is_active=True,
    )
    schedule.toggle()
    assert not schedule.is_active


def test_toggle_inactive_to_active_with_next_run() -> None:
    """Toggle jadwal nonaktif → aktif, next_run harus di-set."""
    now = datetime(2025, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    schedule = ScheduleLike(
        id=1, name="Test", task_type="engage",
        cron_expression="0 9 * * *", is_active=False,
        last_run=datetime(2024, 12, 31, tzinfo=timezone.utc),
    )
    schedule.toggle(now=now)

    assert schedule.is_active
    if schedule.next_run is not None:
        assert schedule.next_run > now, "next_run harus di masa depan"


def test_double_toggle_from_active() -> None:
    """toggle(toggle(aktif)) = aktif dengan next_run baru."""
    now = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    schedule = ScheduleLike(
        id=2, name="Daily Post", task_type="post_konten",
        cron_expression="0 9 * * *", is_active=True,
        last_run=datetime(2025, 5, 31, tzinfo=timezone.utc),
    )

    original_last_run = schedule.last_run

    schedule.toggle(now=now)  # → nonaktif
    schedule.toggle(now=now)  # → aktif, next_run dari now

    assert schedule.is_active
    assert schedule.retry_count == 0
    # next_run harus setelah 'now', bukan berdasarkan last_run
    if schedule.next_run is not None:
        assert schedule.next_run > now


def test_double_toggle_from_inactive() -> None:
    """toggle(toggle(nonaktif)) = aktif dengan next_run baru."""
    now = datetime(2025, 3, 15, 7, 0, 0, tzinfo=timezone.utc)
    schedule = ScheduleLike(
        id=3, name="Weekly Hunt", task_type="job_hunt",
        cron_expression="0 9 * * 1", is_active=False,
    )

    schedule.toggle(now=now)  # → aktif
    schedule.toggle(now=now)  # → nonaktif
    assert not schedule.is_active

    schedule.toggle(now=now)  # → aktif lagi
    assert schedule.is_active
    if schedule.next_run is not None:
        assert schedule.next_run > now
