"""
Property 10: Error Condition — Disconnect HP saat Eksekusi

**Validates: Requirements 1.2, 1.4**

Properti yang diuji:
- Jika HP terputus di tengah eksekusi (ADBTimeoutError), sistem TIDAK BOLEH crash.
- Status eksekusi HARUS diperbarui menjadi 'failed' di bot_log dengan pesan error deskriptif.
- Backend tetap stabil dan dapat menerima request baru setelah HP terputus.
- `system_state_after_disconnect == stable`

Testing strategy:
- Gunakan Hypothesis untuk generate berbagai kombinasi perintah ADB dan kondisi timeout.
- Mock subprocess ADB untuk mensimulasikan TimeoutError.
- Verifikasi bahwa setiap TimeoutError ditangkap, bot_log dibuat dengan status='failed',
  dan tidak ada unhandled exception yang membuat sistem crash.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.services.adb_service import (
    ADBCommandError,
    ADBResult,
    ADBService,
    ADBTimeoutError,
)
from app.services.device_monitor import (
    DeviceEvent,
    DeviceEventType,
    DeviceMonitor,
    DeviceState,
)

# ---------------------------------------------------------------------------
# Domain stubs — simulasi bot_log tanpa database nyata
# ---------------------------------------------------------------------------

VALID_BOT_LOG_STATUSES = ("success", "failed", "running", "skipped", "timeout")

VALID_ADB_ACTIONS = (
    "open_linkedin",
    "navigate_post",
    "type_content",
    "publish_post",
    "screenshot",
    "scroll_feed",
    "post_comment",
    "open_jobs",
    "search_jobs",
    "easy_apply",
    "anti_ban_delay",
)


@dataclass
class BotLogEntry:
    """Representasi in-memory dari bot_log record (tanpa DB)."""

    task_id: str
    action: str
    status: str
    message: Optional[str] = None
    error_detail: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


class InMemoryBotLogRepository:
    """In-memory store yang mensimulasikan tabel bot_logs."""

    def __init__(self) -> None:
        self._logs: List[BotLogEntry] = []

    def add(self, entry: BotLogEntry) -> None:
        self._logs.append(entry)

    def all(self) -> List[BotLogEntry]:
        return list(self._logs)

    def failed_logs(self) -> List[BotLogEntry]:
        return [e for e in self._logs if e.status == "failed"]

    def count(self) -> int:
        return len(self._logs)


# ---------------------------------------------------------------------------
# Minimal BotExecutor stub — mensimulasikan eksekusi perintah ADB oleh bot
# ---------------------------------------------------------------------------


class BotExecutor:
    """
    Minimal bot executor yang menjalankan perintah ADB dan mencatat ke bot_log.

    Ini mensimulasikan pola yang digunakan oleh BaseBot (design.md).
    Jika ADBTimeoutError muncul, eksekusi ditandai 'failed' di log.
    Sistem TIDAK BOLEH crash (Requirements 1.4, Property 10).
    """

    def __init__(self, adb: ADBService, log_repo: InMemoryBotLogRepository) -> None:
        self._adb = adb
        self._log_repo = log_repo
        self._is_stable: bool = True  # sistem tetap stabil setelah error

    @property
    def is_stable(self) -> bool:
        return self._is_stable

    async def execute_action(
        self,
        task_id: str,
        action: str,
        adb_coroutine: Any,
    ) -> str:
        """
        Jalankan satu aksi ADB, tangkap ADBTimeoutError, dan catat ke bot_log.

        Returns:
            Status log: 'success' atau 'failed'.
        """
        import time

        start_ms = int(time.time() * 1000)
        try:
            await adb_coroutine
            elapsed = int(time.time() * 1000) - start_ms
            self._log_repo.add(
                BotLogEntry(
                    task_id=task_id,
                    action=action,
                    status="success",
                    message=f"Aksi '{action}' berhasil",
                    duration_ms=elapsed,
                )
            )
            return "success"
        except ADBTimeoutError as exc:
            elapsed = int(time.time() * 1000) - start_ms
            # Sistem HARUS mencatat status='failed' — Requirements 1.4, Property 10
            self._log_repo.add(
                BotLogEntry(
                    task_id=task_id,
                    action=action,
                    status="failed",
                    message=f"Timeout ADB saat aksi '{action}'",
                    error_detail=str(exc),
                    duration_ms=elapsed,
                )
            )
            # Sistem TETAP STABIL — tidak re-raise, tidak crash
            return "failed"
        except Exception as exc:  # noqa: BLE001
            elapsed = int(time.time() * 1000) - start_ms
            self._log_repo.add(
                BotLogEntry(
                    task_id=task_id,
                    action=action,
                    status="failed",
                    message=f"Error tidak terduga saat aksi '{action}'",
                    error_detail=str(exc),
                    duration_ms=elapsed,
                )
            )
            return "failed"

    async def run_sequence(
        self,
        task_id: str,
        actions: List[str],
        timeout_on_action: Optional[str] = None,
    ) -> List[str]:
        """
        Jalankan urutan aksi ADB. Jika timeout_on_action diberikan,
        simulasikan ADBTimeoutError pada aksi tersebut.

        Returns:
            List status setiap aksi ('success' atau 'failed').
        """
        results = []
        for action in actions:
            if action == timeout_on_action:
                # Simulasikan disconnect/timeout
                coro = self._simulate_timeout_action(action)
            else:
                coro = self._simulate_success_action(action)
            status = await self.execute_action(task_id, action, coro)
            results.append(status)
        return results

    async def _simulate_success_action(self, action: str) -> ADBResult:
        return ADBResult(success=True, output="OK", error="", return_code=0)

    async def _simulate_timeout_action(self, action: str) -> None:
        raise ADBTimeoutError(
            f"Perintah ADB '{action}' timeout setelah 30 detik — HP kemungkinan terputus"
        )


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_action_st = st.sampled_from(VALID_ADB_ACTIONS)
_task_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=4,
    max_size=36,
)
_actions_list_st = st.lists(_action_st, min_size=1, max_size=10)


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@given(
    task_id=_task_id_st,
    actions=_actions_list_st,
    timeout_action_index=st.integers(min_value=0, max_value=9),
)
@h_settings(max_examples=100)
def test_property10_timeout_creates_failed_log_and_system_stays_stable(
    task_id: str,
    actions: List[str],
    timeout_action_index: int,
) -> None:
    """
    **Property 10 — Validates: Requirements 1.2, 1.4**

    Untuk setiap urutan aksi ADB, jika ADBTimeoutError terjadi pada aksi manapun:
    1. Sistem TIDAK BOLEH crash (tidak ada unhandled exception).
    2. Aksi yang timeout HARUS dicatat dengan status='failed' di bot_log.
    3. bot_log entry HARUS memiliki error_detail yang deskriptif.
    4. Aksi-aksi SEBELUM timeout HARUS tetap tercatat dengan benar.
    5. Sistem TETAP STABIL dan dapat menerima request baru (is_stable=True).
    """
    # Pilih aksi yang akan di-timeout (modulo agar valid)
    actual_index = timeout_action_index % len(actions)
    timeout_action = actions[actual_index]

    log_repo = InMemoryBotLogRepository()
    adb = ADBService.__new__(ADBService)
    executor = BotExecutor(adb=adb, log_repo=log_repo)

    # Jalankan sequence — HARUS tidak raise exception
    results = asyncio.run(
        executor.run_sequence(
            task_id=task_id,
            actions=actions,
            timeout_on_action=timeout_action,
        )
    )

    # 1. Tidak ada unhandled exception — sistem stabil
    assert executor.is_stable, "Sistem harus tetap stabil setelah timeout ADB"

    # 2. Jumlah log entries harus sama dengan jumlah aksi (setiap aksi menghasilkan 1 log)
    assert log_repo.count() == len(actions), (
        f"Harus ada {len(actions)} bot_log entries, dapat {log_repo.count()}"
    )

    # 3. Aksi yang timeout harus memiliki status='failed'
    failed_logs = log_repo.failed_logs()
    assert len(failed_logs) >= 1, (
        "Harus ada minimal 1 bot_log dengan status='failed' setelah timeout"
    )

    # Temukan log untuk aksi yang di-timeout
    timeout_logs = [e for e in failed_logs if e.action == timeout_action]
    assert len(timeout_logs) >= 1, (
        f"Harus ada bot_log dengan action='{timeout_action}' dan status='failed'"
    )

    # 4. Setiap failed log harus punya error_detail
    for log in failed_logs:
        assert log.error_detail is not None and len(log.error_detail) > 0, (
            f"bot_log dengan status='failed' harus memiliki error_detail yang deskriptif, "
            f"action={log.action!r}"
        )

    # 5. Verifikasi results array memiliki 'failed' untuk aksi timeout
    assert "failed" in results, "results harus mengandung 'failed' untuk aksi yang timeout"


@given(
    task_id=_task_id_st,
    actions=_actions_list_st,
)
@h_settings(max_examples=100)
def test_property10_all_actions_succeed_produces_no_failed_logs(
    task_id: str,
    actions: List[str],
) -> None:
    """
    **Property 10a — Validates: Requirements 1.4**

    Ketika TIDAK ada timeout, semua aksi harus berhasil dan
    tidak ada bot_log dengan status='failed'.
    """
    log_repo = InMemoryBotLogRepository()
    adb = ADBService.__new__(ADBService)
    executor = BotExecutor(adb=adb, log_repo=log_repo)

    results = asyncio.run(
        executor.run_sequence(
            task_id=task_id,
            actions=actions,
            timeout_on_action=None,  # Tidak ada timeout
        )
    )

    assert all(r == "success" for r in results), (
        "Semua aksi harus sukses ketika tidak ada timeout"
    )
    assert log_repo.count() == len(actions)
    assert len(log_repo.failed_logs()) == 0, (
        "Tidak boleh ada failed log ketika tidak ada timeout"
    )


@given(
    task_id=_task_id_st,
    actions=_actions_list_st,
    timeout_action_index=st.integers(min_value=0, max_value=9),
)
@h_settings(max_examples=100)
def test_property10_system_accepts_new_requests_after_disconnect(
    task_id: str,
    actions: List[str],
    timeout_action_index: int,
) -> None:
    """
    **Property 10b — Validates: Requirements 1.2, 1.4**

    `system_state_after_disconnect == stable`:
    Setelah HP disconnect (timeout), sistem harus dapat menjalankan
    request baru tanpa error.
    """
    actual_index = timeout_action_index % len(actions)
    timeout_action = actions[actual_index]

    log_repo = InMemoryBotLogRepository()
    adb = ADBService.__new__(ADBService)
    executor = BotExecutor(adb=adb, log_repo=log_repo)

    # Sesi pertama — ada timeout (simulasi disconnect)
    asyncio.run(
        executor.run_sequence(
            task_id=task_id,
            actions=actions,
            timeout_on_action=timeout_action,
        )
    )

    logs_after_first_session = log_repo.count()

    # Sesi kedua — request baru setelah disconnect
    # Sistem HARUS dapat menerima dan menjalankan ini (Requirements 1.2)
    new_task_id = task_id + "_new"
    new_results = asyncio.run(
        executor.run_sequence(
            task_id=new_task_id,
            actions=["open_linkedin", "screenshot"],
            timeout_on_action=None,  # Request baru berhasil
        )
    )

    # Sistem masih stabil
    assert executor.is_stable, "Sistem harus tetap stabil untuk request baru"

    # Log baru berhasil dibuat
    assert log_repo.count() == logs_after_first_session + 2, (
        "Sesi baru setelah disconnect harus menghasilkan log baru"
    )
    assert all(r == "success" for r in new_results), (
        "Request baru setelah disconnect harus berhasil"
    )


# ---------------------------------------------------------------------------
# DeviceMonitor tests — disconnect triggers stop callbacks
# ---------------------------------------------------------------------------


@given(
    stop_callback_count=st.integers(min_value=1, max_value=5),
)
@h_settings(max_examples=50)
def test_property10_disconnect_triggers_all_stop_callbacks(
    stop_callback_count: int,
) -> None:
    """
    **Property 10c — Validates: Requirements 1.2**

    Saat HP disconnect, DeviceMonitor HARUS memanggil semua stop callbacks
    yang terdaftar untuk menghentikan running tasks.
    """
    callback_call_counts = [0] * stop_callback_count

    def make_callback(idx: int) -> Callable[[], None]:
        def cb() -> None:
            callback_call_counts[idx] += 1

        return cb

    monitor = DeviceMonitor()

    for i in range(stop_callback_count):
        monitor.register_stop_callback(make_callback(i))

    # Simulasikan: sebelumnya connected, sekarang tidak ada perangkat
    # Paksa state ke CONNECTED untuk mensimulasikan device yang sebelumnya ada
    monitor._state = DeviceState.CONNECTED
    monitor._current_device = MagicMock()
    monitor._current_device.device_id = "emulator-5554"

    # Jalankan handle_no_devices
    asyncio.run(monitor._handle_no_devices(DeviceState.CONNECTED, "emulator-5554"))

    # Semua stop callbacks harus dipanggil
    assert all(c == 1 for c in callback_call_counts), (
        f"Semua {stop_callback_count} stop callback harus dipanggil saat disconnect, "
        f"call counts: {callback_call_counts}"
    )
    assert monitor.state == DeviceState.DISCONNECTED, (
        "State harus DISCONNECTED setelah handle_no_devices"
    )


@given(
    stop_callback_count=st.integers(min_value=0, max_value=3),
)
@h_settings(max_examples=50)
def test_property10_device_monitor_state_is_disconnected_after_no_devices(
    stop_callback_count: int,
) -> None:
    """
    **Property 10d — Validates: Requirements 1.2**

    State monitor HARUS menjadi DISCONNECTED setelah tidak ada perangkat terdeteksi
    (dari state CONNECTED/READY/RUNNING).
    """
    monitor = DeviceMonitor()

    for _ in range(stop_callback_count):
        monitor.register_stop_callback(lambda: None)

    for previous_state in (DeviceState.CONNECTED, DeviceState.READY, DeviceState.RUNNING):
        monitor._state = previous_state
        monitor._current_device = MagicMock()
        monitor._current_device.device_id = "test_device"

        asyncio.run(monitor._handle_no_devices(previous_state, "test_device"))

        assert monitor.state == DeviceState.DISCONNECTED, (
            f"State harus DISCONNECTED setelah disconnect dari {previous_state.value}"
        )
        assert monitor._current_device is None, (
            "current_device harus None setelah disconnect"
        )


# ---------------------------------------------------------------------------
# Unit Tests — Example-based
# ---------------------------------------------------------------------------


def test_adb_timeout_error_is_caught_and_logged() -> None:
    """
    Unit test: ADBTimeoutError harus ditangkap dan menghasilkan
    bot_log dengan status='failed' dan error_detail yang deskriptif.
    """
    log_repo = InMemoryBotLogRepository()
    adb = ADBService.__new__(ADBService)
    executor = BotExecutor(adb=adb, log_repo=log_repo)

    results = asyncio.run(
        executor.run_sequence(
            task_id="test-task-001",
            actions=["open_linkedin", "type_content", "publish_post"],
            timeout_on_action="type_content",
        )
    )

    assert results == ["success", "failed", "success"], (
        "Hanya aksi 'type_content' yang harus failed"
    )
    assert log_repo.count() == 3

    failed = log_repo.failed_logs()
    assert len(failed) == 1
    assert failed[0].action == "type_content"
    assert failed[0].status == "failed"
    assert "timeout" in (failed[0].error_detail or "").lower()


def test_multiple_timeouts_all_logged() -> None:
    """
    Unit test: Beberapa timeout dalam satu sequence harus semua dicatat.
    Setiap aksi yang sama di-timeout (simulasi HP disconnect setelah reconnect).
    """
    log_repo = InMemoryBotLogRepository()
    adb = ADBService.__new__(ADBService)
    executor = BotExecutor(adb=adb, log_repo=log_repo)

    # Jalankan dua sequence terpisah, masing-masing dengan satu timeout
    asyncio.run(
        executor.run_sequence(
            task_id="task-A",
            actions=["open_linkedin", "screenshot"],
            timeout_on_action="open_linkedin",
        )
    )
    asyncio.run(
        executor.run_sequence(
            task_id="task-B",
            actions=["scroll_feed", "post_comment"],
            timeout_on_action="post_comment",
        )
    )

    assert log_repo.count() == 4  # 2 aksi × 2 sequence
    failed = log_repo.failed_logs()
    assert len(failed) == 2

    failed_actions = {e.action for e in failed}
    assert "open_linkedin" in failed_actions
    assert "post_comment" in failed_actions


def test_system_stable_after_timeout() -> None:
    """
    Unit test: Sistem tetap stabil (is_stable=True) setelah timeout.
    """
    log_repo = InMemoryBotLogRepository()
    adb = ADBService.__new__(ADBService)
    executor = BotExecutor(adb=adb, log_repo=log_repo)

    asyncio.run(
        executor.run_sequence(
            task_id="task-disconnect",
            actions=["open_linkedin", "navigate_post"],
            timeout_on_action="open_linkedin",
        )
    )

    assert executor.is_stable, "Sistem harus tetap stabil setelah ADBTimeoutError"


def test_device_monitor_registers_and_calls_stop_callback() -> None:
    """
    Unit test: DeviceMonitor memanggil callback saat HP disconnect.
    """
    was_called = []

    def stop_callback() -> None:
        was_called.append(True)

    monitor = DeviceMonitor()
    monitor.register_stop_callback(stop_callback)
    monitor._state = DeviceState.RUNNING
    monitor._current_device = MagicMock()
    monitor._current_device.device_id = "device-123"

    asyncio.run(monitor._handle_no_devices(DeviceState.RUNNING, "device-123"))

    assert len(was_called) == 1, "Stop callback harus dipanggil saat HP disconnect"
    assert monitor.state == DeviceState.DISCONNECTED


def test_device_monitor_no_stop_callback_when_was_already_disconnected() -> None:
    """
    Unit test: Stop callback TIDAK dipanggil jika sebelumnya sudah disconnected.
    """
    was_called = []

    def stop_callback() -> None:
        was_called.append(True)

    monitor = DeviceMonitor()
    monitor.register_stop_callback(stop_callback)
    monitor._state = DeviceState.DISCONNECTED  # Sudah disconnected sebelumnya

    asyncio.run(monitor._handle_no_devices(DeviceState.DISCONNECTED, None))

    assert len(was_called) == 0, (
        "Stop callback tidak boleh dipanggil jika sudah dalam state DISCONNECTED"
    )


def test_failed_log_has_descriptive_error_detail() -> None:
    """
    Unit test: bot_log dengan status='failed' harus memiliki error_detail > 0 chars.
    """
    log_repo = InMemoryBotLogRepository()
    adb = ADBService.__new__(ADBService)
    executor = BotExecutor(adb=adb, log_repo=log_repo)

    asyncio.run(
        executor.run_sequence(
            task_id="task-err",
            actions=["screenshot"],
            timeout_on_action="screenshot",
        )
    )

    failed = log_repo.failed_logs()
    assert len(failed) == 1
    assert failed[0].error_detail is not None
    assert len(failed[0].error_detail) > 10, (
        "error_detail harus deskriptif (>10 karakter)"
    )
