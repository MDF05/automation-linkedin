"""
OCR Engine — Ekstraksi teks dari screenshot layar HP Android.

Pipeline:
    Screenshot (bytes/path) → Preprocessing (grayscale, contrast, resize)
    → EasyOCR (primary, confidence >= 0.6)
    → Pytesseract (fallback jika EasyOCR tidak tersedia atau confidence rendah)
    → Filter (emoji, whitespace, min_len=10)
    → OCRResult {text, confidence, words_count}

Kedua library (EasyOCR dan pytesseract) diimpor secara lazy dengan try/except
sehingga service dapat berjalan meskipun salah satu atau keduanya tidak terinstal
(graceful degradation).

Requirements: 4.2, 4.8, 5.3
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

# ---------------------------------------------------------------------------
# Lazy imports — graceful degradation jika library tidak tersedia
# ---------------------------------------------------------------------------

try:
    import easyocr  # type: ignore[import]
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

try:
    import pytesseract  # type: ignore[import]
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

try:
    from PIL import Image, ImageEnhance, ImageFilter  # type: ignore[import]
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class OCRError(Exception):
    """Base exception untuk semua error OCR."""


class OCRInsufficientTextError(OCRError):
    """
    Raised ketika teks yang berhasil diekstrak dari screenshot kurang dari 10 karakter.

    Requirements: 4.8 — IF OCR_Engine gagal mengekstrak teks yang bermakna dari
    screenshot (teks < 10 karakter), THEN THE Bot SHALL melewati post tersebut.
    """


class OCREngineUnavailableError(OCRError):
    """Raised ketika tidak ada OCR engine yang tersedia (EasyOCR maupun pytesseract)."""


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class OCRResult:
    """
    Hasil ekstraksi teks dari screenshot.

    Attributes:
        text:        Teks yang telah difilter dan dinormalisasi.
        confidence:  Skor confidence rata-rata (0.0–1.0). -1.0 jika tidak tersedia.
        words_count: Jumlah kata dalam teks hasil ekstraksi.
        engine_used: Engine yang digunakan: 'easyocr', 'tesseract', atau 'none'.
    """

    text: str
    confidence: float
    words_count: int
    engine_used: str = "none"


# ---------------------------------------------------------------------------
# Preprocessing Helpers
# ---------------------------------------------------------------------------

# Threshold confidence EasyOCR — dari design.md OCR Pipeline
EASYOCR_CONFIDENCE_THRESHOLD: float = 0.6

# Panjang teks minimum yang dianggap bermakna
MIN_TEXT_LENGTH: int = 10

# Regex pattern untuk strip emoji (Unicode categories Sm, So, Sk, dan surrogate blocks)
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001f926-\U0001f937"
    "\U00010000-\U0010ffff"
    "\u2640-\u2642"
    "\u2600-\u2B55"
    "\u200d"
    "\u23cf"
    "\u23e9"
    "\u231a"
    "\ufe0f"  # dingbats
    "\u3030"
    "]+",
    flags=re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    """Hapus karakter emoji dari teks."""
    return _EMOJI_PATTERN.sub("", text)


def _normalize_whitespace(text: str) -> str:
    """Normalisasi whitespace berlebihan: strip dan collapse spasi ganda."""
    return " ".join(text.split())


def _filter_text(text: str) -> str:
    """
    Terapkan semua filter pada teks yang diekstrak:
    1. Strip emoji
    2. Normalisasi unicode (NFC)
    3. Normalisasi whitespace

    Requirements: 4.2 (dari design.md: Filter emoji, whitespace, min_len=10)
    """
    text = _strip_emoji(text)
    text = unicodedata.normalize("NFC", text)
    text = _normalize_whitespace(text)
    return text.strip()


def _preprocess_image_bytes(image_bytes: bytes) -> bytes:
    """
    Preprocessing gambar untuk meningkatkan akurasi OCR:
    1. Konversi ke grayscale
    2. Tingkatkan kontras menggunakan ImageEnhance
    3. Resize ke minimal 1800px lebar (jika lebih kecil) untuk OCR yang lebih akurat

    Returns:
        Bytes gambar PNG yang telah diproses.

    Requirements: design.md OCR Pipeline — Grayscale + Contrast + Resize
    """
    if not _PIL_AVAILABLE:
        # Jika PIL tidak tersedia, kembalikan bytes asli
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes))

    # Konversi ke grayscale
    img = img.convert("L")

    # Tingkatkan kontras dengan faktor 2.0
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # Resize jika lebar < 1800px (scale up proportionally)
    width, height = img.size
    if width < 1800:
        scale = 1800 / width
        new_width = int(width * scale)
        new_height = int(height * scale)
        img = img.resize((new_width, new_height), Image.LANCZOS)  # type: ignore[attr-defined]

    # Serialize ke bytes PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _load_image_bytes(source: Union[str, bytes, Path]) -> bytes:
    """
    Muat gambar dari berbagai sumber ke bytes.

    Args:
        source: Path string, Path object, atau raw bytes gambar.

    Returns:
        Raw image bytes.
    """
    if isinstance(source, bytes):
        return source
    path = Path(source) if isinstance(source, str) else source
    return path.read_bytes()


# ---------------------------------------------------------------------------
# OCR Engine (EasyOCR)
# ---------------------------------------------------------------------------

# Singleton reader untuk menghindari reload model berulang kali
_easyocr_reader: Optional[object] = None


def _get_easyocr_reader() -> "easyocr.Reader":  # type: ignore[name-defined]
    """Kembalikan singleton EasyOCR Reader (lazy init)."""
    global _easyocr_reader
    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(  # type: ignore[union-attr]
            ["en", "id"],  # English + Indonesian
            gpu=False,
            verbose=False,
        )
    return _easyocr_reader  # type: ignore[return-value]


def _extract_with_easyocr(image_bytes: bytes) -> Optional[OCRResult]:
    """
    Ekstrak teks menggunakan EasyOCR.

    Returns:
        OCRResult jika confidence rata-rata >= EASYOCR_CONFIDENCE_THRESHOLD,
        None jika confidence terlalu rendah atau terjadi error.

    Requirements: 4.2, design.md OCR Pipeline — EasyOCR (confidence >= 0.6)
    """
    if not _EASYOCR_AVAILABLE:
        return None

    try:
        reader = _get_easyocr_reader()
        # readtext menerima numpy array, PIL Image, atau path; kita gunakan bytes-wrapped PIL
        img = Image.open(io.BytesIO(image_bytes))
        results = reader.readtext(img)  # type: ignore[union-attr]

        if not results:
            return OCRResult(text="", confidence=0.0, words_count=0, engine_used="easyocr")

        # Setiap item: (bbox, text, confidence)
        texts = []
        confidences = []
        for _bbox, text, conf in results:
            confidences.append(conf)
            if conf >= EASYOCR_CONFIDENCE_THRESHOLD:
                texts.append(text)

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        if avg_confidence < EASYOCR_CONFIDENCE_THRESHOLD:
            # Confidence terlalu rendah — biarkan fallback ke tesseract
            return None

        combined_text = _filter_text(" ".join(texts))
        words_count = len(combined_text.split()) if combined_text else 0

        return OCRResult(
            text=combined_text,
            confidence=avg_confidence,
            words_count=words_count,
            engine_used="easyocr",
        )

    except Exception:
        return None


# ---------------------------------------------------------------------------
# OCR Engine (pytesseract fallback)
# ---------------------------------------------------------------------------


def _extract_with_tesseract(image_bytes: bytes) -> Optional[OCRResult]:
    """
    Ekstrak teks menggunakan pytesseract sebagai fallback.

    Returns:
        OCRResult jika berhasil, None jika terjadi error.

    Requirements: 4.2, design.md OCR Pipeline — Pytesseract fallback
    """
    if not _TESSERACT_AVAILABLE:
        return None

    try:
        img = Image.open(io.BytesIO(image_bytes))

        # Konfigurasi tesseract: mode OSD, bahasa English + Indonesian
        custom_config = r"--oem 3 --psm 3"
        try:
            raw_text = pytesseract.image_to_string(  # type: ignore[union-attr]
                img, lang="eng+ind", config=custom_config
            )
        except Exception:
            # Fallback ke English saja jika data bahasa Indonesia tidak tersedia
            raw_text = pytesseract.image_to_string(img, config=custom_config)  # type: ignore[union-attr]

        filtered_text = _filter_text(raw_text)
        words_count = len(filtered_text.split()) if filtered_text else 0

        # Pytesseract tidak memberikan confidence per default — gunakan -1.0 sebagai penanda
        return OCRResult(
            text=filtered_text,
            confidence=-1.0,
            words_count=words_count,
            engine_used="tesseract",
        )

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_text(source: Union[str, bytes, Path]) -> OCRResult:
    """
    Ekstrak teks dari screenshot layar HP.

    Pipeline:
    1. Muat gambar dari path atau bytes
    2. Preprocessing: grayscale + enhance contrast + resize
    3. Coba EasyOCR (primary) — gunakan hasilnya jika confidence >= 0.6
    4. Fallback ke pytesseract jika EasyOCR gagal atau tidak tersedia
    5. Filter teks: strip emoji, normalisasi whitespace
    6. Raise OCRInsufficientTextError jika teks < MIN_TEXT_LENGTH (10 karakter)

    Args:
        source: Path ke file gambar (str atau Path), atau raw bytes gambar dari screenshot.

    Returns:
        OCRResult dengan field: text, confidence, words_count, engine_used.

    Raises:
        OCRInsufficientTextError: Jika teks yang berhasil diekstrak < 10 karakter.
        OCREngineUnavailableError: Jika tidak ada engine OCR yang tersedia.
        FileNotFoundError: Jika source adalah path dan file tidak ditemukan.

    Requirements: 4.2, 4.8, 5.3
    """
    # --- 1. Muat bytes gambar ---
    image_bytes = _load_image_bytes(source)

    # --- 2. Preprocessing ---
    processed_bytes = _preprocess_image_bytes(image_bytes)

    # --- 3. Coba EasyOCR (primary) ---
    result = _extract_with_easyocr(processed_bytes)

    # --- 4. Fallback ke pytesseract ---
    if result is None:
        result = _extract_with_tesseract(processed_bytes)

    # --- 5. Tidak ada engine tersedia ---
    if result is None:
        raise OCREngineUnavailableError(
            "Tidak ada OCR engine yang tersedia. "
            "Install easyocr atau pytesseract."
        )

    # --- 6. Validasi panjang teks minimum ---
    if len(result.text) < MIN_TEXT_LENGTH:
        raise OCRInsufficientTextError(
            f"Teks yang diekstrak terlalu pendek ({len(result.text)} karakter, "
            f"minimum {MIN_TEXT_LENGTH}). "
            f"Teks: {result.text!r}"
        )

    return result
