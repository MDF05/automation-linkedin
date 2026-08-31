"""
Device Router — API endpoints untuk manajemen koneksi HP Android.

Requirements: 1.1, 1.5
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.services.adb_service import ADBService, ADBTimeoutError

router = APIRouter(prefix="/device", tags=["device"])


@router.get("/status")
async def get_device_status() -> Dict[str, Any]:
    """
    GET /api/device/status

    Return status koneksi HP dan info perangkat yang terhubung.

    Requirements: 1.1, 1.5
    """
    try:
        svc = ADBService()
        devices = await svc.get_connected_devices()

        if not devices:
            return {
                "connected": False,
                "device_id": None,
                "model": None,
                "android_version": None,
                "linkedin_installed": False,
                "devices": [],
            }

        device = devices[0]
        linkedin_ok = False
        android_ver = None
        model = device.model

        if device.state == "device":
            target_svc = ADBService(device_id=device.device_id)
            linkedin_ok = await target_svc.is_linkedin_installed()
            android_ver = await target_svc.get_android_version()
            if not model:
                model = await target_svc.get_device_model()

        return {
            "connected": device.state == "device",
            "device_id": device.device_id,
            "model": model,
            "android_version": android_ver,
            "linkedin_installed": linkedin_ok,
            "devices": [
                {"device_id": d.device_id, "state": d.state, "model": d.model}
                for d in devices
            ],
        }

    except ADBTimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"ADB timeout: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/screenshot")
async def take_screenshot() -> Dict[str, Any]:
    """
    POST /api/device/screenshot

    Ambil screenshot manual dari layar HP yang terhubung.

    Requirements: 1.6
    """
    try:
        svc = ADBService()
        devices = await svc.get_connected_devices()

        if not devices or devices[0].state != "device":
            raise HTTPException(status_code=503, detail="HP tidak terhubung")

        target_svc = ADBService(device_id=devices[0].device_id)
        path = await target_svc.take_screenshot()

        return {"screenshot_path": path, "device_id": devices[0].device_id}

    except HTTPException:
        raise
    except ADBTimeoutError as exc:
        raise HTTPException(status_code=504, detail=f"ADB timeout: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
