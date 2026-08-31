"""
CSV Exporter — Ekspor data entitas utama ke format CSV dengan UTF-8 BOM.

Komponen ini:
- Mendukung export terpisah untuk: posts, bot_logs, interactions, job_applications (Requirements 11.1)
- Menghasilkan CSV bytes dengan encoding UTF-8 BOM untuk kompatibilitas Excel (Requirements 11.3)
- Menyertakan baris header dengan nama kolom deskriptif (Requirements 11.4)
- Setiap fungsi menerima list dict plain Python agar testable tanpa DB (Requirements 11.2)

Round-trip property: exported CSV dapat di-parse kembali ke data setara (Requirements 11.5)
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Header definitions per entity
# ---------------------------------------------------------------------------

POSTS_HEADERS: List[str] = [
    "id",
    "title",
    "content",
    "content_type",
    "status",
    "platform",
    "image_url",
    "is_thread",
    "thread_count",
    "scheduled_at",
    "posted_at",
    "likes",
    "comments",
    "shares",
    "ai_provider_used",
    "tone",
    "linkedin_post_id",
    "created_at",
    "updated_at",
]

BOT_LOGS_HEADERS: List[str] = [
    "id",
    "post_id",
    "task_id",
    "action",
    "status",
    "message",
    "error_detail",
    "stack_trace",
    "screenshot_path",
    "duration_ms",
    "module",
    "created_at",
]

INTERACTIONS_HEADERS: List[str] = [
    "id",
    "target_post_url",
    "target_author",
    "target_post_text",
    "action_type",
    "content_sent",
    "status",
    "skip_reason",
    "ai_provider_used",
    "screenshot_path",
    "created_at",
]

JOB_APPLICATIONS_HEADERS: List[str] = [
    "id",
    "job_title",
    "company",
    "location",
    "salary_range",
    "job_url",
    "status",
    "has_easy_apply",
    "job_type",
    "applied_at",
    "notes",
    "search_session_id",
    "screenshot_path",
    "created_at",
    "updated_at",
]

# UTF-8 BOM prefix for Excel compatibility
UTF8_BOM = b"\xef\xbb\xbf"


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------


def _records_to_csv_bytes(
    headers: List[str],
    records: List[Dict[str, Any]],
) -> bytes:
    """
    Konversi list record (dict) ke bytes CSV dengan UTF-8 BOM.

    Args:
        headers: Daftar nama kolom header yang deskriptif.
        records: List dict yang mewakili baris data. Nilai yang tidak ada
                 di suatu record akan diisi string kosong.

    Returns:
        Bytes CSV dengan UTF-8 BOM prefix, header row, diikuti data rows.

    Requirements: 11.3, 11.4
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=headers,
        extrasaction="ignore",   # abaikan key yang tidak ada di headers
        lineterminator="\r\n",   # RFC 4180 line endings
    )
    writer.writeheader()
    for record in records:
        # Pastikan semua header ada (nilai kosong jika field tidak ada di record)
        row = {h: record.get(h, "") for h in headers}
        writer.writerow(row)

    csv_text = buffer.getvalue()
    return UTF8_BOM + csv_text.encode("utf-8")


# ---------------------------------------------------------------------------
# Public export functions
# ---------------------------------------------------------------------------


def export_posts(records: List[Dict[str, Any]]) -> bytes:
    """
    Ekspor data posts ke CSV bytes dengan UTF-8 BOM.

    Args:
        records: List dict posts. Setiap dict merepresentasikan satu baris post.
                 Key yang dikenali: id, title, content, content_type, status,
                 platform, image_url, is_thread, thread_count, scheduled_at,
                 posted_at, likes, comments, shares, ai_provider_used, tone,
                 linkedin_post_id, created_at, updated_at.

    Returns:
        Bytes CSV siap unduh, dimulai dengan UTF-8 BOM.

    Requirements: 11.1, 11.2, 11.3, 11.4
    """
    return _records_to_csv_bytes(POSTS_HEADERS, records)


def export_bot_logs(records: List[Dict[str, Any]]) -> bytes:
    """
    Ekspor data bot_logs ke CSV bytes dengan UTF-8 BOM.

    Args:
        records: List dict bot_logs. Key yang dikenali: id, post_id, task_id,
                 action, status, message, error_detail, stack_trace,
                 screenshot_path, duration_ms, module, created_at.

    Returns:
        Bytes CSV siap unduh, dimulai dengan UTF-8 BOM.

    Requirements: 11.1, 11.2, 11.3, 11.4
    """
    return _records_to_csv_bytes(BOT_LOGS_HEADERS, records)


def export_interactions(records: List[Dict[str, Any]]) -> bytes:
    """
    Ekspor data interactions ke CSV bytes dengan UTF-8 BOM.

    Args:
        records: List dict interactions. Key yang dikenali: id, target_post_url,
                 target_author, target_post_text, action_type, content_sent,
                 status, skip_reason, ai_provider_used, screenshot_path, created_at.

    Returns:
        Bytes CSV siap unduh, dimulai dengan UTF-8 BOM.

    Requirements: 11.1, 11.2, 11.3, 11.4
    """
    return _records_to_csv_bytes(INTERACTIONS_HEADERS, records)


def export_job_applications(records: List[Dict[str, Any]]) -> bytes:
    """
    Ekspor data job_applications ke CSV bytes dengan UTF-8 BOM.

    Args:
        records: List dict job_applications. Key yang dikenali: id, job_title,
                 company, location, salary_range, job_url, status, has_easy_apply,
                 job_type, applied_at, notes, search_session_id, screenshot_path,
                 created_at, updated_at.

    Returns:
        Bytes CSV siap unduh, dimulai dengan UTF-8 BOM.

    Requirements: 11.1, 11.2, 11.3, 11.4
    """
    return _records_to_csv_bytes(JOB_APPLICATIONS_HEADERS, records)


# ---------------------------------------------------------------------------
# Parse helper (for round-trip testing — Requirements 11.5)
# ---------------------------------------------------------------------------


def parse_csv_bytes(csv_bytes: bytes) -> List[Dict[str, str]]:
    """
    Parse CSV bytes (dengan atau tanpa UTF-8 BOM) kembali ke list dict.

    Digunakan untuk memverifikasi round-trip property: data yang diekspor
    dapat di-parse kembali ke data setara dengan data asli.

    Args:
        csv_bytes: Bytes CSV yang dihasilkan oleh fungsi export_* di atas.

    Returns:
        List dict di mana setiap dict merepresentasikan satu baris data,
        dengan key sesuai header CSV.

    Requirements: 11.5
    """
    # Strip UTF-8 BOM jika ada
    if csv_bytes.startswith(UTF8_BOM):
        csv_bytes = csv_bytes[len(UTF8_BOM):]

    text = csv_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]
