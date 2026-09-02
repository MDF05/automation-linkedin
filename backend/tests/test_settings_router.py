"""
Unit tests untuk `settings` router — validasi input.

Validates: Requirements 12.2, 12.3

Tests yang dicakup:
- GET /api/settings — mengembalikan semua konfigurasi dengan updated_at
- PUT /api/settings — data valid berhasil disimpan (200)
- PUT /api/settings dengan batas harian negatif → 422 dengan pesan spesifik
- PUT /api/settings dengan delay min > max → 422 dengan pesan spesifik
- PUT /api/settings dengan delay min == max → 422 (min harus strictly less than max)
- PUT /api/settings dengan batas harian nol → 422 (harus bilangan positif)
- PUT /api/settings dengan nilai boundary yang valid → 200

Catatan: Semua tes menggunakan FastAPI TestClient dengan override dependency
`get_db` sehingga tidak memerlukan database PostgreSQL yang berjalan.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import create_app
from app.core.database import get_db


# ---------------------------------------------------------------------------
# Async DB mock
# ---------------------------------------------------------------------------


def make_mock_db_session(settings_rows: List[Any] | None = None) -> AsyncMock:
    """
    Buat mock AsyncSession yang mensimulasikan query ke tabel settings.

    Parameters
    ----------
    settings_rows:
        List of mock Settings ORM row objects. Jika None, kembalikan list kosong
        (skenario database kosong / no settings yet).
    """
    if settings_rows is None:
        settings_rows = []

    mock_session = AsyncMock(spec=AsyncSession)

    # Mock untuk select(Settings) → scalars().all()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = settings_rows

    # Mock untuk fungsi max(updated_at)
    mock_max_result = MagicMock()
    mock_max_result.scalar_one_or_none.return_value = None

    # execute dipanggil dua kali di GET: satu untuk select rows, satu untuk max(updated_at)
    # dan bisa dipanggil beberapa kali di PUT (untuk upsert per key)
    mock_session.execute = AsyncMock(
        side_effect=[mock_result, mock_max_result]
        + [MagicMock(scalar_one_or_none=MagicMock(return_value=None))] * 10
    )
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.add = MagicMock()

    return mock_session


async def _mock_get_db_empty() -> AsyncGenerator[AsyncMock, None]:
    """Dependency override: DB session tanpa rows (database kosong)."""
    yield make_mock_db_session()


# ---------------------------------------------------------------------------
# TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    """
    Buat TestClient dengan dependency get_db di-override oleh mock session kosong.
    """
    app = create_app()
    app.dependency_overrides[get_db] = _mock_get_db_empty
    return TestClient(app, raise_server_exceptions=True)


def _client_with_db(mock_session: AsyncMock) -> TestClient:
    """
    Buat TestClient dengan mock session khusus.
    """
    async def _override() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app = create_app()
    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Helper: ambil detail error 422 dari response JSON
# ---------------------------------------------------------------------------


def get_422_details(response_json: dict) -> list[dict]:
    """Kembalikan list detail validasi error dari response JSON 422."""
    return response_json.get("detail", [])


def error_messages_text(response_json: dict) -> str:
    """
    Kembalikan semua pesan error sebagai satu string untuk assertion mudah.
    """
    details = get_422_details(response_json)
    if isinstance(details, list):
        return " ".join(
            str(d.get("msg", "")) + " " + str(d.get("loc", ""))
            for d in details
        ).lower()
    return str(details).lower()


# ===========================================================================
# 1. GET /api/settings
# ===========================================================================


class TestGetSettings:
    """Test suite untuk GET /api/settings (Requirements 12.5)."""

    def test_get_settings_returns_200(self, client: TestClient) -> None:
        """GET /api/settings harus mengembalikan status 200."""
        response = client.get("/api/settings")
        assert response.status_code == 200

    def test_get_settings_returns_json(self, client: TestClient) -> None:
        """GET /api/settings harus mengembalikan response JSON yang valid."""
        response = client.get("/api/settings")
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert isinstance(data, dict)

    def test_get_settings_contains_required_keys(self, client: TestClient) -> None:
        """
        GET /api/settings harus mengembalikan semua kunci konfigurasi utama.
        Requirements 12.5: tampilkan nilai konfigurasi saat ini.
        """
        response = client.get("/api/settings")
        data = response.json()
        expected_keys = {
            "ai_provider_chain",
            "ai_usage_limits",
            "anti_ban_limits",
            "anti_ban_delays",
            "content_language",
            "screenshot_enabled",
        }
        for key in expected_keys:
            assert key in data, f"Kunci '{key}' tidak ditemukan dalam response settings"

    def test_get_settings_has_updated_at_key(self, client: TestClient) -> None:
        """
        GET /api/settings harus menyertakan field updated_at.
        Requirements 12.5: tampilkan timestamp kapan terakhir diubah.
        """
        response = client.get("/api/settings")
        data = response.json()
        assert "updated_at" in data

    def test_get_settings_anti_ban_limits_has_defaults(self, client: TestClient) -> None:
        """
        Saat database kosong, anti_ban_limits harus mengembalikan nilai default.
        """
        response = client.get("/api/settings")
        data = response.json()
        limits = data["anti_ban_limits"]
        assert isinstance(limits, dict)
        assert limits.get("posts_per_day") == 3
        assert limits.get("comments_per_day") == 15
        assert limits.get("applies_per_day") == 20

    def test_get_settings_anti_ban_delays_has_defaults(self, client: TestClient) -> None:
        """
        Saat database kosong, anti_ban_delays harus mengembalikan nilai default.
        """
        response = client.get("/api/settings")
        data = response.json()
        delays = data["anti_ban_delays"]
        assert isinstance(delays, dict)
        assert delays.get("tap_min_ms") == 1000
        assert delays.get("tap_max_ms") == 3000
        assert delays.get("nav_min_ms") == 2000
        assert delays.get("nav_max_ms") == 5000

    def test_get_settings_default_provider_chain(self, client: TestClient) -> None:
        """
        Saat database kosong, ai_provider_chain harus berisi urutan default.
        """
        response = client.get("/api/settings")
        data = response.json()
        chain = data["ai_provider_chain"]
        assert isinstance(chain, list)
        assert len(chain) > 0


# ===========================================================================
# 2. PUT /api/settings — data VALID
# ===========================================================================


class TestPutSettingsValid:
    """Test suite untuk PUT /api/settings dengan data valid (Requirements 12.2)."""

    def test_put_settings_valid_data_returns_200(self) -> None:
        """
        PUT /api/settings dengan data valid harus mengembalikan status 200.
        Requirements 12.2: backend harus memvalidasi dan menyimpan nilai yang valid.
        """
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": 3,
                    "comments_per_day": 15,
                    "applies_per_day": 20,
                }
            },
        )
        assert response.status_code == 200

    def test_put_settings_returns_status_ok(self) -> None:
        """PUT /api/settings yang berhasil harus mengembalikan status 'ok'."""
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={"content_language": "english"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_put_settings_returns_updated_keys(self) -> None:
        """PUT /api/settings harus mengembalikan daftar kunci yang diperbarui."""
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={
                "content_language": "english",
                "screenshot_enabled": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        updated_keys = data.get("updated_keys", [])
        assert "content_language" in updated_keys
        assert "screenshot_enabled" in updated_keys

    def test_put_settings_valid_anti_ban_delays(self) -> None:
        """
        PUT /api/settings dengan delay min < max yang valid harus berhasil.
        """
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 500,
                    "tap_max_ms": 2000,
                    "nav_min_ms": 1000,
                    "nav_max_ms": 4000,
                }
            },
        )
        assert response.status_code == 200

    def test_put_settings_valid_boundary_posts_per_day_1(self) -> None:
        """
        Nilai batas harian minimum (1) harus valid.
        Requirements 12.2: batas harian harus bilangan positif.
        """
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": 1,
                    "comments_per_day": 1,
                    "applies_per_day": 1,
                }
            },
        )
        assert response.status_code == 200

    def test_put_settings_partial_update_only_changed_fields(self) -> None:
        """
        PUT /api/settings hanya memperbarui field yang dikirim (partial update).
        """
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={"screenshot_enabled": True},
        )
        assert response.status_code == 200

    def test_put_settings_valid_provider_chain(self) -> None:
        """PUT /api/settings dengan daftar provider AI valid harus berhasil."""
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={"ai_provider_chain": ["deepseek", "groq"]},
        )
        assert response.status_code == 200

    def test_put_settings_valid_tap_delay_large_values(self) -> None:
        """
        Nilai delay yang besar tetapi valid (min < max) harus diterima.
        """
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 1000,
                    "tap_max_ms": 10000,
                    "nav_min_ms": 2000,
                    "nav_max_ms": 15000,
                }
            },
        )
        assert response.status_code == 200


# ===========================================================================
# 3. PUT /api/settings — batas harian NEGATIF (Requirements 12.2, 12.3)
# ===========================================================================


class TestPutSettingsNegativeDailyLimits:
    """
    Test suite: batas harian negatif harus ditolak dengan 422.
    Requirements 12.2: validasi nilai sebelum simpan.
    Requirements 12.3: pesan error spesifik menyebut field yang tidak valid.
    """

    def test_negative_posts_per_day_returns_422(self, client: TestClient) -> None:
        """
        posts_per_day negatif → 422.
        Requirements 12.3: error harus menyebut field yang tidak valid.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": -1,
                    "comments_per_day": 15,
                    "applies_per_day": 20,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        error_text = error_messages_text(body)
        # Pesan harus menyebut field yang tidak valid
        assert "posts_per_day" in error_text or "anti_ban_limits" in error_text, (
            f"Pesan error harus menyebut field yang tidak valid. Actual: {body}"
        )

    def test_negative_comments_per_day_returns_422(self, client: TestClient) -> None:
        """comments_per_day negatif → 422 dengan field yang spesifik."""
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": 3,
                    "comments_per_day": -5,
                    "applies_per_day": 20,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        error_text = error_messages_text(body)
        assert "comments_per_day" in error_text or "anti_ban_limits" in error_text, (
            f"Pesan error harus menyebut field yang tidak valid. Actual: {body}"
        )

    def test_negative_applies_per_day_returns_422(self, client: TestClient) -> None:
        """applies_per_day negatif → 422 dengan field yang spesifik."""
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": 3,
                    "comments_per_day": 15,
                    "applies_per_day": -10,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        error_text = error_messages_text(body)
        assert "applies_per_day" in error_text or "anti_ban_limits" in error_text, (
            f"Pesan error harus menyebut field yang tidak valid. Actual: {body}"
        )

    def test_zero_posts_per_day_returns_422(self, client: TestClient) -> None:
        """
        posts_per_day = 0 → 422 (harus bilangan positif, minimum 1).
        Requirements 12.2: batas harian harus bilangan positif.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": 0,
                    "comments_per_day": 15,
                    "applies_per_day": 20,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        error_text = error_messages_text(body)
        assert "posts_per_day" in error_text or "anti_ban_limits" in error_text, (
            f"Nilai 0 untuk posts_per_day harus ditolak. Actual: {body}"
        )

    def test_zero_comments_per_day_returns_422(self, client: TestClient) -> None:
        """comments_per_day = 0 → 422 (harus bilangan positif)."""
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": 3,
                    "comments_per_day": 0,
                    "applies_per_day": 20,
                }
            },
        )
        assert response.status_code == 422

    def test_zero_applies_per_day_returns_422(self, client: TestClient) -> None:
        """applies_per_day = 0 → 422 (harus bilangan positif)."""
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": 3,
                    "comments_per_day": 15,
                    "applies_per_day": 0,
                }
            },
        )
        assert response.status_code == 422

    def test_all_negative_limits_returns_422(self, client: TestClient) -> None:
        """Semua field negatif sekaligus → 422."""
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": -3,
                    "comments_per_day": -15,
                    "applies_per_day": -20,
                }
            },
        )
        assert response.status_code == 422

    def test_422_response_has_detail_field(self, client: TestClient) -> None:
        """
        Response 422 harus memiliki field 'detail' sesuai format FastAPI/Pydantic.
        Requirements 12.3: pesan error yang spesifik.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": -1,
                    "comments_per_day": 15,
                    "applies_per_day": 20,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        assert "detail" in body, (
            f"Response 422 harus memiliki field 'detail'. Actual: {body}"
        )

    def test_422_detail_mentions_field_name_for_negative_limit(
        self, client: TestClient
    ) -> None:
        """
        Detail error 422 harus menyebut nama field yang tidak valid.
        Requirements 12.3: pesan error spesifik menyebutkan field mana yang tidak valid.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": -99,
                    "comments_per_day": 15,
                    "applies_per_day": 20,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        # Detail harus berupa list (Pydantic format) atau string yang mengandung info field
        detail = body.get("detail")
        assert detail is not None, "Field 'detail' tidak boleh kosong"

        if isinstance(detail, list):
            # Format Pydantic: [{"loc": [..., "field_name"], "msg": "...", "type": "..."}]
            locs = [str(item.get("loc", "")) for item in detail]
            all_locs_text = " ".join(locs).lower()
            # Harus menyebut path ke field yang bermasalah
            assert (
                "posts_per_day" in all_locs_text
                or "anti_ban_limits" in all_locs_text
            ), (
                f"'loc' dalam detail harus menyebut field yang tidak valid. "
                f"Actual locs: {locs}"
            )


# ===========================================================================
# 4. PUT /api/settings — delay min >= max (Requirements 12.2, 12.3)
# ===========================================================================


class TestPutSettingsDelayMinMaxValidation:
    """
    Test suite: delay min >= max harus ditolak dengan 422 dan pesan spesifik.
    Requirements 12.2: range delay harus min < max.
    Requirements 12.3: pesan error spesifik.
    """

    def test_tap_min_greater_than_tap_max_returns_422(
        self, client: TestClient
    ) -> None:
        """
        tap_min_ms > tap_max_ms → 422.
        Requirements 12.2: delay range harus min < max.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 5000,  # > tap_max_ms
                    "tap_max_ms": 1000,
                    "nav_min_ms": 2000,
                    "nav_max_ms": 5000,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        error_text = error_messages_text(body)
        # Harus menyebut field tap_min_ms atau tap_max_ms
        assert (
            "tap_min_ms" in error_text
            or "tap_max_ms" in error_text
            or "anti_ban_delays" in error_text
        ), (
            f"Pesan error harus menyebut delay field yang tidak valid. Actual: {body}"
        )

    def test_nav_min_greater_than_nav_max_returns_422(
        self, client: TestClient
    ) -> None:
        """
        nav_min_ms > nav_max_ms → 422.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 1000,
                    "tap_max_ms": 3000,
                    "nav_min_ms": 8000,  # > nav_max_ms
                    "nav_max_ms": 5000,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        error_text = error_messages_text(body)
        assert (
            "nav_min_ms" in error_text
            or "nav_max_ms" in error_text
            or "anti_ban_delays" in error_text
        ), (
            f"Pesan error harus menyebut delay field yang tidak valid. Actual: {body}"
        )

    def test_tap_min_equal_to_tap_max_returns_422(
        self, client: TestClient
    ) -> None:
        """
        tap_min_ms == tap_max_ms → 422.
        AntiBanDelays memerlukan strictly min < max (menggunakan >= dalam validasi).
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 1000,
                    "tap_max_ms": 1000,  # sama dengan min
                    "nav_min_ms": 2000,
                    "nav_max_ms": 5000,
                }
            },
        )
        assert response.status_code == 422

    def test_nav_min_equal_to_nav_max_returns_422(
        self, client: TestClient
    ) -> None:
        """nav_min_ms == nav_max_ms → 422 (min harus strictly < max)."""
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 1000,
                    "tap_max_ms": 3000,
                    "nav_min_ms": 2000,
                    "nav_max_ms": 2000,  # sama dengan min
                }
            },
        )
        assert response.status_code == 422

    def test_both_tap_and_nav_invalid_returns_422(self, client: TestClient) -> None:
        """Kedua pasangan (tap dan nav) min > max → 422."""
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 5000,
                    "tap_max_ms": 100,
                    "nav_min_ms": 9000,
                    "nav_max_ms": 1000,
                }
            },
        )
        assert response.status_code == 422

    def test_delay_422_error_mentions_specific_field(self, client: TestClient) -> None:
        """
        Response 422 untuk delay invalid harus memiliki detail yang spesifik.
        Requirements 12.3: pesan error spesifik.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 3000,
                    "tap_max_ms": 1000,  # tap_min > tap_max
                    "nav_min_ms": 2000,
                    "nav_max_ms": 5000,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        assert "detail" in body, (
            f"Response 422 harus memiliki field 'detail'. Actual: {body}"
        )
        detail = body["detail"]
        assert detail is not None and detail != [], (
            f"Field 'detail' tidak boleh kosong untuk error validasi. Actual: {body}"
        )

    def test_delay_error_message_mentions_tap_field(self, client: TestClient) -> None:
        """
        Pesan error untuk tap_min_ms > tap_max_ms harus menyebut nama field
        tap_min_ms atau tap_max_ms.
        Requirements 12.3: pesan error menyebutkan field mana yang tidak valid.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 9999,
                    "tap_max_ms": 100,
                    "nav_min_ms": 2000,
                    "nav_max_ms": 5000,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        detail = body.get("detail", [])
        # Untuk Pydantic model_validator errors, loc biasanya berisi nama model
        detail_str = str(detail).lower()
        assert (
            "tap_min_ms" in detail_str
            or "tap_max_ms" in detail_str
            or "anti_ban_delays" in detail_str
        ), (
            f"Detail error harus menyebut field tap yang tidak valid. "
            f"Actual detail: {detail}"
        )

    def test_delay_error_message_mentions_nav_field(self, client: TestClient) -> None:
        """
        Pesan error untuk nav_min_ms > nav_max_ms harus menyebut nama field
        nav_min_ms atau nav_max_ms.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 1000,
                    "tap_max_ms": 3000,
                    "nav_min_ms": 9999,
                    "nav_max_ms": 1000,
                }
            },
        )
        assert response.status_code == 422
        body = response.json()
        detail = body.get("detail", [])
        detail_str = str(detail).lower()
        assert (
            "nav_min_ms" in detail_str
            or "nav_max_ms" in detail_str
            or "anti_ban_delays" in detail_str
        ), (
            f"Detail error harus menyebut field nav yang tidak valid. "
            f"Actual detail: {detail}"
        )


# ===========================================================================
# 5. PUT /api/settings — nilai boundary yang valid
# ===========================================================================


class TestPutSettingsBoundaryValues:
    """
    Test suite: nilai boundary yang valid harus diterima (200).
    """

    def test_minimum_positive_limit_1_accepted(self) -> None:
        """
        Nilai minimum yang valid untuk batas harian adalah 1 (ge=1).
        Req 12.2: batas harian harus bilangan positif.
        """
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": 1,
                    "comments_per_day": 1,
                    "applies_per_day": 1,
                }
            },
        )
        assert response.status_code == 200

    def test_large_positive_limit_accepted(self) -> None:
        """Nilai batas harian besar tetap valid."""
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": 100,
                    "comments_per_day": 200,
                    "applies_per_day": 500,
                }
            },
        )
        assert response.status_code == 200

    def test_delay_where_tap_min_is_one_less_than_max_accepted(self) -> None:
        """
        Delay dengan selisih minimal (min + 1 = max) harus valid.
        Req 12.2: delay range harus min < max.
        """
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 100,
                    "tap_max_ms": 101,  # min + 1 = max: valid
                    "nav_min_ms": 200,
                    "nav_max_ms": 201,  # min + 1 = max: valid
                }
            },
        )
        assert response.status_code == 200

    def test_empty_body_returns_200_no_updates(self) -> None:
        """
        Body JSON kosong {} harus valid (tidak ada field yang diperbarui).
        """
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put("/api/settings", json={})
        assert response.status_code == 200

    def test_cv_path_string_accepted(self) -> None:
        """cv_path sebagai string valid harus diterima."""
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={"cv_path": "/home/user/cv.pdf"},
        )
        assert response.status_code == 200

    def test_screenshot_enabled_false_accepted(self) -> None:
        """screenshot_enabled = False adalah nilai boolean yang valid."""
        mock_session = make_mock_db_session()
        client = _client_with_db(mock_session)

        response = client.put(
            "/api/settings",
            json={"screenshot_enabled": False},
        )
        assert response.status_code == 200


# ===========================================================================
# 6. PUT /api/settings — kombinasi data valid dan tidak valid
# ===========================================================================


class TestPutSettingsMixedValidation:
    """
    Test suite: kombinasi beberapa field valid dan tidak valid.
    """

    def test_valid_delays_but_invalid_limits_returns_422(
        self, client: TestClient
    ) -> None:
        """
        anti_ban_delays valid tetapi anti_ban_limits negatif → 422.
        Pydantic harus menolak seluruh request karena ada field tidak valid.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 1000,
                    "tap_max_ms": 3000,
                    "nav_min_ms": 2000,
                    "nav_max_ms": 5000,
                },
                "anti_ban_limits": {
                    "posts_per_day": -1,  # tidak valid
                    "comments_per_day": 15,
                    "applies_per_day": 20,
                },
            },
        )
        assert response.status_code == 422

    def test_invalid_delays_but_valid_limits_returns_422(
        self, client: TestClient
    ) -> None:
        """
        anti_ban_limits valid tetapi anti_ban_delays min > max → 422.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 5000,  # > tap_max_ms
                    "tap_max_ms": 1000,
                    "nav_min_ms": 2000,
                    "nav_max_ms": 5000,
                },
                "anti_ban_limits": {
                    "posts_per_day": 3,
                    "comments_per_day": 15,
                    "applies_per_day": 20,
                },
            },
        )
        assert response.status_code == 422

    def test_422_response_format_is_valid_json(self, client: TestClient) -> None:
        """Response 422 harus berupa JSON yang dapat di-parse dengan benar."""
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_limits": {
                    "posts_per_day": -1,
                    "comments_per_day": 15,
                    "applies_per_day": 20,
                }
            },
        )
        assert response.status_code == 422
        # Tidak boleh raise exception saat parse JSON
        body = response.json()
        assert isinstance(body, dict)


# ===========================================================================
# 7. Edge cases — tap_min_ms below minimum (ge=100)
# ===========================================================================


class TestPutSettingsDelayMinimumMs:
    """
    Test suite: nilai delay di bawah batas minimum absolut (ge=100).
    """

    def test_tap_min_ms_below_100_returns_422(self, client: TestClient) -> None:
        """
        tap_min_ms < 100 → 422 karena field memiliki constraint ge=100.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 50,   # < 100: tidak valid
                    "tap_max_ms": 3000,
                    "nav_min_ms": 2000,
                    "nav_max_ms": 5000,
                }
            },
        )
        assert response.status_code == 422

    def test_nav_max_ms_below_100_returns_422(self, client: TestClient) -> None:
        """
        Nilai delay yang sangat kecil (< 100ms) tidak valid untuk semua delay field.
        """
        response = client.put(
            "/api/settings",
            json={
                "anti_ban_delays": {
                    "tap_min_ms": 100,
                    "tap_max_ms": 200,
                    "nav_min_ms": 100,
                    "nav_max_ms": 50,  # < 100: tidak valid
                }
            },
        )
        assert response.status_code == 422
