"""
Device Monitor — Background task untuk memantau status koneksi HP Android.

Komponen ini:
- Poll `adb devices` setiap 5 detik (Requirements 1.5)
- Emit event saat status berubah: connected, disconnected, error (Requirements 1.5)
- Menghentikan running tasks saat HP disconnect (Requirements 1.2)
- Callback/broadcaster opsional untuk integrasi WebSocket (task 18)

State machine perangkat (dari design.md):
    Disconnected → Detecting → Connected → Ready → Running → Error
    Running → Disconnected (jika USB dicabut)

Requirements: 1.1, 1.2, 1.5
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.services.adb_service import ADBService, ADBTimeoutError, DeviceInfo

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Device State Machine
# ---------------------------------------------------------------------------


class DeviceState(str, Enum):
    """State machine status perangkat Android (dari design.md)."""

    DISCONNECTED = "disconnected"
    DETECTING = "detecting"
    CONNECTED = "connected"
    READY = "ready"      # LinkedIn verified
    RUNNING = "running"  # Bot sedang berjalan
    ERROR = "error"


# ---------------------------------------------------------------------------
# Event Types (untuk WebSocket — task 18)
# ---------------------------------------------------------------------------


class DeviceEventType(str, Enum):
    """Tipe event yang dikirim ke broadcaster."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    LINKEDIN_READY = "linkedin_ready"
    STATUS_UPDATE = "status_update"


@dataclass
class DeviceEvent:
    """Payload event yang dikirim ke broadcaster."""

    event_type: DeviceEventType
    device_id: Optional[str]
    state: DeviceState
    message: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Broadcaster type alias
# ---------------------------------------------------------------------------

# Tipe callback broadcaster: menerima DeviceEvent, bisa sync atau async.
# Akan diisi oleh WebSocket manager (task 18). Default: None (tidak ada broadcast).
BroadcasterCallback = Callable[[DeviceEvent], Any]


# ---------------------------------------------------------------------------
# DeviceMonitor
# ---------------------------------------------------------------------------


class DeviceMonitor:
    """
    Monitor koneksi HP Android secara berkala.

    Poll `adb devices` setiap POLL_INTERVAL_SECONDS detik.
    Saat status berubah, panggil broadcaster callback jika ada.
    Saat HP disconnect, panggil semua stop_callback yang terdaftar
    untuk menghentikan task yang sedang berjalan.

    Penggunaan:
        monitor = DeviceMonitor(broadcaster=ws_manager.broadcast)
        await monitor.start()
        ...
        await monitor.stop()

    Requirements: 1.1, 1.2, 1.5
    """

    POLL_INTERVAL_SECONDS: float = 5.0  # Interval polling (Requirements 1.5)
    DETECT_TIMEOUT_SECONDS: float = 10.0  # Timeout deteksi perangkat (Requirements 1.1)

    def __init__(
        self,
        broadcaster: Optional[BroadcasterCallback] = None,
        adb_service: Optional[ADBService] = None,
    ) -> None:
        """
        Inisialisasi DeviceMonitor.

        Args:
            broadcaster: Callback opsional yang dipanggil saat ada event device.
                         Dapat sync atau async. Akan diintegrasikan dengan
                         WebSocket manager pada task 18.
            adb_service:  Instance ADBService. Jika None, dibuat secara otomatis.
        """
        self._broadcaster = broadcaster
        self._adb = adb_service or ADBService()

        self._state: DeviceState = DeviceState.DISCONNECTED
        self._current_device: Optional[DeviceInfo] = None

        # Callbacks yang dipanggil saat HP disconnect — Requirements 1.2
        self._stop_callbacks: List[Callable[[], Any]] = []

        self._running: bool = False
        self._task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> DeviceState:
        """State perangkat saat ini."""
        return self._state

    @property
    def current_device(self) -> Optional[DeviceInfo]:
        """Info perangkat yang sedang terhubung."""
        return self._current_device

    @property
    def is_connected(self) -> bool:
        """True jika ada perangkat yang terhubung."""
        return self._state in (
            DeviceState.CONNECTED,
            DeviceState.READY,
            DeviceState.RUNNING,
        )

    def register_stop_callback(self, callback: Callable[[], Any]) -> None:
        """
        Daftarkan callback yang akan dipanggil saat HP disconnect.

        Digunakan oleh BotService untuk menghentikan task yang sedang berjalan.

        Args:
            callback: Fungsi (sync atau async) yang dipanggil saat disconnect.

        Requirements: 1.2
        """
        self._stop_callbacks.append(callback)

    def unregister_stop_callback(self, callback: Callable[[], Any]) -> None:
        """Hapus callback dari daftar."""
        try:
            self._stop_callbacks.remove(callback)
        except ValueError:
            pass

    async def start(self) -> None:
        """
        Mulai background polling loop.

        Requirements: 1.5
        """
        if self._running:
            logger.warning("DeviceMonitor sudah berjalan.")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="device_monitor")
        logger.info("DeviceMonitor dimulai (interval=%.1fs).", self.POLL_INTERVAL_SECONDS)

    async def stop(self) -> None:
        """Hentikan background polling loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("DeviceMonitor dihentikan.")

    async def check_once(self) -> DeviceState:
        """
        Lakukan satu kali poll dan update state. Berguna untuk test dan CLI.

        Returns:
            State perangkat setelah pengecekan.
        """
        await self._do_poll()
        return self._state

    # ------------------------------------------------------------------
    # Internal Poll Loop
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Loop utama yang poll setiap POLL_INTERVAL_SECONDS."""
        while self._running:
            try:
                await self._do_poll()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error tidak terduga di DeviceMonitor poll: %s", exc)
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    async def _do_poll(self) -> None:
        """
        Satu siklus polling: cek ADB devices, update state, emit event jika berubah.
        """
        previous_state = self._state
        previous_device_id = (
            self._current_device.device_id if self._current_device else None
        )

        try:
            self._state = DeviceState.DETECTING
            devices = await asyncio.wait_for(
                self._adb.get_connected_devices(),
                timeout=self.DETECT_TIMEOUT_SECONDS,
            )
        except (asyncio.TimeoutError, ADBTimeoutError) as exc:
            logger.warning("Timeout saat mendeteksi perangkat: %s", exc)
            await self._transition_to_error(str(exc), previous_state, previous_device_id)
            return
        except Exception as exc:  # noqa: BLE001
            logger.error("Error ADB saat polling: %s", exc)
            await self._transition_to_error(str(exc), previous_state, previous_device_id)
            return

        # Filter hanya perangkat yang benar-benar terhubung (state == "device")
        active_devices = [d for d in devices if d.state == "device"]

        if not active_devices:
            await self._handle_no_devices(previous_state, previous_device_id)
            return

        # Gunakan perangkat pertama yang aktif
        device = active_devices[0]

        # Verifikasi LinkedIn (Requirements 1.3)
        try:
            linkedin_ok = await asyncio.wait_for(
                self._adb.is_linkedin_installed(device.device_id),
                timeout=self.DETECT_TIMEOUT_SECONDS,
            )
            device.linkedin_installed = linkedin_ok
        except (asyncio.TimeoutError, ADBTimeoutError):
            device.linkedin_installed = False

        self._current_device = device

        if linkedin_ok:
            self._state = DeviceState.READY
        else:
            self._state = DeviceState.CONNECTED

        # Emit event jika state atau device berubah
        if (
            previous_state in (DeviceState.DISCONNECTED, DeviceState.ERROR, DeviceState.DETECTING)
            or previous_device_id != device.device_id
        ):
            event_type = (
                DeviceEventType.LINKEDIN_READY if linkedin_ok else DeviceEventType.CONNECTED
            )
            await self._emit_event(
                DeviceEvent(
                    event_type=event_type,
                    device_id=device.device_id,
                    state=self._state,
                    message=(
                        f"Perangkat {device.device_id} terhubung"
                        + (" — LinkedIn siap" if linkedin_ok else " — LinkedIn tidak ditemukan")
                    ),
                    extra={
                        "model": device.model,
                        "linux_installed": linkedin_ok,
                    },
                )
            )
        elif previous_state != self._state:
            # State berubah (misal CONNECTED → READY setelah LinkedIn diverifikasi)
            await self._emit_event(
                DeviceEvent(
                    event_type=DeviceEventType.STATUS_UPDATE,
                    device_id=device.device_id,
                    state=self._state,
                    message=f"Status perangkat diperbarui: {self._state.value}",
                )
            )

    async def _handle_no_devices(
        self,
        previous_state: DeviceState,
        previous_device_id: Optional[str],
    ) -> None:
        """Handle kondisi ketika tidak ada perangkat aktif."""
        self._state = DeviceState.DISCONNECTED

        # HP baru saja disconnect (sebelumnya connected/ready/running)
        was_connected = previous_state in (
            DeviceState.CONNECTED,
            DeviceState.READY,
            DeviceState.RUNNING,
        )

        if was_connected:
            logger.warning(
                "HP Android disconnect (device_id=%s, state_sebelumnya=%s).",
                previous_device_id,
                previous_state.value,
            )
            # Hentikan semua running tasks — Requirements 1.2
            await self._invoke_stop_callbacks()

            await self._emit_event(
                DeviceEvent(
                    event_type=DeviceEventType.DISCONNECTED,
                    device_id=previous_device_id,
                    state=DeviceState.DISCONNECTED,
                    message=(
                        f"HP Android terputus"
                        + (f" ({previous_device_id})" if previous_device_id else "")
                    ),
                )
            )

        self._current_device = None

    async def _transition_to_error(
        self,
        error_msg: str,
        previous_state: DeviceState,
        previous_device_id: Optional[str],
    ) -> None:
        """Transisi ke state ERROR."""
        self._state = DeviceState.ERROR

        was_connected = previous_state in (
            DeviceState.CONNECTED,
            DeviceState.READY,
            DeviceState.RUNNING,
        )

        if was_connected:
            # Hentikan running tasks — Requirements 1.2
            await self._invoke_stop_callbacks()

        await self._emit_event(
            DeviceEvent(
                event_type=DeviceEventType.ERROR,
                device_id=previous_device_id,
                state=DeviceState.ERROR,
                message=f"Error ADB: {error_msg}",
                extra={"error": error_msg},
            )
        )

    async def _invoke_stop_callbacks(self) -> None:
        """
        Panggil semua stop callbacks untuk menghentikan running tasks.

        Requirements: 1.2 — HP disconnect saat bot berjalan harus menghentikan task.
        """
        for callback in list(self._stop_callbacks):
            try:
                result = callback()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                logger.error("Error saat memanggil stop callback: %s", exc)

    async def _emit_event(self, event: DeviceEvent) -> None:
        """
        Kirim event ke broadcaster callback jika ada.

        Broadcaster akan diisi oleh WebSocket manager (task 18).
        Saat ini hanya log ke logger.

        Requirements: 1.5
        """
        logger.info(
            "DeviceEvent: type=%s device=%s state=%s message=%s",
            event.event_type.value,
            event.device_id,
            event.state.value,
            event.message,
        )

        if self._broadcaster is None:
            return

        try:
            result = self._broadcaster(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:  # noqa: BLE001
            logger.error("Error pada broadcaster: %s", exc)

    # ------------------------------------------------------------------
    # Context Manager Support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "DeviceMonitor":
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()
