"""
Image Service — Generate Gambar untuk Konten LinkedIn.

Komponen ini menyediakan:
- ``generate_image(prompt, provider)`` — generate gambar menggunakan provider yang dipilih.

Provider yang didukung:
- ``ideogram`` — Ideogram.ai API (https://api.ideogram.ai/generate)
- ``playground`` — Playground.ai (belum diimplementasikan, raise NotImplementedError)

Gambar yang dihasilkan dikembalikan sebagai URL untuk preview di Studio sebelum
pengguna menyetujui untuk posting (Requirements 3.5).

Requirements: 2.5, 3.4, 3.5
"""

from __future__ import annotations

import logging
from typing import TypedDict

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class ImageResult(TypedDict):
    """Hasil generate gambar dari provider."""
    url: str
    provider: str
    prompt: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Ideogram API endpoint
_IDEOGRAM_API_URL = "https://api.ideogram.ai/generate"

# HTTP timeout (seconds)
_REQUEST_TIMEOUT = 60.0


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class ImageGenerationError(Exception):
    """
    Dilempar saat generate gambar gagal.

    Attributes:
        provider: Nama provider yang gagal.
        message:  Pesan error deskriptif.
    """

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_image(prompt: str, provider: str = "ideogram") -> ImageResult:
    """
    Generate gambar berdasarkan ``prompt`` menggunakan ``provider`` yang dipilih.

    Args:
        prompt:   Deskripsi gambar yang ingin dihasilkan.
        provider: Provider image generation — ``'ideogram'`` atau ``'playground'``.
                  Default: ``'ideogram'``.

    Returns:
        Dict ``{"url": str, "provider": str, "prompt": str}`` berisi URL gambar
        yang dapat langsung digunakan untuk preview di Studio.

    Raises:
        ImageGenerationError: Jika generate gambar gagal (API error, auth error, dll.)
        NotImplementedError:  Jika provider ``'playground'`` dipilih (belum diimplementasikan).
        ValueError:           Jika ``provider`` tidak dikenali.

    Requirements: 2.5, 3.4, 3.5
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt tidak boleh kosong.")

    prompt = prompt.strip()

    if provider == "ideogram":
        return await _generate_ideogram(prompt)
    elif provider == "playground":
        raise NotImplementedError(
            "Provider 'playground' belum diimplementasikan. "
            "Gunakan provider 'ideogram' sebagai gantinya."
        )
    else:
        raise ValueError(
            f"Provider '{provider}' tidak dikenali. "
            "Pilihan yang valid: 'ideogram', 'playground'."
        )


# ---------------------------------------------------------------------------
# Ideogram Provider
# ---------------------------------------------------------------------------

async def _generate_ideogram(prompt: str) -> ImageResult:
    """
    Generate gambar via Ideogram.ai API.

    Endpoint: POST https://api.ideogram.ai/generate
    Headers: ``Api-Key: <ideogram_api_key>``
    Body:
    ```json
    {
        "image_request": {
            "prompt": "<prompt>",
            "aspect_ratio": "ASPECT_1_1",
            "model": "V_2",
            "magic_prompt_option": "AUTO"
        }
    }
    ```

    Response berisi ``data[0].url`` sebagai URL gambar yang dihasilkan.

    Args:
        prompt: Deskripsi gambar.

    Returns:
        ``ImageResult`` dengan URL gambar, provider='ideogram', dan prompt.

    Raises:
        ImageGenerationError: Jika API key tidak tersedia, request gagal,
                              atau response tidak mengandung URL gambar.

    Requirements: 2.5, 3.4, 3.5
    """
    settings = get_settings()

    # Validasi API key
    api_key = settings.ideogram_api_key
    if not api_key:
        raise ImageGenerationError(
            "ideogram",
            "IDEOGRAM_API_KEY tidak dikonfigurasi. "
            "Set env var IDEOGRAM_API_KEY untuk menggunakan Ideogram.ai.",
        )

    # Payload sesuai Ideogram API docs
    payload = {
        "image_request": {
            "prompt": prompt,
            "aspect_ratio": "ASPECT_1_1",
            "model": "V_2",
            "magic_prompt_option": "AUTO",
        }
    }

    headers = {
        "Api-Key": api_key,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                _IDEOGRAM_API_URL,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        # Coba ambil pesan error dari response body
        try:
            error_body = exc.response.json()
            error_msg = error_body.get("error", {}).get("message", str(exc))
        except Exception:
            error_msg = str(exc)

        if status_code == 401:
            raise ImageGenerationError(
                "ideogram",
                f"Autentikasi gagal (401): API key tidak valid atau kadaluarsa. {error_msg}",
            ) from exc
        elif status_code == 429:
            raise ImageGenerationError(
                "ideogram",
                f"Rate limit tercapai (429): Terlalu banyak request. {error_msg}",
            ) from exc
        elif status_code == 402:
            raise ImageGenerationError(
                "ideogram",
                f"Kredit Ideogram habis (402): Tambah kredit di dashboard Ideogram. {error_msg}",
            ) from exc
        else:
            raise ImageGenerationError(
                "ideogram",
                f"HTTP {status_code}: {error_msg}",
            ) from exc

    except httpx.TimeoutException as exc:
        raise ImageGenerationError(
            "ideogram",
            f"Request timeout setelah {_REQUEST_TIMEOUT:.0f} detik. Coba lagi.",
        ) from exc

    except httpx.RequestError as exc:
        raise ImageGenerationError(
            "ideogram",
            f"Koneksi gagal: {exc}",
        ) from exc

    # Parse URL gambar dari response
    # Expected format: {"data": [{"url": "https://...", ...}, ...], ...}
    image_data = data.get("data", [])
    if not image_data:
        raise ImageGenerationError(
            "ideogram",
            f"Response tidak mengandung data gambar. Response: {data}",
        )

    image_url = image_data[0].get("url", "").strip()
    if not image_url:
        raise ImageGenerationError(
            "ideogram",
            f"URL gambar tidak ditemukan di response. data[0]: {image_data[0]}",
        )

    logger.info(
        "image_service[ideogram]: gambar berhasil dihasilkan untuk prompt '%s...' → %s",
        prompt[:50],
        image_url,
    )

    return {
        "url": image_url,
        "provider": "ideogram",
        "prompt": prompt,
    }
