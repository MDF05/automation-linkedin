"""
WebSocket Connection Manager — Kelola koneksi WebSocket dari multiple clients.

Komponen ini:
- Maintain set koneksi WebSocket yang aktif
- broadcast(event_type, data) — kirim event ke semua client
- send_personal(websocket, event_type, data) — kirim ke satu client

Requirements: 1.5, 2.10
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manager koneksi WebSocket untuk broadcast event real-time.

    Thread-safe untuk asyncio single-thread. Koneksi yang terputus
    secara otomatis dihapus saat broadcast/send gagal.

    Requirements: 1.5, 2.10
    """

    def __init__(self) -> None:
        self._active: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """
        Terima dan daftarkan koneksi WebSocket baru.

        Args:
            websocket: Koneksi WebSocket dari client.
        """
        await websocket.accept()
        self._active.add(websocket)
        logger.info(
            "WebSocket: client terhubung (total=%d)", len(self._active)
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """
        Hapus koneksi WebSocket yang terputus.

        Args:
            websocket: Koneksi yang akan dihapus.
        """
        self._active.discard(websocket)
        logger.info(
            "WebSocket: client terputus (total=%d)", len(self._active)
        )

    async def broadcast(self, event_type: str, data: Any) -> None:
        """
        Kirim event ke semua client yang terhubung.

        Koneksi yang gagal diterima (client disconnect) otomatis dihapus.

        Args:
            event_type: Tipe event, misal 'device_status', 'bot_progress', 'bot_log'.
            data:       Payload event (dict atau primitive yang JSON-serializable).

        Requirements: 1.5, 2.10
        """
        if not self._active:
            return

        message = json.dumps({"type": event_type, "data": data})
        dead: List[WebSocket] = []

        for ws in list(self._active):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

    async def send_personal(
        self,
        websocket: WebSocket,
        event_type: str,
        data: Any,
    ) -> None:
        """
        Kirim event ke satu client tertentu.

        Args:
            websocket:  Target client.
            event_type: Tipe event.
            data:       Payload event.

        Requirements: 1.5
        """
        message = json.dumps({"type": event_type, "data": data})
        try:
            await websocket.send_text(message)
        except Exception as exc:
            logger.warning("WebSocket send_personal gagal: %s", exc)
            self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        """Jumlah koneksi aktif."""
        return len(self._active)


# Singleton instance — digunakan di seluruh aplikasi
manager = ConnectionManager()
