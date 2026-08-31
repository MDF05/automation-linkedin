"""
WebSocket Router — Endpoint `/ws` untuk event real-time.

Event types (server → client):
- device_status    — status koneksi HP (polling 5s)
- bot_progress     — langkah-langkah eksekusi bot
- bot_log          — entri log baru
- captcha_detected — CAPTCHA terdeteksi di layar

Requirements: 1.5, 2.10, 9.6
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WS /ws

    Terima koneksi WebSocket dan maintain hingga client disconnect.

    Client dapat mengirim:
    - {"type": "bot:stop_request", "data": {"task_id": "..."}}
    - {"type": "subscribe:device", "data": {}}

    Server mengirim event berdasarkan aktivitas bot dan device monitor.

    Requirements: 1.5, 2.10, 9.6
    """
    await manager.connect(websocket)
    logger.info("WebSocket: client baru terhubung (total=%d)", manager.connection_count)

    # Kirim status awal device saat client connect
    try:
        from app.services.adb_service import ADBService
        svc = ADBService()
        devices = await svc.get_connected_devices()
        connected = bool(devices and devices[0].state == "device")
        device_id = devices[0].device_id if connected else None
        await manager.send_personal(websocket, "device_status", {
            "connected": connected,
            "device_id": device_id,
        })
    except Exception:
        await manager.send_personal(websocket, "device_status", {
            "connected": False,
            "device_id": None,
        })

    try:
        while True:
            # Terima pesan dari client (jika ada) — non-blocking
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                try:
                    msg = json.loads(raw)
                    event_type = msg.get("type", "")
                    data = msg.get("data", {})

                    if event_type == "bot:stop_request":
                        # Handler stop request — akan dikembangkan di task integrasi
                        logger.info("WebSocket: bot stop_request task_id=%s", data.get("task_id"))
                        await manager.send_personal(websocket, "bot:stopped", {
                            "task_id": data.get("task_id"),
                            "reason": "user_requested",
                        })

                    elif event_type == "subscribe:device":
                        # Re-send device status
                        await manager.send_personal(websocket, "device_status", {
                            "connected": False,
                            "device_id": None,
                        })

                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Timeout normal — lanjutkan loop (keep-alive)
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket: client disconnect (total=%d)", manager.connection_count)
    except Exception as exc:
        manager.disconnect(websocket)
        logger.warning("WebSocket: error — %s", exc)
