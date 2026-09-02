"""
Unit tests untuk `csv_exporter.py` — semua metode.

Validates: Requirements 11.1–11.4

Tests yang dicakup:
- Semua fungsi export menghasilkan bytes yang diawali UTF-8 BOM (Req 11.3)
- Baris pertama adalah header deskriptif yang sesuai (Req 11.4)
- Jumlah baris data sesuai dengan jumlah record yang diberikan (Req 11.2)
- Dataset kosong menghasilkan CSV hanya dengan baris header + BOM
- Semua kolom yang diperlukan hadir dalam header untuk setiap entitas (Req 11.1, 11.4)
- Nilai field tercermin dengan benar dalam output CSV
- Filter status dan rentang tanggal membatasi baris dengan benar (Req 11.2)
- Karakter khusus (koma, tanda kutip, newline) di-escape dengan benar

Catatan: csv_exporter.py menerima list dict Python biasa — tidak ada DB,
sehingga semua test ini adalah pure unit tests tanpa perlu mocking DB.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import pytest

from app.services.csv_exporter import (
    BOT_LOGS_HEADERS,
    INTERACTIONS_HEADERS,
    JOB_APPLICATIONS_HEADERS,
    POSTS_HEADERS,
    UTF8_BOM,
    export_bot_logs,
    export_interactions,
    export_job_applications,
    export_posts,
    parse_csv_bytes,
)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _decode_csv(csv_bytes: bytes) -> List[Dict[str, str]]:
    """Decode CSV bytes (strip BOM) dan kembalikan list of dicts."""
    return parse_csv_bytes(csv_bytes)


def _count_rows(csv_bytes: bytes) -> int:
    """Hitung jumlah baris data (tidak termasuk header) dari CSV bytes."""
    return len(_decode_csv(csv_bytes))


def _get_header_row(csv_bytes: bytes) -> List[str]:
    """
    Ambil baris header dari CSV bytes.
    Strip BOM jika ada, lalu parse baris pertama sebagai header.
    """
    raw = csv_bytes
    if raw.startswith(UTF8_BOM):
        raw = raw[len(UTF8_BOM):]
    text = raw.decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    return next(reader)


def _filter_by_status(
    records: List[Dict[str, Any]], status: str
) -> List[Dict[str, Any]]:
    """Simulasi filter status pada list records."""
    return [r for r in records if r.get("status") == status]


def _filter_by_date_range(
    records: List[Dict[str, Any]],
    field: str,
    start: datetime,
    end: datetime,
) -> List[Dict[str, Any]]:
    """Simulasi filter rentang tanggal pada list records berdasarkan field ISO string."""
    result = []
    for r in records:
        val = r.get(field)
        if val is None:
            continue
        try:
            dt = datetime.fromisoformat(str(val))
            # normalisasi timezone-aware vs naive
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if start <= dt <= end:
                result.append(r)
        except (ValueError, TypeError):
            pass
    return result


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_posts() -> List[Dict[str, Any]]:
    """Tiga post dengan status berbeda untuk dipakai dalam berbagai test."""
    return [
        {
            "id": 1,
            "title": "Tips Python",
            "content": "Gunakan list comprehension untuk kode yang lebih bersih.",
            "content_type": "tips_list",
            "status": "posted",
            "platform": "linkedin",
            "image_url": None,
            "is_thread": False,
            "thread_count": 1,
            "scheduled_at": None,
            "posted_at": "2024-03-01T10:00:00+00:00",
            "likes": 42,
            "comments": 5,
            "shares": 2,
            "ai_provider_used": "deepseek",
            "tone": "edukasi",
            "linkedin_post_id": "urn:li:share:111",
            "created_at": "2024-03-01T09:00:00+00:00",
            "updated_at": "2024-03-01T10:05:00+00:00",
        },
        {
            "id": 2,
            "title": "Draft Motivasi",
            "content": "Jangan menyerah saat menghadapi tantangan.",
            "content_type": "storytelling",
            "status": "draft",
            "platform": "linkedin",
            "image_url": None,
            "is_thread": False,
            "thread_count": 1,
            "scheduled_at": None,
            "posted_at": None,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "ai_provider_used": "groq",
            "tone": "inspiratif",
            "linkedin_post_id": None,
            "created_at": "2024-03-05T08:00:00+00:00",
            "updated_at": "2024-03-05T08:00:00+00:00",
        },
        {
            "id": 3,
            "title": "Promosi Jasa",
            "content": "Kami menawarkan layanan konsultasi IT terbaik.",
            "content_type": "promo",
            "status": "scheduled",
            "platform": "linkedin",
            "image_url": "https://example.com/img.jpg",
            "is_thread": False,
            "thread_count": 1,
            "scheduled_at": "2024-03-10T09:00:00+00:00",
            "posted_at": None,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "ai_provider_used": "groq",
            "tone": "profesional",
            "linkedin_post_id": None,
            "created_at": "2024-03-06T07:00:00+00:00",
            "updated_at": "2024-03-06T07:00:00+00:00",
        },
    ]


@pytest.fixture()
def sample_bot_logs() -> List[Dict[str, Any]]:
    """Empat entri bot_log dengan status dan aksi berbeda."""
    return [
        {
            "id": 1,
            "post_id": 1,
            "task_id": "task-001",
            "action": "publish_post",
            "status": "success",
            "message": "Post berhasil dipublikasikan.",
            "error_detail": None,
            "stack_trace": None,
            "screenshot_path": "/static/screenshots/001.png",
            "duration_ms": 4500,
            "module": "A",
            "created_at": "2024-03-01T10:00:00+00:00",
        },
        {
            "id": 2,
            "post_id": None,
            "task_id": "task-002",
            "action": "generate_comment",
            "status": "success",
            "message": "Komentar berhasil dibuat.",
            "error_detail": None,
            "stack_trace": None,
            "screenshot_path": None,
            "duration_ms": 1200,
            "module": "C",
            "created_at": "2024-03-02T11:00:00+00:00",
        },
        {
            "id": 3,
            "post_id": None,
            "task_id": "task-003",
            "action": "open_linkedin",
            "status": "failed",
            "message": "Timeout saat membuka LinkedIn.",
            "error_detail": "ADBTimeoutError: timeout after 30s",
            "stack_trace": "Traceback (most recent call last):\n  ...",
            "screenshot_path": "/static/screenshots/003_err.png",
            "duration_ms": 30000,
            "module": "A",
            "created_at": "2024-03-03T09:00:00+00:00",
        },
        {
            "id": 4,
            "post_id": None,
            "task_id": "task-004",
            "action": "idle_wait",
            "status": "skipped",
            "message": "Batas harian tercapai.",
            "error_detail": None,
            "stack_trace": None,
            "screenshot_path": None,
            "duration_ms": 0,
            "module": "C",
            "created_at": "2024-03-04T15:00:00+00:00",
        },
    ]


@pytest.fixture()
def sample_interactions() -> List[Dict[str, Any]]:
    """Tiga interaksi dengan status berbeda."""
    return [
        {
            "id": 1,
            "target_post_url": "https://linkedin.com/posts/abc-123",
            "target_author": "Budi Santoso",
            "target_post_text": "5 tips produktivitas kerja dari rumah.",
            "action_type": "comment",
            "content_sent": "Sangat bermanfaat, terima kasih!",
            "status": "success",
            "skip_reason": None,
            "ai_provider_used": "deepseek",
            "screenshot_path": "/static/screenshots/int_001.png",
            "created_at": "2024-03-01T14:00:00+00:00",
        },
        {
            "id": 2,
            "target_post_url": "https://linkedin.com/posts/def-456",
            "target_author": "Siti Rahayu",
            "target_post_text": "Bergabung bersama kami!",
            "action_type": "comment",
            "content_sent": None,
            "status": "skipped",
            "skip_reason": "teks_terlalu_pendek",
            "ai_provider_used": None,
            "screenshot_path": None,
            "created_at": "2024-03-02T10:00:00+00:00",
        },
        {
            "id": 3,
            "target_post_url": "https://linkedin.com/posts/ghi-789",
            "target_author": "Andi Wijaya",
            "target_post_text": "Pandangan saya tentang remote work.",
            "action_type": "comment",
            "content_sent": "Setuju sekali dengan perspektif ini.",
            "status": "failed",
            "skip_reason": None,
            "ai_provider_used": "groq",
            "screenshot_path": "/static/screenshots/int_003_err.png",
            "created_at": "2024-03-03T16:00:00+00:00",
        },
    ]


@pytest.fixture()
def sample_job_applications() -> List[Dict[str, Any]]:
    """Empat lamaran pekerjaan dengan status berbeda."""
    return [
        {
            "id": 1,
            "job_title": "Backend Developer",
            "company": "PT Teknologi Maju",
            "location": "Jakarta",
            "salary_range": "10-15jt",
            "job_url": "https://linkedin.com/jobs/111",
            "status": "applied",
            "has_easy_apply": True,
            "job_type": "full-time",
            "applied_at": "2024-03-01T09:00:00+00:00",
            "notes": "Melamar via Easy Apply",
            "search_session_id": "sess-001",
            "screenshot_path": "/static/screenshots/job_001.png",
            "created_at": "2024-03-01T08:00:00+00:00",
            "updated_at": "2024-03-01T09:00:00+00:00",
        },
        {
            "id": 2,
            "job_title": "Data Analyst",
            "company": "Startup Innovasi",
            "location": "Remote",
            "salary_range": None,
            "job_url": "https://linkedin.com/jobs/222",
            "status": "found",
            "has_easy_apply": False,
            "job_type": "full-time",
            "applied_at": None,
            "notes": None,
            "search_session_id": "sess-001",
            "screenshot_path": None,
            "created_at": "2024-03-01T08:30:00+00:00",
            "updated_at": "2024-03-01T08:30:00+00:00",
        },
        {
            "id": 3,
            "job_title": "Frontend Engineer",
            "company": "Perusahaan Digital",
            "location": "Bandung",
            "salary_range": "8-12jt",
            "job_url": "https://linkedin.com/jobs/333",
            "status": "skipped",
            "has_easy_apply": True,
            "job_type": "full-time",
            "applied_at": None,
            "notes": None,
            "search_session_id": "sess-001",
            "screenshot_path": None,
            "created_at": "2024-03-01T08:45:00+00:00",
            "updated_at": "2024-03-01T08:45:00+00:00",
        },
        {
            "id": 4,
            "job_title": "DevOps Engineer",
            "company": "Cloud Solutions",
            "location": "Jakarta",
            "salary_range": "15-20jt",
            "job_url": "https://linkedin.com/jobs/444",
            "status": "applied",
            "has_easy_apply": True,
            "job_type": "kontrak",
            "applied_at": "2024-03-02T11:00:00+00:00",
            "notes": "Fast process",
            "search_session_id": "sess-002",
            "screenshot_path": "/static/screenshots/job_004.png",
            "created_at": "2024-03-02T10:00:00+00:00",
            "updated_at": "2024-03-02T11:05:00+00:00",
        },
    ]


# ---------------------------------------------------------------------------
# Tests: UTF-8 BOM (Requirements 11.3)
# ---------------------------------------------------------------------------


class TestUTF8BOM:
    """Semua fungsi export harus menghasilkan CSV yang diawali UTF-8 BOM."""

    def test_export_posts_starts_with_bom(self, sample_posts: List[Dict[str, Any]]) -> None:
        """export_posts harus menghasilkan bytes yang diawali UTF-8 BOM."""
        result = export_posts(sample_posts)
        assert result[:3] == UTF8_BOM, (
            f"export_posts harus diawali UTF-8 BOM \\xef\\xbb\\xbf, "
            f"bukan {result[:3]!r}"
        )

    def test_export_bot_logs_starts_with_bom(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """export_bot_logs harus menghasilkan bytes yang diawali UTF-8 BOM."""
        result = export_bot_logs(sample_bot_logs)
        assert result[:3] == UTF8_BOM

    def test_export_interactions_starts_with_bom(
        self, sample_interactions: List[Dict[str, Any]]
    ) -> None:
        """export_interactions harus menghasilkan bytes yang diawali UTF-8 BOM."""
        result = export_interactions(sample_interactions)
        assert result[:3] == UTF8_BOM

    def test_export_job_applications_starts_with_bom(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """export_job_applications harus menghasilkan bytes yang diawali UTF-8 BOM."""
        result = export_job_applications(sample_job_applications)
        assert result[:3] == UTF8_BOM

    def test_bom_present_on_empty_dataset(self) -> None:
        """BOM harus tetap ada meskipun dataset kosong."""
        assert export_posts([])[:3] == UTF8_BOM
        assert export_bot_logs([])[:3] == UTF8_BOM
        assert export_interactions([])[:3] == UTF8_BOM
        assert export_job_applications([])[:3] == UTF8_BOM

    def test_bom_value_is_correct_three_bytes(self) -> None:
        """Nilai UTF-8 BOM harus persis tiga byte: 0xEF 0xBB 0xBF."""
        assert UTF8_BOM == b"\xef\xbb\xbf"
        result = export_posts([])
        assert result[0] == 0xEF
        assert result[1] == 0xBB
        assert result[2] == 0xBF

    def test_export_returns_bytes_type(self) -> None:
        """Semua fungsi export harus mengembalikan tipe bytes."""
        assert isinstance(export_posts([]), bytes)
        assert isinstance(export_bot_logs([]), bytes)
        assert isinstance(export_interactions([]), bytes)
        assert isinstance(export_job_applications([]), bytes)


# ---------------------------------------------------------------------------
# Tests: Header Row (Requirements 11.4)
# ---------------------------------------------------------------------------


class TestHeaderRow:
    """Baris header harus ada dan berisi kolom deskriptif yang benar."""

    def test_export_posts_has_correct_header(self) -> None:
        """export_posts harus menghasilkan header yang persis sesuai POSTS_HEADERS."""
        result = export_posts([])
        header = _get_header_row(result)
        assert header == POSTS_HEADERS, (
            f"Header posts tidak sesuai.\n"
            f"Expected: {POSTS_HEADERS}\n"
            f"Actual:   {header}"
        )

    def test_export_bot_logs_has_correct_header(self) -> None:
        """export_bot_logs harus menghasilkan header yang persis sesuai BOT_LOGS_HEADERS."""
        result = export_bot_logs([])
        header = _get_header_row(result)
        assert header == BOT_LOGS_HEADERS

    def test_export_interactions_has_correct_header(self) -> None:
        """export_interactions harus menghasilkan header yang persis sesuai INTERACTIONS_HEADERS."""
        result = export_interactions([])
        header = _get_header_row(result)
        assert header == INTERACTIONS_HEADERS

    def test_export_job_applications_has_correct_header(self) -> None:
        """export_job_applications harus menghasilkan header yang persis sesuai JOB_APPLICATIONS_HEADERS."""
        result = export_job_applications([])
        header = _get_header_row(result)
        assert header == JOB_APPLICATIONS_HEADERS

    def test_posts_header_contains_required_columns(self) -> None:
        """Header posts harus mengandung kolom-kolom penting: id, content, status, created_at."""
        required = {"id", "content", "status", "created_at", "content_type"}
        assert required.issubset(set(POSTS_HEADERS)), (
            f"Kolom wajib tidak ditemukan di POSTS_HEADERS: {required - set(POSTS_HEADERS)}"
        )

    def test_bot_logs_header_contains_required_columns(self) -> None:
        """Header bot_logs harus mengandung kolom-kolom penting."""
        required = {"id", "action", "status", "message", "created_at", "duration_ms"}
        assert required.issubset(set(BOT_LOGS_HEADERS))

    def test_interactions_header_contains_required_columns(self) -> None:
        """Header interactions harus mengandung kolom-kolom penting."""
        required = {
            "id", "target_post_url", "action_type", "content_sent", "status", "created_at"
        }
        assert required.issubset(set(INTERACTIONS_HEADERS))

    def test_job_applications_header_contains_required_columns(self) -> None:
        """Header job_applications harus mengandung kolom-kolom penting."""
        required = {
            "id", "job_title", "company", "job_url", "status", "created_at"
        }
        assert required.issubset(set(JOB_APPLICATIONS_HEADERS))

    def test_header_row_is_first_non_bom_content(self) -> None:
        """Baris pertama setelah BOM harus berupa header (bukan baris data)."""
        post_record = {
            "id": 1,
            "content": "Test konten",
            "status": "posted",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        result = export_posts([post_record])
        header = _get_header_row(result)
        # Header tidak boleh mengandung nilai numerik '1' sebagai elemen pertama
        assert header[0] == "id", (
            f"Elemen pertama header seharusnya 'id', bukan {header[0]!r}"
        )

    def test_header_count_matches_defined_headers(self) -> None:
        """Jumlah kolom di header CSV harus sama persis dengan panjang list header yang didefinisikan."""
        assert len(_get_header_row(export_posts([]))) == len(POSTS_HEADERS)
        assert len(_get_header_row(export_bot_logs([]))) == len(BOT_LOGS_HEADERS)
        assert len(_get_header_row(export_interactions([]))) == len(INTERACTIONS_HEADERS)
        assert len(_get_header_row(export_job_applications([]))) == len(JOB_APPLICATIONS_HEADERS)


# ---------------------------------------------------------------------------
# Tests: Data Row Count (Requirements 11.2)
# ---------------------------------------------------------------------------


class TestDataRowCount:
    """Jumlah baris data harus sesuai dengan jumlah record yang diberikan."""

    def test_export_posts_row_count_matches(
        self, sample_posts: List[Dict[str, Any]]
    ) -> None:
        """export_posts harus menghasilkan tepat 3 baris data untuk 3 record."""
        result = export_posts(sample_posts)
        assert _count_rows(result) == len(sample_posts), (
            f"Jumlah baris: expected {len(sample_posts)}, actual {_count_rows(result)}"
        )

    def test_export_bot_logs_row_count_matches(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """export_bot_logs harus menghasilkan tepat 4 baris data untuk 4 record."""
        result = export_bot_logs(sample_bot_logs)
        assert _count_rows(result) == len(sample_bot_logs)

    def test_export_interactions_row_count_matches(
        self, sample_interactions: List[Dict[str, Any]]
    ) -> None:
        """export_interactions harus menghasilkan tepat 3 baris data untuk 3 record."""
        result = export_interactions(sample_interactions)
        assert _count_rows(result) == len(sample_interactions)

    def test_export_job_applications_row_count_matches(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """export_job_applications harus menghasilkan tepat 4 baris data untuk 4 record."""
        result = export_job_applications(sample_job_applications)
        assert _count_rows(result) == len(sample_job_applications)

    def test_single_record_produces_one_data_row(self) -> None:
        """Satu record harus menghasilkan tepat satu baris data."""
        record = {
            "id": 1,
            "action": "publish_post",
            "status": "success",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        result = export_bot_logs([record])
        assert _count_rows(result) == 1

    def test_ten_records_produce_ten_data_rows(self) -> None:
        """Sepuluh record harus menghasilkan tepat 10 baris data."""
        records = [
            {"id": i, "action": "idle_wait", "status": "success",
             "created_at": "2024-01-01T00:00:00+00:00"}
            for i in range(1, 11)
        ]
        result = export_bot_logs(records)
        assert _count_rows(result) == 10

    def test_row_count_with_filtered_status_posted(
        self, sample_posts: List[Dict[str, Any]]
    ) -> None:
        """
        Setelah filter status='posted', jumlah baris di CSV harus sesuai
        dengan jumlah record yang lolos filter.
        Req 11.2: CSV_Exporter menghasilkan CSV dari data yang difilter.
        """
        filtered = _filter_by_status(sample_posts, "posted")
        result = export_posts(filtered)
        assert _count_rows(result) == len(filtered), (
            f"Harus ada {len(filtered)} baris 'posted', bukan {_count_rows(result)}"
        )
        # Dari sample_posts, hanya 1 yang berstatus 'posted'
        assert _count_rows(result) == 1

    def test_row_count_with_filtered_status_draft(
        self, sample_posts: List[Dict[str, Any]]
    ) -> None:
        """Setelah filter status='draft', jumlah baris CSV harus sesuai."""
        filtered = _filter_by_status(sample_posts, "draft")
        result = export_posts(filtered)
        assert _count_rows(result) == len(filtered)
        assert _count_rows(result) == 1

    def test_row_count_with_filtered_status_bot_logs_success(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """Setelah filter status='success' pada bot_logs, jumlah baris harus sesuai."""
        filtered = _filter_by_status(sample_bot_logs, "success")
        result = export_bot_logs(filtered)
        assert _count_rows(result) == len(filtered)
        # 2 log memiliki status 'success'
        assert _count_rows(result) == 2

    def test_row_count_with_filtered_status_job_applied(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """Setelah filter status='applied' pada job_applications, jumlah baris harus sesuai."""
        filtered = _filter_by_status(sample_job_applications, "applied")
        result = export_job_applications(filtered)
        assert _count_rows(result) == len(filtered)
        # 2 aplikasi memiliki status 'applied'
        assert _count_rows(result) == 2

    def test_row_count_with_date_range_filter(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """
        Setelah filter rentang tanggal, jumlah baris harus sesuai.
        Req 11.2: export data yang difilter menghasilkan jumlah baris yang tepat.
        """
        start = datetime(2024, 3, 1, tzinfo=timezone.utc)
        end = datetime(2024, 3, 2, 23, 59, 59, tzinfo=timezone.utc)

        filtered = _filter_by_date_range(sample_bot_logs, "created_at", start, end)
        result = export_bot_logs(filtered)

        assert _count_rows(result) == len(filtered)
        # task-001 (2024-03-01) dan task-002 (2024-03-02) → 2 baris
        assert _count_rows(result) == 2

    def test_row_count_strict_date_filter(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """Filter tanggal yang ketat (satu hari) harus menghasilkan lebih sedikit baris."""
        start = datetime(2024, 3, 3, tzinfo=timezone.utc)
        end = datetime(2024, 3, 3, 23, 59, 59, tzinfo=timezone.utc)

        filtered = _filter_by_date_range(sample_bot_logs, "created_at", start, end)
        result = export_bot_logs(filtered)

        # Hanya task-003 (2024-03-03) yang sesuai
        assert _count_rows(result) == 1

    def test_no_match_filter_produces_zero_data_rows(
        self, sample_posts: List[Dict[str, Any]]
    ) -> None:
        """Filter yang tidak cocok harus menghasilkan 0 baris data (hanya header)."""
        filtered = _filter_by_status(sample_posts, "nonexistent_status")
        result = export_posts(filtered)
        assert _count_rows(result) == 0


# ---------------------------------------------------------------------------
# Tests: Empty Dataset (Requirements 11.1, 11.4)
# ---------------------------------------------------------------------------


class TestEmptyDataset:
    """Dataset kosong harus menghasilkan CSV yang hanya berisi BOM + header."""

    def test_empty_posts_has_only_header(self) -> None:
        """export_posts([]) harus menghasilkan CSV dengan 0 baris data."""
        result = export_posts([])
        assert _count_rows(result) == 0

    def test_empty_bot_logs_has_only_header(self) -> None:
        """export_bot_logs([]) harus menghasilkan CSV dengan 0 baris data."""
        result = export_bot_logs([])
        assert _count_rows(result) == 0

    def test_empty_interactions_has_only_header(self) -> None:
        """export_interactions([]) harus menghasilkan CSV dengan 0 baris data."""
        result = export_interactions([])
        assert _count_rows(result) == 0

    def test_empty_job_applications_has_only_header(self) -> None:
        """export_job_applications([]) harus menghasilkan CSV dengan 0 baris data."""
        result = export_job_applications([])
        assert _count_rows(result) == 0

    def test_empty_posts_header_still_present(self) -> None:
        """Meskipun dataset kosong, header harus tetap ada."""
        result = export_posts([])
        header = _get_header_row(result)
        assert header == POSTS_HEADERS

    def test_empty_bot_logs_header_still_present(self) -> None:
        """Meskipun dataset kosong, header bot_logs harus tetap ada."""
        result = export_bot_logs([])
        header = _get_header_row(result)
        assert header == BOT_LOGS_HEADERS

    def test_empty_csv_still_starts_with_bom(self) -> None:
        """CSV dari dataset kosong harus tetap diawali BOM."""
        for exporter in [export_posts, export_bot_logs, export_interactions, export_job_applications]:
            result = exporter([])
            assert result[:3] == UTF8_BOM, (
                f"{exporter.__name__} dengan input kosong harus tetap menghasilkan BOM"
            )

    def test_empty_csv_parse_returns_empty_list(self) -> None:
        """parse_csv_bytes pada CSV kosong (hanya header) harus mengembalikan list kosong."""
        result = parse_csv_bytes(export_posts([]))
        assert result == []


# ---------------------------------------------------------------------------
# Tests: Field Values (nilai field dalam output CSV)
# ---------------------------------------------------------------------------


class TestFieldValues:
    """Nilai field dalam CSV harus mencerminkan nilai dari records input."""

    def test_post_content_preserved(self, sample_posts: List[Dict[str, Any]]) -> None:
        """Konten post harus tersimpan dengan benar dalam CSV."""
        result = export_posts(sample_posts)
        parsed = _decode_csv(result)
        assert parsed[0]["content"] == sample_posts[0]["content"]

    def test_post_status_values_correct(self, sample_posts: List[Dict[str, Any]]) -> None:
        """Status post harus tercermin dengan benar dalam CSV."""
        result = export_posts(sample_posts)
        parsed = _decode_csv(result)
        statuses = [row["status"] for row in parsed]
        assert statuses == ["posted", "draft", "scheduled"]

    def test_bot_log_action_preserved(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """Nilai field 'action' dalam bot_logs harus tersimpan."""
        result = export_bot_logs(sample_bot_logs)
        parsed = _decode_csv(result)
        assert parsed[0]["action"] == "publish_post"
        assert parsed[1]["action"] == "generate_comment"

    def test_none_value_becomes_empty_string(self) -> None:
        """Nilai None harus menjadi string kosong dalam CSV."""
        record = {
            "id": 1,
            "post_id": None,
            "task_id": "t-001",
            "action": "idle_wait",
            "status": "success",
            "message": None,
            "error_detail": None,
            "stack_trace": None,
            "screenshot_path": None,
            "duration_ms": None,
            "module": None,
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        result = export_bot_logs([record])
        parsed = _decode_csv(result)
        assert parsed[0]["post_id"] == ""
        assert parsed[0]["message"] == ""
        assert parsed[0]["error_detail"] == ""
        assert parsed[0]["module"] == ""

    def test_missing_field_becomes_empty_string(self) -> None:
        """Field yang tidak ada dalam record harus menjadi string kosong."""
        # Record yang hanya memiliki sebagian field
        minimal_record = {"id": 1, "status": "success"}
        result = export_bot_logs([minimal_record])
        parsed = _decode_csv(result)
        # Field yang tidak ada harus menjadi string kosong
        assert parsed[0]["action"] == ""
        assert parsed[0]["message"] == ""
        assert parsed[0]["duration_ms"] == ""

    def test_numeric_id_preserved_as_string(self) -> None:
        """ID numerik harus tersimpan sebagai string (karena CSV tidak punya tipe)."""
        record = {"id": 42, "status": "success", "action": "publish_post",
                  "created_at": "2024-01-01T00:00:00+00:00"}
        result = export_bot_logs([record])
        parsed = _decode_csv(result)
        assert parsed[0]["id"] == "42"

    def test_url_field_preserved(self, sample_interactions: List[Dict[str, Any]]) -> None:
        """URL dalam field target_post_url harus tersimpan dengan benar."""
        result = export_interactions(sample_interactions)
        parsed = _decode_csv(result)
        assert parsed[0]["target_post_url"] == "https://linkedin.com/posts/abc-123"

    def test_job_title_and_company_preserved(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """Job title dan company harus tersimpan dengan benar."""
        result = export_job_applications(sample_job_applications)
        parsed = _decode_csv(result)
        assert parsed[0]["job_title"] == "Backend Developer"
        assert parsed[0]["company"] == "PT Teknologi Maju"

    def test_boolean_field_preserved(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """Field boolean (has_easy_apply) harus tersimpan sebagai string representasi."""
        result = export_job_applications(sample_job_applications)
        parsed = _decode_csv(result)
        # True/False disimpan sebagai string
        assert parsed[0]["has_easy_apply"] in ("True", "False", "true", "false", "1", "0")

    def test_interaction_author_preserved(
        self, sample_interactions: List[Dict[str, Any]]
    ) -> None:
        """Nama penulis target harus tersimpan dengan benar."""
        result = export_interactions(sample_interactions)
        parsed = _decode_csv(result)
        assert parsed[0]["target_author"] == "Budi Santoso"

    def test_indonesian_text_preserved(self) -> None:
        """Teks bahasa Indonesia harus tersimpan dengan benar (UTF-8)."""
        record = {
            "id": 1,
            "target_post_url": "https://linkedin.com/posts/test",
            "target_author": "Budi Santoso",
            "target_post_text": "Semangat untuk terus berkarya dan berkembang!",
            "action_type": "comment",
            "content_sent": "Sangat menginspirasi, terima kasih banyak!",
            "status": "success",
            "skip_reason": None,
            "ai_provider_used": "deepseek",
            "screenshot_path": None,
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        result = export_interactions([record])
        parsed = _decode_csv(result)
        assert parsed[0]["target_post_text"] == "Semangat untuk terus berkarya dan berkembang!"
        assert parsed[0]["content_sent"] == "Sangat menginspirasi, terima kasih banyak!"

    def test_special_characters_properly_escaped(self) -> None:
        """
        Tanda kutip, koma, dan newline dalam field harus di-escape dengan benar
        agar CSV tetap valid dan dapat di-parse ulang.
        """
        record = {
            "id": 1,
            "action": "generate_comment",
            "status": "success",
            "message": 'Komentar berhasil: "Kerja keras, pantang menyerah!"',
            "error_detail": None,
            "stack_trace": None,
            "screenshot_path": None,
            "duration_ms": 500,
            "module": "C",
            "post_id": None,
            "task_id": "escape-test",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        result = export_bot_logs([record])
        parsed = _decode_csv(result)
        assert parsed[0]["message"] == 'Komentar berhasil: "Kerja keras, pantang menyerah!"'

    def test_content_with_comma_preserved(self) -> None:
        """Konten dengan koma di dalamnya harus tersimpan dengan benar dalam CSV."""
        record = {
            "id": 1,
            "content": "Tips 1, 2, dan 3 untuk sukses di LinkedIn.",
            "status": "draft",
            "content_type": "tips_list",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        result = export_posts([record])
        parsed = _decode_csv(result)
        assert parsed[0]["content"] == "Tips 1, 2, dan 3 untuk sukses di LinkedIn."


# ---------------------------------------------------------------------------
# Tests: All Required Columns Present (Requirements 11.1, 11.4)
# ---------------------------------------------------------------------------


class TestRequiredColumns:
    """Semua kolom yang diperlukan harus hadir untuk setiap entitas."""

    def test_posts_all_entity_columns_in_header(self) -> None:
        """
        Header posts harus mengandung semua kolom entitas yang diperlukan
        sesuai model Post dari Requirements.
        """
        expected_columns = {
            "id", "content", "content_type", "status",
            "created_at", "tone", "ai_provider_used",
        }
        assert expected_columns.issubset(set(POSTS_HEADERS)), (
            f"Kolom wajib tidak ditemukan: {expected_columns - set(POSTS_HEADERS)}"
        )

    def test_bot_logs_all_entity_columns_in_header(self) -> None:
        """
        Header bot_logs harus mengandung semua kolom yang relevan untuk audit trail
        sesuai Requirements 7.1.
        """
        expected_columns = {
            "id", "action", "status", "message",
            "error_detail", "duration_ms", "created_at",
        }
        assert expected_columns.issubset(set(BOT_LOGS_HEADERS))

    def test_interactions_all_entity_columns_in_header(self) -> None:
        """
        Header interactions harus mengandung kolom untuk melacak interaksi
        sesuai Requirements 4.6.
        """
        expected_columns = {
            "id", "target_post_url", "target_author",
            "action_type", "content_sent", "status", "created_at",
        }
        assert expected_columns.issubset(set(INTERACTIONS_HEADERS))

    def test_job_applications_all_entity_columns_in_header(self) -> None:
        """
        Header job_applications harus mengandung kolom untuk melacak lamaran
        sesuai Requirements 5.6.
        """
        expected_columns = {
            "id", "job_title", "company", "location",
            "job_url", "status", "applied_at", "created_at",
        }
        assert expected_columns.issubset(set(JOB_APPLICATIONS_HEADERS))

    def test_parsed_row_contains_all_header_keys(
        self, sample_posts: List[Dict[str, Any]]
    ) -> None:
        """
        Setiap baris yang di-parse dari CSV harus memiliki semua key header
        sebagai field (meskipun nilainya kosong).
        """
        result = export_posts(sample_posts)
        parsed = _decode_csv(result)

        for i, row in enumerate(parsed):
            missing = [h for h in POSTS_HEADERS if h not in row]
            assert not missing, (
                f"Baris {i}: field {missing} tidak ditemukan dalam row yang di-parse"
            )

    def test_bot_logs_parsed_row_contains_all_header_keys(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """Setiap baris bot_logs yang di-parse harus memiliki semua key header."""
        result = export_bot_logs(sample_bot_logs)
        parsed = _decode_csv(result)

        for i, row in enumerate(parsed):
            missing = [h for h in BOT_LOGS_HEADERS if h not in row]
            assert not missing, (
                f"Baris {i}: field {missing} tidak ditemukan dalam row yang di-parse"
            )

    def test_no_extra_columns_beyond_defined_headers(self) -> None:
        """CSV yang di-parse tidak boleh mengandung kolom di luar yang didefinisikan."""
        result = export_posts([{"id": 1, "status": "draft",
                                "created_at": "2024-01-01T00:00:00+00:00",
                                "extra_field": "nilai_ekstra"}])
        parsed = _decode_csv(result)
        if parsed:
            extra = [k for k in parsed[0] if k not in POSTS_HEADERS]
            assert not extra, (
                f"Kolom tak terduga ditemukan dalam CSV: {extra}"
            )


# ---------------------------------------------------------------------------
# Tests: Filter Scenarios (Requirements 11.2)
# ---------------------------------------------------------------------------


class TestFilterScenarios:
    """Skenario filter harus menghasilkan jumlah baris yang tepat."""

    def test_export_all_records_no_filter(
        self, sample_posts: List[Dict[str, Any]]
    ) -> None:
        """Tanpa filter, semua record harus diekspor."""
        result = export_posts(sample_posts)
        assert _count_rows(result) == 3

    def test_export_with_status_filter_reduces_rows(
        self, sample_posts: List[Dict[str, Any]]
    ) -> None:
        """Filter status harus mengurangi jumlah baris secara proporsional."""
        all_result = export_posts(sample_posts)
        filtered_posted = _filter_by_status(sample_posts, "posted")
        filtered_result = export_posts(filtered_posted)

        assert _count_rows(all_result) > _count_rows(filtered_result)
        assert _count_rows(filtered_result) == 1

    def test_export_with_empty_filter_result(
        self, sample_posts: List[Dict[str, Any]]
    ) -> None:
        """Filter yang tidak cocok menghasilkan 0 baris, bukan error."""
        filtered = _filter_by_status(sample_posts, "rejected")
        result = export_posts(filtered)
        assert _count_rows(result) == 0
        # Header tetap ada
        header = _get_header_row(result)
        assert header == POSTS_HEADERS

    def test_date_range_filter_reduces_bot_log_rows(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """Filter rentang tanggal yang lebih sempit harus menghasilkan lebih sedikit baris."""
        all_result = export_bot_logs(sample_bot_logs)

        # Filter ke satu hari saja
        start = datetime(2024, 3, 1, tzinfo=timezone.utc)
        end = datetime(2024, 3, 1, 23, 59, 59, tzinfo=timezone.utc)
        filtered = _filter_by_date_range(sample_bot_logs, "created_at", start, end)
        filtered_result = export_bot_logs(filtered)

        assert _count_rows(all_result) > _count_rows(filtered_result)
        assert _count_rows(filtered_result) == 1

    def test_combined_status_and_date_filter(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """Filter gabungan (status + tanggal) harus menghasilkan irisan yang benar."""
        start = datetime(2024, 3, 1, tzinfo=timezone.utc)
        end = datetime(2024, 3, 2, 23, 59, 59, tzinfo=timezone.utc)

        # Filter tanggal dulu, kemudian status
        date_filtered = _filter_by_date_range(
            sample_bot_logs, "created_at", start, end
        )
        combined_filtered = _filter_by_status(date_filtered, "success")

        result = export_bot_logs(combined_filtered)
        # Hanya log task-001 dan task-002 yang berada di rentang tanggal,
        # keduanya berstatus 'success' → 2 baris
        assert _count_rows(result) == 2

    def test_interactions_filter_by_status_skipped(
        self, sample_interactions: List[Dict[str, Any]]
    ) -> None:
        """Filter interactions dengan status='skipped' harus menghasilkan 1 baris."""
        filtered = _filter_by_status(sample_interactions, "skipped")
        result = export_interactions(filtered)
        assert _count_rows(result) == 1
        parsed = _decode_csv(result)
        assert parsed[0]["skip_reason"] == "teks_terlalu_pendek"

    def test_job_applications_filter_by_status_found(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """Filter job_applications dengan status='found' harus menghasilkan 1 baris."""
        filtered = _filter_by_status(sample_job_applications, "found")
        result = export_job_applications(filtered)
        assert _count_rows(result) == 1
        parsed = _decode_csv(result)
        assert parsed[0]["job_title"] == "Data Analyst"


# ---------------------------------------------------------------------------
# Tests: export_posts specific entity coverage (Requirements 11.1)
# ---------------------------------------------------------------------------


class TestExportPostsEntityCoverage:
    """Test coverage spesifik untuk export_posts."""

    def test_export_posts_is_callable_with_empty_list(self) -> None:
        """export_posts harus dapat dipanggil dengan list kosong tanpa error."""
        result = export_posts([])
        assert isinstance(result, bytes)

    def test_export_posts_posted_at_null_for_draft(self) -> None:
        """Post berstatus 'draft' harus memiliki posted_at kosong."""
        record = {
            "id": 2,
            "title": "Draft",
            "content": "Isi draft",
            "status": "draft",
            "posted_at": None,
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        result = export_posts([record])
        parsed = _decode_csv(result)
        assert parsed[0]["posted_at"] == ""

    def test_export_posts_posted_at_present_for_posted(self) -> None:
        """Post berstatus 'posted' harus memiliki posted_at yang terisi."""
        record = {
            "id": 1,
            "title": "Sudah diposting",
            "content": "Isi post",
            "status": "posted",
            "posted_at": "2024-03-01T10:00:00+00:00",
            "created_at": "2024-03-01T09:00:00+00:00",
        }
        result = export_posts([record])
        parsed = _decode_csv(result)
        assert parsed[0]["posted_at"] == "2024-03-01T10:00:00+00:00"

    def test_export_posts_image_url_field(self) -> None:
        """Field image_url harus tersimpan dengan benar."""
        record = {
            "id": 1,
            "status": "draft",
            "image_url": "https://images.example.com/promo.jpg",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        result = export_posts([record])
        parsed = _decode_csv(result)
        assert parsed[0]["image_url"] == "https://images.example.com/promo.jpg"


# ---------------------------------------------------------------------------
# Tests: export_bot_logs specific entity coverage (Requirements 11.1)
# ---------------------------------------------------------------------------


class TestExportBotLogsEntityCoverage:
    """Test coverage spesifik untuk export_bot_logs."""

    def test_export_bot_logs_error_detail_preserved(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """error_detail pada log yang gagal harus tersimpan."""
        result = export_bot_logs(sample_bot_logs)
        parsed = _decode_csv(result)
        # task-003 adalah failed log
        failed_row = next(r for r in parsed if r["status"] == "failed")
        assert "ADBTimeoutError" in failed_row["error_detail"]

    def test_export_bot_logs_screenshot_path_preserved(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """screenshot_path harus tersimpan untuk log yang memilikinya."""
        result = export_bot_logs(sample_bot_logs)
        parsed = _decode_csv(result)
        assert parsed[0]["screenshot_path"] == "/static/screenshots/001.png"

    def test_export_bot_logs_duration_ms_preserved(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """duration_ms harus tersimpan sebagai string."""
        result = export_bot_logs(sample_bot_logs)
        parsed = _decode_csv(result)
        assert parsed[0]["duration_ms"] == "4500"

    def test_export_bot_logs_module_field_preserved(
        self, sample_bot_logs: List[Dict[str, Any]]
    ) -> None:
        """Field 'module' harus tersimpan (A/B/C/D)."""
        result = export_bot_logs(sample_bot_logs)
        parsed = _decode_csv(result)
        modules = [row["module"] for row in parsed]
        assert "A" in modules
        assert "C" in modules


# ---------------------------------------------------------------------------
# Tests: export_interactions specific entity coverage (Requirements 11.1)
# ---------------------------------------------------------------------------


class TestExportInteractionsEntityCoverage:
    """Test coverage spesifik untuk export_interactions."""

    def test_export_interactions_skip_reason_preserved(
        self, sample_interactions: List[Dict[str, Any]]
    ) -> None:
        """skip_reason pada interaksi yang dilewati harus tersimpan."""
        result = export_interactions(sample_interactions)
        parsed = _decode_csv(result)
        skipped = next(r for r in parsed if r["status"] == "skipped")
        assert skipped["skip_reason"] == "teks_terlalu_pendek"

    def test_export_interactions_all_action_types_preserved(
        self, sample_interactions: List[Dict[str, Any]]
    ) -> None:
        """action_type harus tersimpan untuk setiap interaksi."""
        result = export_interactions(sample_interactions)
        parsed = _decode_csv(result)
        for row in parsed:
            assert row["action_type"] == "comment"

    def test_export_interactions_ai_provider_nullable(
        self, sample_interactions: List[Dict[str, Any]]
    ) -> None:
        """ai_provider_used yang None harus menjadi string kosong."""
        result = export_interactions(sample_interactions)
        parsed = _decode_csv(result)
        # Interaksi ke-2 tidak menggunakan AI (dilewati)
        skipped = next(r for r in parsed if r["status"] == "skipped")
        assert skipped["ai_provider_used"] == ""


# ---------------------------------------------------------------------------
# Tests: export_job_applications specific entity coverage (Requirements 11.1)
# ---------------------------------------------------------------------------


class TestExportJobApplicationsEntityCoverage:
    """Test coverage spesifik untuk export_job_applications."""

    def test_export_job_applications_applied_at_preserved(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """applied_at harus tersimpan untuk lamaran yang sudah diapply."""
        result = export_job_applications(sample_job_applications)
        parsed = _decode_csv(result)
        applied = [r for r in parsed if r["status"] == "applied"]
        for row in applied:
            assert row["applied_at"] != "", (
                "applied_at seharusnya tidak kosong untuk status='applied'"
            )

    def test_export_job_applications_job_url_preserved(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """job_url harus tersimpan dengan benar."""
        result = export_job_applications(sample_job_applications)
        parsed = _decode_csv(result)
        urls = [row["job_url"] for row in parsed]
        assert "https://linkedin.com/jobs/111" in urls

    def test_export_job_applications_salary_range_nullable(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """salary_range yang None harus menjadi string kosong."""
        result = export_job_applications(sample_job_applications)
        parsed = _decode_csv(result)
        found = next(r for r in parsed if r["status"] == "found")
        assert found["salary_range"] == ""

    def test_export_job_applications_search_session_id_preserved(
        self, sample_job_applications: List[Dict[str, Any]]
    ) -> None:
        """search_session_id harus tersimpan untuk pelacakan sesi."""
        result = export_job_applications(sample_job_applications)
        parsed = _decode_csv(result)
        session_ids = {row["search_session_id"] for row in parsed}
        assert "sess-001" in session_ids
        assert "sess-002" in session_ids


# ---------------------------------------------------------------------------
# Tests: parse_csv_bytes helper
# ---------------------------------------------------------------------------


class TestParseCsvBytes:
    """Test untuk fungsi helper parse_csv_bytes."""

    def test_parse_strips_bom_before_parsing(self) -> None:
        """parse_csv_bytes harus menghilangkan BOM sebelum parsing."""
        csv_bytes = export_posts([])
        # Jika BOM tidak di-strip, parsing akan gagal atau header akan salah
        parsed = parse_csv_bytes(csv_bytes)
        assert isinstance(parsed, list)

    def test_parse_empty_csv_returns_empty_list(self) -> None:
        """Parsing CSV kosong (hanya header) harus mengembalikan list kosong."""
        csv_bytes = export_interactions([])
        parsed = parse_csv_bytes(csv_bytes)
        assert parsed == []

    def test_parse_returns_list_of_dicts(self) -> None:
        """parse_csv_bytes harus mengembalikan list of dicts."""
        record = {"id": 1, "status": "success", "action": "idle_wait",
                  "created_at": "2024-01-01T00:00:00+00:00"}
        csv_bytes = export_bot_logs([record])
        parsed = parse_csv_bytes(csv_bytes)
        assert isinstance(parsed, list)
        assert all(isinstance(row, dict) for row in parsed)

    def test_parse_csv_without_bom_also_works(self) -> None:
        """parse_csv_bytes harus bekerja pada CSV yang tidak memiliki BOM."""
        # Buat CSV manual tanpa BOM
        csv_content = "id,status\r\n1,success\r\n"
        csv_bytes = csv_content.encode("utf-8")
        parsed = parse_csv_bytes(csv_bytes)
        assert len(parsed) == 1
        assert parsed[0]["id"] == "1"
        assert parsed[0]["status"] == "success"
