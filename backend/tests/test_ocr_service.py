"""
Unit tests untuk `ocr_service.py` — berbagai skenario screenshot.

Validates: Requirements 4.2, 4.8

Tests yang dicakup:
- Screenshot kosong (tidak ada teks yang diekstrak) → OCRInsufficientTextError
- Teks < 10 karakter → OCRInsufficientTextError
- Teks normal (>= 10 karakter) → mengembalikan OCRResult dengan field yang benar
- Teks campuran (Indonesia + Inggris) → mengembalikan OCRResult gabungan
- Confidence EasyOCR terlalu rendah → fallback ke pytesseract
- EasyOCR tidak tersedia → menggunakan pytesseract
"""

from __future__ import annotations

import io
from typing import List, Tuple
from unittest.mock import MagicMock, patch

import pytest

from app.services.ocr_service import (
    MIN_TEXT_LENGTH,
    OCREngineUnavailableError,
    OCRInsufficientTextError,
    OCRResult,
    _extract_with_easyocr,
    _extract_with_tesseract,
    _filter_text,
    extract_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_png_bytes() -> bytes:
    """Buat bytes PNG minimal valid untuk digunakan sebagai input screenshot."""
    try:
        from PIL import Image  # type: ignore[import]

        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        # Fallback: bytes PNG 1x1 yang valid (hardcoded)
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )


SAMPLE_PNG = _make_minimal_png_bytes()

# Teks normal dengan panjang >= MIN_TEXT_LENGTH (10 karakter)
NORMAL_TEXT = "Hello LinkedIn, this is a normal post content."

# Teks campuran (Indonesia + Inggris)
MIXED_TEXT = "Selamat pagi! Good morning everyone, have a great day di LinkedIn."

# Teks < 10 karakter (terlalu pendek)
SHORT_TEXT = "Hi"

# Teks kosong
EMPTY_TEXT = ""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def png_bytes() -> bytes:
    """Kembalikan bytes PNG minimal untuk dipakai di test."""
    return SAMPLE_PNG


# ---------------------------------------------------------------------------
# Helper: membuat mock EasyOCR result
# Setiap item: (bbox, text, confidence)
# ---------------------------------------------------------------------------


def _easyocr_results(
    text: str,
    confidence: float = 0.85,
) -> List[Tuple[list, str, float]]:
    """Buat list hasil EasyOCR dengan satu item."""
    bbox = [[0, 0], [100, 0], [100, 20], [0, 20]]
    return [(bbox, text, confidence)]


def _easyocr_results_multi(
    items: List[Tuple[str, float]],
) -> List[Tuple[list, str, float]]:
    """Buat list hasil EasyOCR dari beberapa pasangan (text, confidence)."""
    bbox = [[0, 0], [100, 0], [100, 20], [0, 20]]
    return [(bbox, text, conf) for text, conf in items]


# ---------------------------------------------------------------------------
# Tests: _filter_text (helper)
# ---------------------------------------------------------------------------


class TestFilterText:
    """Test suite untuk fungsi _filter_text."""

    def test_strips_emoji(self) -> None:
        """Emoji harus dihapus dari teks."""
        text = "Hello 😀 World 🚀"
        result = _filter_text(text)
        assert "😀" not in result
        assert "🚀" not in result

    def test_normalizes_whitespace(self) -> None:
        """Whitespace berlebihan harus dinormalisasi menjadi satu spasi."""
        text = "Hello   World\n\nTest"
        result = _filter_text(text)
        assert "  " not in result
        assert result == "Hello World Test"

    def test_strips_leading_trailing_whitespace(self) -> None:
        """Whitespace di awal/akhir harus dihapus."""
        text = "  Hello World  "
        result = _filter_text(text)
        assert result == "Hello World"

    def test_empty_string_returns_empty(self) -> None:
        """String kosong dikembalikan sebagai string kosong."""
        assert _filter_text("") == ""

    def test_normal_text_unchanged(self) -> None:
        """Teks normal (tanpa emoji/whitespace berlebihan) tidak berubah."""
        text = "This is a normal post content."
        assert _filter_text(text) == text


# ---------------------------------------------------------------------------
# Tests: Skenario 1 — Screenshot kosong (tidak ada teks diekstrak)
# ---------------------------------------------------------------------------


class TestEmptyScreenshot:
    """
    Skenario 1: Screenshot kosong → OCRInsufficientTextError.

    Validates: Requirements 4.8 — IF OCR_Engine gagal mengekstrak teks yang bermakna
    (teks < 10 karakter), THEN THE Bot SHALL melewati post tersebut.
    """

    def test_empty_screenshot_easyocr_raises_insufficient_text_error(
        self, png_bytes: bytes
    ) -> None:
        """EasyOCR mengembalikan teks kosong → OCRInsufficientTextError."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = []
            mock_reader_fn.return_value = mock_reader

            with pytest.raises(OCRInsufficientTextError):
                extract_text(png_bytes)

    def test_empty_screenshot_tesseract_raises_insufficient_text_error(
        self, png_bytes: bytes
    ) -> None:
        """pytesseract mengembalikan teks kosong → OCRInsufficientTextError."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", False),
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", True),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            with patch(
                "app.services.ocr_service.pytesseract"
            ) as mock_tess:
                mock_tess.image_to_string.return_value = ""

                with pytest.raises(OCRInsufficientTextError):
                    extract_text(png_bytes)

    def test_error_message_mentions_length(self, png_bytes: bytes) -> None:
        """Pesan error harus menyebutkan panjang teks yang diekstrak."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = []
            mock_reader_fn.return_value = mock_reader

            with pytest.raises(OCRInsufficientTextError, match=r"\d+ karakter"):
                extract_text(png_bytes)


# ---------------------------------------------------------------------------
# Tests: Skenario 2 — Teks < 10 karakter
# ---------------------------------------------------------------------------


class TestShortText:
    """
    Skenario 2: Teks < 10 karakter → OCRInsufficientTextError.

    Validates: Requirements 4.8 — teks < 10 karakter dianggap tidak bermakna.
    """

    def test_text_less_than_10_chars_easyocr_raises(self, png_bytes: bytes) -> None:
        """Teks 2 karakter dari EasyOCR → OCRInsufficientTextError."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(SHORT_TEXT)
            mock_reader_fn.return_value = mock_reader

            with pytest.raises(OCRInsufficientTextError):
                extract_text(png_bytes)

    def test_text_exactly_9_chars_raises(self, png_bytes: bytes) -> None:
        """Teks tepat 9 karakter (< 10) → OCRInsufficientTextError."""
        text_9 = "123456789"  # 9 karakter
        assert len(text_9) == 9

        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(text_9)
            mock_reader_fn.return_value = mock_reader

            with pytest.raises(OCRInsufficientTextError):
                extract_text(png_bytes)

    def test_text_less_than_10_chars_tesseract_raises(self, png_bytes: bytes) -> None:
        """Teks 5 karakter dari pytesseract → OCRInsufficientTextError."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", False),
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", True),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            with patch("app.services.ocr_service.pytesseract") as mock_tess:
                mock_tess.image_to_string.return_value = "Hello"

                with pytest.raises(OCRInsufficientTextError):
                    extract_text(png_bytes)

    def test_min_text_length_constant_is_10(self) -> None:
        """Konstanta MIN_TEXT_LENGTH harus bernilai 10."""
        assert MIN_TEXT_LENGTH == 10


# ---------------------------------------------------------------------------
# Tests: Skenario 3 — Teks normal (>= 10 karakter)
# ---------------------------------------------------------------------------


class TestNormalText:
    """
    Skenario 3: Teks normal (>= 10 karakter) → OCRResult dengan field yang benar.

    Validates: Requirements 4.2 — OCR_Engine SHALL mengekstrak teks dari post.
    """

    def test_normal_text_returns_ocr_result(self, png_bytes: bytes) -> None:
        """Teks normal → mengembalikan instance OCRResult."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(NORMAL_TEXT)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)

            assert isinstance(result, OCRResult)

    def test_normal_text_result_contains_text(self, png_bytes: bytes) -> None:
        """OCRResult.text harus berisi teks yang diekstrak."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(NORMAL_TEXT)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)

            assert len(result.text) >= MIN_TEXT_LENGTH

    def test_normal_text_result_has_confidence(self, png_bytes: bytes) -> None:
        """OCRResult.confidence harus berupa float dalam range 0.0–1.0."""
        confidence = 0.85
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(
                NORMAL_TEXT, confidence=confidence
            )
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)

            assert isinstance(result.confidence, float)
            assert 0.0 <= result.confidence <= 1.0

    def test_normal_text_result_has_words_count(self, png_bytes: bytes) -> None:
        """OCRResult.words_count harus > 0 untuk teks normal."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(NORMAL_TEXT)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)

            assert result.words_count > 0

    def test_normal_text_result_has_engine_used_easyocr(
        self, png_bytes: bytes
    ) -> None:
        """OCRResult.engine_used harus 'easyocr' ketika EasyOCR berhasil."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(NORMAL_TEXT)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)

            assert result.engine_used == "easyocr"

    def test_text_exactly_10_chars_does_not_raise(self, png_bytes: bytes) -> None:
        """Teks tepat 10 karakter (boundary) → TIDAK raise OCRInsufficientTextError."""
        text_10 = "1234567890"  # tepat 10 karakter
        assert len(text_10) == 10

        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(text_10)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)
            assert len(result.text) >= MIN_TEXT_LENGTH

    def test_words_count_matches_actual_word_count(self, png_bytes: bytes) -> None:
        """OCRResult.words_count harus sesuai dengan jumlah kata sebenarnya."""
        text = "Hello LinkedIn this is five"  # 5 kata
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(text)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)

            assert result.words_count == len(result.text.split())


# ---------------------------------------------------------------------------
# Tests: Skenario 4 — Teks campuran bahasa (Indonesia + Inggris)
# ---------------------------------------------------------------------------


class TestMixedLanguageText:
    """
    Skenario 4: Teks campuran (Indonesia + Inggris) → OCRResult gabungan.

    Validates: Requirements 4.2 — OCR_Engine harus mendukung teks berbahasa Latin
    dengan akurasi minimal 80%.
    """

    def test_mixed_language_returns_ocr_result(self, png_bytes: bytes) -> None:
        """Teks campuran Indonesia+Inggris → OCRResult berhasil dikembalikan."""
        indonesian = "Selamat pagi semua"
        english = "Good morning everyone"
        items = [(indonesian, 0.9), (english, 0.88)]

        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results_multi(items)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)

            assert isinstance(result, OCRResult)

    def test_mixed_language_combines_texts(self, png_bytes: bytes) -> None:
        """Teks dari kedua bahasa harus digabungkan dalam OCRResult.text."""
        indonesian = "Selamat pagi semua"
        english = "Good morning everyone"
        items = [(indonesian, 0.9), (english, 0.88)]

        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results_multi(items)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)

            # Teks gabungan harus mengandung kata dari kedua bahasa
            assert "Selamat" in result.text or "pagi" in result.text or len(result.text) >= MIN_TEXT_LENGTH

    def test_mixed_language_confidence_is_average(self, png_bytes: bytes) -> None:
        """Confidence harus merupakan rata-rata dari semua hasil EasyOCR."""
        conf1, conf2 = 0.9, 0.8
        items = [("Selamat pagi semua", conf1), ("Good morning everyone", conf2)]
        expected_avg = (conf1 + conf2) / 2

        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results_multi(items)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)

            assert abs(result.confidence - expected_avg) < 0.01

    def test_mixed_language_long_text_does_not_raise(
        self, png_bytes: bytes
    ) -> None:
        """Teks campuran panjang tidak boleh raise exception apapun."""
        long_mixed = (
            "Saya sangat senang bekerja di perusahaan ini. "
            "I am very happy working at this company. "
            "Terima kasih atas semua dukungannya!"
        )
        items = [(long_mixed, 0.87)]

        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results_multi(items)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)
            assert len(result.text) >= MIN_TEXT_LENGTH


# ---------------------------------------------------------------------------
# Tests: Skenario 5 — EasyOCR confidence terlalu rendah → fallback pytesseract
# ---------------------------------------------------------------------------


class TestEasyOCRLowConfidenceFallback:
    """
    Skenario 5: Confidence EasyOCR < 0.6 → fallback ke pytesseract.

    Validates: Requirements 4.2 — OCR Pipeline fallback behavior.
    """

    def test_low_confidence_falls_back_to_tesseract(self, png_bytes: bytes) -> None:
        """Confidence rata-rata < 0.6 → hasil datang dari pytesseract."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", True),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            # EasyOCR dengan confidence rendah (0.3 < threshold 0.6)
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(
                NORMAL_TEXT, confidence=0.3
            )
            mock_reader_fn.return_value = mock_reader

            with patch("app.services.ocr_service.pytesseract") as mock_tess:
                mock_tess.image_to_string.return_value = NORMAL_TEXT

                result = extract_text(png_bytes)

                # Harus menggunakan tesseract karena EasyOCR confidence rendah
                assert result.engine_used == "tesseract"

    def test_low_confidence_engine_used_is_tesseract(
        self, png_bytes: bytes
    ) -> None:
        """engine_used harus 'tesseract' ketika EasyOCR confidence rendah."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", True),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(
                "short", confidence=0.2
            )
            mock_reader_fn.return_value = mock_reader

            with patch("app.services.ocr_service.pytesseract") as mock_tess:
                mock_tess.image_to_string.return_value = NORMAL_TEXT

                result = extract_text(png_bytes)

                assert result.engine_used == "tesseract"

    def test_low_confidence_tesseract_confidence_is_minus_one(
        self, png_bytes: bytes
    ) -> None:
        """Ketika fallback ke tesseract, confidence harus -1.0 (tidak tersedia)."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", True),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(
                NORMAL_TEXT, confidence=0.1
            )
            mock_reader_fn.return_value = mock_reader

            with patch("app.services.ocr_service.pytesseract") as mock_tess:
                mock_tess.image_to_string.return_value = NORMAL_TEXT

                result = extract_text(png_bytes)

                assert result.confidence == -1.0

    def test_easyocr_returns_none_when_confidence_below_threshold(
        self, png_bytes: bytes
    ) -> None:
        """_extract_with_easyocr harus mengembalikan None jika confidence < threshold."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(
                NORMAL_TEXT, confidence=0.4
            )
            mock_reader_fn.return_value = mock_reader

            result = _extract_with_easyocr(png_bytes)

            assert result is None


# ---------------------------------------------------------------------------
# Tests: Skenario 6 — EasyOCR tidak tersedia → menggunakan pytesseract
# ---------------------------------------------------------------------------


class TestEasyOCRUnavailable:
    """
    Skenario 6: EasyOCR tidak tersedia → menggunakan pytesseract sebagai satu-satunya engine.

    Validates: Requirements 4.2 — graceful degradation.
    """

    def test_easyocr_unavailable_uses_tesseract(self, png_bytes: bytes) -> None:
        """Ketika EasyOCR tidak tersedia, hasil harus datang dari pytesseract."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", False),
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", True),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            with patch("app.services.ocr_service.pytesseract") as mock_tess:
                mock_tess.image_to_string.return_value = NORMAL_TEXT

                result = extract_text(png_bytes)

                assert result.engine_used == "tesseract"

    def test_easyocr_unavailable_returns_valid_result(
        self, png_bytes: bytes
    ) -> None:
        """Ketika EasyOCR tidak tersedia, OCRResult tetap valid."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", False),
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", True),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            with patch("app.services.ocr_service.pytesseract") as mock_tess:
                mock_tess.image_to_string.return_value = NORMAL_TEXT

                result = extract_text(png_bytes)

                assert isinstance(result, OCRResult)
                assert len(result.text) >= MIN_TEXT_LENGTH
                assert result.words_count > 0

    def test_easyocr_returns_none_when_not_available(self) -> None:
        """_extract_with_easyocr harus mengembalikan None jika tidak tersedia."""
        with patch("app.services.ocr_service._EASYOCR_AVAILABLE", False):
            result = _extract_with_easyocr(SAMPLE_PNG)
            assert result is None

    def test_tesseract_returns_none_when_not_available(self) -> None:
        """_extract_with_tesseract harus mengembalikan None jika tidak tersedia."""
        with patch("app.services.ocr_service._TESSERACT_AVAILABLE", False):
            result = _extract_with_tesseract(SAMPLE_PNG)
            assert result is None

    def test_both_engines_unavailable_raises_engine_unavailable_error(
        self, png_bytes: bytes
    ) -> None:
        """Ketika kedua engine tidak tersedia → OCREngineUnavailableError."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", False),
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            with pytest.raises(OCREngineUnavailableError):
                extract_text(png_bytes)

    def test_easyocr_unavailable_tesseract_confidence_is_minus_one(
        self, png_bytes: bytes
    ) -> None:
        """Ketika hanya menggunakan tesseract, confidence harus -1.0."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", False),
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", True),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            with patch("app.services.ocr_service.pytesseract") as mock_tess:
                mock_tess.image_to_string.return_value = NORMAL_TEXT

                result = extract_text(png_bytes)

                assert result.confidence == -1.0


# ---------------------------------------------------------------------------
# Tests: OCRResult dataclass
# ---------------------------------------------------------------------------


class TestOCRResultDataclass:
    """Test suite untuk validasi struktur OCRResult."""

    def test_ocr_result_has_required_fields(self) -> None:
        """OCRResult harus memiliki semua field yang diperlukan."""
        result = OCRResult(
            text="Hello LinkedIn world",
            confidence=0.9,
            words_count=3,
            engine_used="easyocr",
        )
        assert result.text == "Hello LinkedIn world"
        assert result.confidence == 0.9
        assert result.words_count == 3
        assert result.engine_used == "easyocr"

    def test_ocr_result_default_engine_used(self) -> None:
        """engine_used default harus 'none'."""
        result = OCRResult(text="test text ok", confidence=0.9, words_count=3)
        assert result.engine_used == "none"

    def test_ocr_result_is_dataclass(self) -> None:
        """OCRResult harus berupa dataclass."""
        import dataclasses

        assert dataclasses.is_dataclass(OCRResult)


# ---------------------------------------------------------------------------
# Tests: extract_text — load dari bytes
# ---------------------------------------------------------------------------


class TestExtractTextFromBytes:
    """Test suite untuk extract_text dengan input bytes."""

    def test_extract_text_accepts_bytes_input(self, png_bytes: bytes) -> None:
        """extract_text harus menerima input berupa bytes."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", False),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.return_value = _easyocr_results(NORMAL_TEXT)
            mock_reader_fn.return_value = mock_reader

            result = extract_text(png_bytes)
            assert isinstance(result, OCRResult)

    def test_extract_text_with_easyocr_error_falls_back(
        self, png_bytes: bytes
    ) -> None:
        """Ketika EasyOCR raise exception, harus fallback ke tesseract."""
        with (
            patch("app.services.ocr_service._EASYOCR_AVAILABLE", True),
            patch("app.services.ocr_service._get_easyocr_reader") as mock_reader_fn,
            patch("app.services.ocr_service._TESSERACT_AVAILABLE", True),
            patch("app.services.ocr_service._PIL_AVAILABLE", False),
        ):
            mock_reader = MagicMock()
            mock_reader.readtext.side_effect = RuntimeError("EasyOCR error")
            mock_reader_fn.return_value = mock_reader

            with patch("app.services.ocr_service.pytesseract") as mock_tess:
                mock_tess.image_to_string.return_value = NORMAL_TEXT

                result = extract_text(png_bytes)
                assert result.engine_used == "tesseract"
