"""
Custom FastAPI exception handlers.

Handler ini memastikan exception domain-specific dari services dikembalikan
sebagai respons JSON yang konsisten dengan format ``{"detail": ..., "field": null}``.

Requirements: 1.4, 8.4, 12.3
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


async def adb_timeout_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler untuk ``ADBTimeoutError``.

    Mengembalikan HTTP 503 dengan body JSON yang konsisten.
    Requirements: 1.4
    """
    return JSONResponse(
        status_code=503,
        content={"detail": "ADB timeout", "field": None},
    )


async def all_providers_exhausted_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler untuk ``AllProvidersExhaustedError``.

    Mengembalikan HTTP 503 dengan body JSON yang konsisten.
    Requirements: 8.4
    """
    return JSONResponse(
        status_code=503,
        content={"detail": "All AI providers exhausted", "field": None},
    )


async def ocr_insufficient_text_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler untuk ``OCRInsufficientTextError``.

    Mengembalikan HTTP 422 dengan body JSON yang konsisten.
    Requirements: 12.3
    """
    return JSONResponse(
        status_code=422,
        content={"detail": "OCR insufficient text", "field": None},
    )


def register_exception_handlers(app: object) -> None:
    """
    Daftarkan semua custom exception handler ke instance FastAPI.

    Penggunaan::

        from app.core.exceptions import register_exception_handlers
        register_exception_handlers(app)

    Args:
        app: Instance ``FastAPI`` tempat handler didaftarkan.
    """
    from app.services.adb_service import ADBTimeoutError
    from app.services.ai_service import AllProvidersExhaustedError
    from app.services.ocr_service import OCRInsufficientTextError

    app.add_exception_handler(ADBTimeoutError, adb_timeout_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AllProvidersExhaustedError, all_providers_exhausted_handler)  # type: ignore[arg-type]
    app.add_exception_handler(OCRInsufficientTextError, ocr_insufficient_text_handler)  # type: ignore[arg-type]
