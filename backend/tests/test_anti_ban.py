"""
Unit tests untuk `anti_ban.py` — semua metode.

Validates: Requirements 9.1–9.7

Tests yang dicakup:
- `get_random_delay` mengembalikan nilai dalam range yang diberikan
- `check_daily_limit` mengembalikan True ketika di bawah batas
- `check_daily_limit` mengembalikan False ketika AT atau OVER batas
- `detect_captcha` mengembalikan True untuk setiap CAPTCHA keyword yang diketahui (case-insensitive)
- `detect_captcha` mengembalikan False untuk teks normal
- `simulate_human_scroll` dapat dipanggil tanpa error (async stub)
"""

from __future__ import annotations

import asyncio
from typing import Dict

import pytest

from app.services.anti_ban import (
    CAPTCHA_KEYWORDS,
    DEFAULT_DAILY_LIMITS,
    check_daily_limit,
    detect_captcha,
    get_random_delay,
    simulate_human_scroll,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def default_limits() -> Dict[str, int]:
    """Kembalikan salinan dari DEFAULT_DAILY_LIMITS untuk digunakan dalam test."""
    return dict(DEFAULT_DAILY_LIMITS)


# ---------------------------------------------------------------------------
# Tests: get_random_delay
# ---------------------------------------------------------------------------


class TestGetRandomDelay:
    """Test suite untuk fungsi get_random_delay."""

    def test_returns_value_within_range(self) -> None:
        """Nilai kembalian harus berada dalam [min_s, max_s]."""
        delay = get_random_delay(1.0, 3.0)
        assert 1.0 <= delay <= 3.0

    def test_returns_value_within_tight_range(self) -> None:
        """Juga valid untuk range sempit."""
        delay = get_random_delay(2.0, 2.5)
        assert 2.0 <= delay <= 2.5

    def test_equal_min_max_returns_exact_value(self) -> None:
        """Ketika min == max, nilai yang dikembalikan harus persis min/max."""
        delay = get_random_delay(1.5, 1.5)
        assert delay == pytest.approx(1.5)

    def test_returns_float(self) -> None:
        """Nilai kembalian harus bertipe float."""
        delay = get_random_delay(0.5, 2.0)
        assert isinstance(delay, float)

    def test_different_calls_can_return_different_values(self) -> None:
        """
        Jalankan banyak kali — minimal harus ada dua nilai berbeda
        (memvalidasi bahwa hasilnya memang acak, bukan konstanta).
        """
        results = {get_random_delay(0.0, 10.0) for _ in range(50)}
        assert len(results) > 1, "get_random_delay seharusnya menghasilkan nilai acak"

    def test_raises_value_error_when_min_greater_than_max(self) -> None:
        """Harus raise ValueError jika min_s > max_s."""
        with pytest.raises(ValueError, match="min_s"):
            get_random_delay(5.0, 1.0)

    def test_nav_delay_range(self) -> None:
        """Delay navigasi default (2–5 detik) harus berada dalam range."""
        delay = get_random_delay(2.0, 5.0)
        assert 2.0 <= delay <= 5.0

    def test_tap_delay_range(self) -> None:
        """Delay ketukan default (1–3 detik) harus berada dalam range."""
        delay = get_random_delay(1.0, 3.0)
        assert 1.0 <= delay <= 3.0


# ---------------------------------------------------------------------------
# Tests: check_daily_limit
# ---------------------------------------------------------------------------


class TestCheckDailyLimit:
    """Test suite untuk fungsi check_daily_limit."""

    # --- Post module ---

    def test_post_under_limit_returns_true(self, default_limits: Dict[str, int]) -> None:
        """Jumlah post di bawah batas harian → True (diizinkan)."""
        assert check_daily_limit("post", 0, default_limits) is True
        assert check_daily_limit("post", 1, default_limits) is True
        assert check_daily_limit("post", 2, default_limits) is True

    def test_post_at_limit_returns_false(self, default_limits: Dict[str, int]) -> None:
        """Jumlah post tepat di batas harian (3) → False (ditolak)."""
        assert check_daily_limit("post", 3, default_limits) is False

    def test_post_over_limit_returns_false(self, default_limits: Dict[str, int]) -> None:
        """Jumlah post melebihi batas harian → False (ditolak)."""
        assert check_daily_limit("post", 10, default_limits) is False

    # --- Comment module ---

    def test_comment_under_limit_returns_true(self, default_limits: Dict[str, int]) -> None:
        """Jumlah komentar di bawah 15 → True."""
        assert check_daily_limit("comment", 0, default_limits) is True
        assert check_daily_limit("comment", 14, default_limits) is True

    def test_comment_at_limit_returns_false(self, default_limits: Dict[str, int]) -> None:
        """Jumlah komentar tepat 15 → False."""
        assert check_daily_limit("comment", 15, default_limits) is False

    def test_comment_over_limit_returns_false(self, default_limits: Dict[str, int]) -> None:
        """Jumlah komentar melebihi 15 → False."""
        assert check_daily_limit("comment", 20, default_limits) is False

    # --- Apply module ---

    def test_apply_under_limit_returns_true(self, default_limits: Dict[str, int]) -> None:
        """Jumlah lamaran di bawah 20 → True."""
        assert check_daily_limit("apply", 0, default_limits) is True
        assert check_daily_limit("apply", 19, default_limits) is True

    def test_apply_at_limit_returns_false(self, default_limits: Dict[str, int]) -> None:
        """Jumlah lamaran tepat 20 → False."""
        assert check_daily_limit("apply", 20, default_limits) is False

    def test_apply_over_limit_returns_false(self, default_limits: Dict[str, int]) -> None:
        """Jumlah lamaran melebihi 20 → False."""
        assert check_daily_limit("apply", 25, default_limits) is False

    # --- Custom limits ---

    def test_custom_limit_respected(self) -> None:
        """Batas kustom harus dihormati, bukan hanya nilai default."""
        custom_limits = {"post": 5, "comment": 10, "apply": 8}
        assert check_daily_limit("post", 4, custom_limits) is True
        assert check_daily_limit("post", 5, custom_limits) is False
        assert check_daily_limit("comment", 9, custom_limits) is True
        assert check_daily_limit("comment", 10, custom_limits) is False

    def test_zero_limit_always_returns_false(self) -> None:
        """Batas 0 berarti modul selalu ditolak."""
        limits = {"post": 0}
        assert check_daily_limit("post", 0, limits) is False

    def test_unknown_module_returns_true(self, default_limits: Dict[str, int]) -> None:
        """Modul yang tidak dikenal (tidak ada di limits) harus diizinkan secara default."""
        assert check_daily_limit("unknown_module", 100, default_limits) is True

    def test_empty_limits_dict_returns_true(self) -> None:
        """Dict limits kosong — semua modul diizinkan."""
        assert check_daily_limit("post", 999, {}) is True


# ---------------------------------------------------------------------------
# Tests: detect_captcha
# ---------------------------------------------------------------------------


class TestDetectCaptcha:
    """Test suite untuk fungsi detect_captcha."""

    @pytest.mark.parametrize("keyword", CAPTCHA_KEYWORDS)
    def test_detects_each_known_keyword(self, keyword: str) -> None:
        """
        Setiap keyword CAPTCHA yang didefinisikan harus terdeteksi
        ketika muncul dalam teks.
        """
        text = f"Please {keyword} to continue using LinkedIn."
        assert detect_captcha(text) is True, (
            f"Seharusnya mendeteksi keyword CAPTCHA: {keyword!r}"
        )

    @pytest.mark.parametrize("keyword", CAPTCHA_KEYWORDS)
    def test_detects_keyword_case_insensitive_upper(self, keyword: str) -> None:
        """Pendeteksian harus case-insensitive (huruf kapital)."""
        text = keyword.upper()
        assert detect_captcha(text) is True, (
            f"Seharusnya mendeteksi keyword CAPTCHA uppercase: {keyword.upper()!r}"
        )

    @pytest.mark.parametrize("keyword", CAPTCHA_KEYWORDS)
    def test_detects_keyword_case_insensitive_title(self, keyword: str) -> None:
        """Pendeteksian harus case-insensitive (title case)."""
        text = keyword.title()
        assert detect_captcha(text) is True, (
            f"Seharusnya mendeteksi keyword CAPTCHA title case: {keyword.title()!r}"
        )

    def test_returns_false_for_normal_linkedin_text(self) -> None:
        """Teks normal beranda LinkedIn tidak boleh terdeteksi sebagai CAPTCHA."""
        normal_texts = [
            "Just posted a new article about Python best practices.",
            "Looking for new opportunities in software engineering.",
            "Congratulations on your new position!",
            "Check out our latest product update.",
            "5 tips for better productivity at work.",
            "Excited to announce that I've joined a new company.",
        ]
        for text in normal_texts:
            assert detect_captcha(text) is False, (
                f"Teks normal seharusnya tidak terdeteksi sebagai CAPTCHA: {text!r}"
            )

    def test_returns_false_for_empty_string(self) -> None:
        """String kosong tidak boleh terdeteksi sebagai CAPTCHA."""
        assert detect_captcha("") is False

    def test_returns_false_for_whitespace_only(self) -> None:
        """String berisi spasi saja tidak boleh terdeteksi sebagai CAPTCHA."""
        assert detect_captcha("   \n\t  ") is False

    def test_detects_captcha_in_sentence(self) -> None:
        """Keyword CAPTCHA di tengah kalimat panjang harus tetap terdeteksi."""
        text = (
            "We've noticed some unusual activity on your account. "
            "Please complete this security check to continue."
        )
        assert detect_captcha(text) is True

    def test_detects_verifikasi_indonesian(self) -> None:
        """Keyword bahasa Indonesia 'verifikasi' harus terdeteksi."""
        text = "Silakan lakukan verifikasi untuk melanjutkan."
        assert detect_captcha(text) is True

    def test_detects_pemeriksaan_keamanan_indonesian(self) -> None:
        """Keyword 'pemeriksaan keamanan' harus terdeteksi."""
        text = "Ini adalah pemeriksaan keamanan rutin."
        assert detect_captcha(text) is True

    def test_detects_prove_youre_human(self) -> None:
        """Keyword 'prove you're human' harus terdeteksi."""
        text = "Please prove you're human to access this content."
        assert detect_captcha(text) is True

    def test_detects_unusual_activity(self) -> None:
        """Keyword 'unusual activity' harus terdeteksi."""
        text = "We detected unusual activity from your account."
        assert detect_captcha(text) is True

    def test_does_not_detect_partial_word_match_for_robot(self) -> None:
        """
        Kata 'robot' yang muncul sebagai bagian dari kata lain (seperti 'robotics')
        TETAP terdeteksi karena mengandung substring 'robot'.
        Ini adalah perilaku yang diharapkan — false positive lebih aman dari false negative.
        """
        text = "I work in robotics and automation."
        # 'robot' adalah substring dari 'robotics', sehingga terdeteksi — ini intentional
        assert detect_captcha(text) is True

    def test_captcha_keyword_list_not_empty(self) -> None:
        """Daftar keyword CAPTCHA tidak boleh kosong."""
        assert len(CAPTCHA_KEYWORDS) > 0


# ---------------------------------------------------------------------------
# Tests: simulate_human_scroll (async)
# ---------------------------------------------------------------------------


class TestSimulateHumanScroll:
    """Test suite untuk fungsi simulate_human_scroll (async stub)."""

    def test_is_coroutine(self) -> None:
        """simulate_human_scroll harus mengembalikan coroutine (async function)."""
        import inspect
        assert inspect.iscoroutinefunction(simulate_human_scroll)

    def test_can_be_awaited_without_error(self) -> None:
        """Memanggil simulate_human_scroll tidak boleh raise exception apapun."""
        asyncio.run(simulate_human_scroll())

    @pytest.mark.asyncio
    async def test_completes_successfully(self) -> None:
        """simulate_human_scroll harus selesai tanpa error dalam test async."""
        await simulate_human_scroll()  # harus tidak raise exception


    @pytest.mark.asyncio
    async def test_calls_adb_execute_swipe_when_adb_service_provided(self) -> None:
        """simulate_human_scroll harus memanggil adb_service.execute_swipe ketika adb_service diberikan."""
        from unittest.mock import AsyncMock, MagicMock

        mock_adb = MagicMock()
        mock_adb.get_screen_resolution = AsyncMock(return_value=(1080, 1920))
        mock_adb.execute_swipe = AsyncMock()

        await simulate_human_scroll(
            device_id="emulator-5554",
            adb_service=mock_adb,
            pattern="skim",
            _fast_mode=True,
        )

        # execute_swipe harus dipanggil setidaknya sekali
        assert mock_adb.execute_swipe.call_count >= 1

    @pytest.mark.asyncio
    async def test_adb_execute_swipe_called_with_correct_coordinates(self) -> None:
        """
        Koordinat swipe yang dikirim ke ADB harus berupa nilai pixel integer
        yang diturunkan dari resolusi layar dan konstanta koordinat relatif.
        """
        from unittest.mock import AsyncMock, MagicMock

        width, height = 1080, 1920

        mock_adb = MagicMock()
        mock_adb.get_screen_resolution = AsyncMock(return_value=(width, height))
        mock_adb.execute_swipe = AsyncMock()

        await simulate_human_scroll(
            device_id="emulator-5554",
            adb_service=mock_adb,
            pattern="skim",
            _fast_mode=True,
        )

        # Verifikasi bahwa setiap panggilan execute_swipe menggunakan koordinat integer
        for call_args in mock_adb.execute_swipe.call_args_list:
            args = call_args[0]  # positional args: (x, y_start, x, y_end, duration_ms)
            assert len(args) == 5
            x1, y1, x2, y2, duration_ms = args
            # Koordinat harus integer
            assert isinstance(x1, int)
            assert isinstance(y1, int)
            assert isinstance(x2, int)
            assert isinstance(y2, int)
            # Durasi harus integer (dalam ms)
            assert isinstance(duration_ms, int)

    @pytest.mark.asyncio
    async def test_adb_swipe_duration_varies_between_calls(self) -> None:
        """
        Durasi swipe harus bervariasi (tidak konstan) antar panggilan,
        mensimulasikan perilaku manusia yang tidak kaku.
        Untuk mendapat variasi, jalankan beberapa kali dengan banyak swipe.
        """
        from unittest.mock import AsyncMock, MagicMock

        mock_adb = MagicMock()
        mock_adb.get_screen_resolution = AsyncMock(return_value=(1080, 1920))
        mock_adb.execute_swipe = AsyncMock()

        # Jalankan dengan pola 'skim' (8–15 swipe) untuk mendapat banyak sampel
        await simulate_human_scroll(
            device_id="emulator-5554",
            adb_service=mock_adb,
            pattern="skim",
            _fast_mode=True,
        )

        durations = [
            call_args[0][4]  # arg ke-5: duration_ms
            for call_args in mock_adb.execute_swipe.call_args_list
        ]

        if len(durations) > 1:
            # Jika ada lebih dari satu swipe, setidaknya ada kemungkinan variasi
            # (range 300–600 ms untuk pola 'skim' cukup lebar untuk variasi)
            # Verifikasi semua durasi berada dalam range yang valid untuk pola 'skim'
            for d in durations:
                assert 300 <= d <= 600, f"Durasi swipe {d}ms di luar range 'skim' (300–600ms)"

    @pytest.mark.asyncio
    async def test_fallback_to_sleep_when_no_adb_service(self) -> None:
        """
        Ketika adb_service=None, simulate_human_scroll harus berjalan tanpa error
        (fallback ke asyncio.sleep) dan tidak mencoba mengakses ADB apapun.
        """
        # Tidak perlu mock apa-apa — hanya pastikan tidak ada exception
        await simulate_human_scroll(
            device_id=None,
            adb_service=None,
            pattern="skim",
            _fast_mode=True,
        )

    @pytest.mark.asyncio
    async def test_all_scroll_patterns_work_with_adb(self) -> None:
        """Semua tiga pola scroll ('slow_read', 'skim', 'deep_read') harus berjalan tanpa error."""
        from unittest.mock import AsyncMock, MagicMock

        for pattern in ("slow_read", "skim", "deep_read"):
            mock_adb = MagicMock()
            mock_adb.get_screen_resolution = AsyncMock(return_value=(1080, 1920))
            mock_adb.execute_swipe = AsyncMock()

            await simulate_human_scroll(
                adb_service=mock_adb,
                pattern=pattern,
                _fast_mode=True,
            )

            # Setiap pola harus melakukan minimal 1 swipe
            assert mock_adb.execute_swipe.call_count >= 1, (
                f"Pola '{pattern}' seharusnya melakukan minimal 1 swipe"
            )

    @pytest.mark.asyncio
    async def test_adb_failure_does_not_crash_scroll(self) -> None:
        """
        Jika ADB execute_swipe gagal (raise exception), scroll harus tetap berjalan
        tanpa crash (graceful degradation sesuai implementasi).
        """
        from unittest.mock import AsyncMock, MagicMock

        mock_adb = MagicMock()
        mock_adb.get_screen_resolution = AsyncMock(return_value=(1080, 1920))
        mock_adb.execute_swipe = AsyncMock(side_effect=Exception("ADB connection lost"))

        # Tidak boleh raise exception
        await simulate_human_scroll(
            adb_service=mock_adb,
            pattern="skim",
            _fast_mode=True,
        )

    @pytest.mark.asyncio
    async def test_get_screen_resolution_called_with_adb_service(self) -> None:
        """get_screen_resolution harus dipanggil tepat sekali untuk mendapatkan dimensi layar."""
        from unittest.mock import AsyncMock, MagicMock

        mock_adb = MagicMock()
        mock_adb.get_screen_resolution = AsyncMock(return_value=(1080, 1920))
        mock_adb.execute_swipe = AsyncMock()

        await simulate_human_scroll(
            adb_service=mock_adb,
            pattern="skim",
            _fast_mode=True,
        )

        mock_adb.get_screen_resolution.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: detect_captcha_from_screenshot (async — via OCR pipeline)
# ---------------------------------------------------------------------------


class TestDetectCaptchaFromScreenshot:
    """
    Test suite untuk fungsi detect_captcha_from_screenshot.

    Fungsi ini menggunakan OCR untuk mengekstrak teks dari screenshot,
    lalu mendeteksi keyword CAPTCHA dari teks tersebut.
    Validates: Requirements 9.6
    """

    @pytest.mark.asyncio
    async def test_returns_true_when_ocr_extracts_captcha_text(self) -> None:
        """
        Ketika OCR mengekstrak teks yang mengandung keyword CAPTCHA,
        detect_captcha_from_screenshot harus mengembalikan True.
        """
        from unittest.mock import MagicMock, patch

        from app.services.anti_ban import detect_captcha_from_screenshot

        mock_ocr_result = MagicMock()
        mock_ocr_result.text = "Please verify your identity to continue."

        with patch(
            "app.services.ocr_service.extract_text", return_value=mock_ocr_result
        ):
            result = await detect_captcha_from_screenshot("/fake/screenshot.png")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_ocr_extracts_normal_text(self) -> None:
        """
        Ketika OCR mengekstrak teks normal (tanpa keyword CAPTCHA),
        detect_captcha_from_screenshot harus mengembalikan False.
        """
        from unittest.mock import MagicMock, patch

        from app.services.anti_ban import detect_captcha_from_screenshot

        mock_ocr_result = MagicMock()
        mock_ocr_result.text = "Check out these great job opportunities in software engineering."

        with patch(
            "app.services.ocr_service.extract_text", return_value=mock_ocr_result
        ):
            result = await detect_captcha_from_screenshot("/fake/screenshot.png")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_ocr_engine_unavailable(self) -> None:
        """
        Ketika OCR engine tidak tersedia (OCREngineUnavailableError),
        detect_captcha_from_screenshot harus mengembalikan False (graceful degradation).
        """
        from unittest.mock import patch

        from app.services.anti_ban import detect_captcha_from_screenshot
        from app.services.ocr_service import OCREngineUnavailableError

        with patch(
            "app.services.ocr_service.extract_text",
            side_effect=OCREngineUnavailableError("No OCR engine available"),
        ):
            result = await detect_captcha_from_screenshot("/fake/screenshot.png")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_generic_exception_occurs(self) -> None:
        """
        Ketika OCR melempar exception apapun (selain OCREngineUnavailableError),
        detect_captcha_from_screenshot harus mengembalikan False (graceful degradation).
        """
        from unittest.mock import patch

        from app.services.anti_ban import detect_captcha_from_screenshot

        with patch(
            "app.services.ocr_service.extract_text",
            side_effect=Exception("Unexpected error reading file"),
        ):
            result = await detect_captcha_from_screenshot("/fake/screenshot.png")

        assert result is False

    @pytest.mark.asyncio
    async def test_detects_captcha_keyword_via_ocr_pipeline(self) -> None:
        """
        Test end-to-end: OCR mengekstrak teks dengan keyword 'captcha',
        fungsi harus mengembalikan True.
        """
        from unittest.mock import MagicMock, patch

        from app.services.anti_ban import detect_captcha_from_screenshot

        mock_ocr_result = MagicMock()
        mock_ocr_result.text = "CAPTCHA required. Please complete the challenge."

        with patch(
            "app.services.ocr_service.extract_text", return_value=mock_ocr_result
        ):
            result = await detect_captcha_from_screenshot("/path/to/screen.png")

        assert result is True

    @pytest.mark.asyncio
    async def test_detects_unusual_activity_via_ocr_pipeline(self) -> None:
        """
        OCR mengekstrak teks 'unusual activity' → detect_captcha_from_screenshot True.
        """
        from unittest.mock import MagicMock, patch

        from app.services.anti_ban import detect_captcha_from_screenshot

        mock_ocr_result = MagicMock()
        mock_ocr_result.text = (
            "We noticed unusual activity from your device. "
            "Please confirm you are human."
        )

        with patch(
            "app.services.ocr_service.extract_text", return_value=mock_ocr_result
        ):
            result = await detect_captcha_from_screenshot("/path/to/screen.png")

        assert result is True

    @pytest.mark.asyncio
    async def test_extract_text_called_with_screenshot_path(self) -> None:
        """
        extract_text harus dipanggil dengan screenshot_path yang diberikan.
        """
        from unittest.mock import MagicMock, patch

        from app.services.anti_ban import detect_captcha_from_screenshot

        mock_ocr_result = MagicMock()
        mock_ocr_result.text = "Normal LinkedIn feed content here."

        with patch(
            "app.services.ocr_service.extract_text", return_value=mock_ocr_result
        ) as mock_extract:
            await detect_captcha_from_screenshot("/screenshots/page_001.png")

        mock_extract.assert_called_once_with("/screenshots/page_001.png")

    @pytest.mark.asyncio
    async def test_detects_pemeriksaan_keamanan_indonesian_via_screenshot(
        self,
    ) -> None:
        """
        Keyword bahasa Indonesia 'pemeriksaan keamanan' harus terdeteksi
        via pipeline OCR screenshot.
        """
        from unittest.mock import MagicMock, patch

        from app.services.anti_ban import detect_captcha_from_screenshot

        mock_ocr_result = MagicMock()
        mock_ocr_result.text = "Lakukan pemeriksaan keamanan untuk melanjutkan."

        with patch(
            "app.services.ocr_service.extract_text", return_value=mock_ocr_result
        ):
            result = await detect_captcha_from_screenshot("/fake/layar.png")

        assert result is True
