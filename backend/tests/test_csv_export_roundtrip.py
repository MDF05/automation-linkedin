"""
Property 4: Round-Trip — Export CSV

Validates: Requirements 11.2, 11.5

Rules verified:
- Data yang diekspor ke CSV lalu di-parse kembali harus menghasilkan nilai setara
  untuk semua field non-computed (round-trip property).
- parse_csv(export_csv(records)) ≈ records
- Berlaku untuk semua entitas: posts, bot_logs, interactions, job_applications.

Testing strategy:
- Menggunakan Hypothesis untuk generate N records dengan nilai arbitrary.
- Setiap field yang tidak ada di record diisi string kosong oleh exporter.
- Untuk field None, dibandingkan terhadap string kosong di CSV (karena CSV tidak
  memiliki konsep null — None → "" saat export).
- Field boolean (is_thread, has_easy_apply) di-export sebagai string repr Python
  ('True'/'False'), sehingga round-trip menghasilkan string, bukan bool asli.
- Timestamp/datetime di-export sebagai repr string; round-trip menghasilkan string.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.services.csv_exporter import (
    BOT_LOGS_HEADERS,
    INTERACTIONS_HEADERS,
    JOB_APPLICATIONS_HEADERS,
    POSTS_HEADERS,
    export_bot_logs,
    export_interactions,
    export_job_applications,
    export_posts,
    parse_csv_bytes,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# Text yang aman untuk CSV — menghindari karakter yang mempengaruhi parsing
_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters="-_.:/@#!?",
        blacklist_characters="\r\n\x00",
    ),
    min_size=0,
    max_size=200,
)

_optional_safe_text = st.one_of(st.none(), _safe_text)

_status_choices = st.sampled_from(["draft", "scheduled", "posted", "failed"])
_bot_action_choices = st.sampled_from([
    "generate_content", "publish_post", "screenshot",
    "scroll_feed", "read_ocr", "generate_comment", "post_comment",
    "open_linkedin", "idle_wait", "anti_ban_delay",
])
_bot_status_choices = st.sampled_from(["success", "failed", "running", "skipped", "timeout"])
_interaction_action_choices = st.sampled_from(["comment", "react", "share", "connect"])
_interaction_status_choices = st.sampled_from(["success", "failed", "skipped"])
_job_status_choices = st.sampled_from([
    "found", "applied", "skipped", "rejected",
    "interview", "offer", "skipped_incomplete_form", "skipped_no_easy_apply",
])
_optional_positive_int = st.one_of(st.none(), st.integers(min_value=0, max_value=999999))
_positive_int = st.integers(min_value=1, max_value=99999)

_timestamp_str = st.datetimes(
    min_value=datetime(2023, 1, 1),
    max_value=datetime(2030, 12, 31),
).map(lambda dt: dt.replace(tzinfo=timezone.utc).isoformat())


def _normalize(value: Any) -> str:
    """
    Normalisasi nilai record ke representasi string yang sama dengan
    yang dihasilkan oleh csv.DictWriter — None menjadi string kosong.
    """
    if value is None:
        return ""
    return str(value)


def _assert_round_trip(
    headers: List[str],
    original_records: List[Dict[str, Any]],
    parsed_records: List[Dict[str, str]],
) -> None:
    """
    Verifikasi bahwa setiap field non-computed dalam parsed_records setara
    dengan original_records setelah normalisasi.
    """
    assert len(parsed_records) == len(original_records), (
        f"Jumlah baris berbeda: original={len(original_records)}, "
        f"parsed={len(parsed_records)}"
    )

    for i, (orig, parsed) in enumerate(zip(original_records, parsed_records)):
        for field in headers:
            expected = _normalize(orig.get(field))
            actual = parsed.get(field, "")
            assert expected == actual, (
                f"Baris {i}, field '{field}': "
                f"expected={expected!r}, actual={actual!r}"
            )


# ---------------------------------------------------------------------------
# Strategies per entity
# ---------------------------------------------------------------------------


def _post_record_strategy():
    """Hasilkan satu dict record post yang valid."""
    return st.fixed_dictionaries({
        "id": _positive_int,
        "title": _optional_safe_text,
        "content": _safe_text,
        "content_type": st.sampled_from([
            "storytelling", "tips_list", "pertanyaan", "kutipan", "promo"
        ]),
        "status": _status_choices,
        "platform": st.just("linkedin"),
        "image_url": _optional_safe_text,
        "is_thread": st.booleans(),
        "thread_count": st.integers(min_value=1, max_value=10),
        "scheduled_at": _optional_safe_text,
        "posted_at": _optional_safe_text,
        "likes": st.integers(min_value=0, max_value=9999),
        "comments": st.integers(min_value=0, max_value=9999),
        "shares": st.integers(min_value=0, max_value=9999),
        "ai_provider_used": _optional_safe_text,
        "tone": _optional_safe_text,
        "linkedin_post_id": _optional_safe_text,
        "created_at": _timestamp_str,
        "updated_at": _timestamp_str,
    })


def _bot_log_record_strategy():
    """Hasilkan satu dict record bot_log yang valid."""
    return st.fixed_dictionaries({
        "id": _positive_int,
        "post_id": _optional_positive_int,
        "task_id": st.just(str(uuid.uuid4())),
        "action": _bot_action_choices,
        "status": _bot_status_choices,
        "message": _optional_safe_text,
        "error_detail": _optional_safe_text,
        "stack_trace": _optional_safe_text,
        "screenshot_path": _optional_safe_text,
        "duration_ms": _optional_positive_int,
        "module": st.one_of(st.none(), st.sampled_from(["A", "B", "C", "D"])),
        "created_at": _timestamp_str,
    })


def _interaction_record_strategy():
    """Hasilkan satu dict record interaction yang valid."""
    return st.fixed_dictionaries({
        "id": _positive_int,
        "target_post_url": _safe_text,
        "target_author": _optional_safe_text,
        "target_post_text": _optional_safe_text,
        "action_type": _interaction_action_choices,
        "content_sent": _optional_safe_text,
        "status": _interaction_status_choices,
        "skip_reason": _optional_safe_text,
        "ai_provider_used": _optional_safe_text,
        "screenshot_path": _optional_safe_text,
        "created_at": _timestamp_str,
    })


def _job_application_record_strategy():
    """Hasilkan satu dict record job_application yang valid."""
    return st.fixed_dictionaries({
        "id": _positive_int,
        "job_title": _safe_text,
        "company": _safe_text,
        "location": _optional_safe_text,
        "salary_range": _optional_safe_text,
        "job_url": _safe_text,
        "status": _job_status_choices,
        "has_easy_apply": st.booleans(),
        "job_type": _optional_safe_text,
        "applied_at": _optional_safe_text,
        "notes": _optional_safe_text,
        "search_session_id": _optional_safe_text,
        "screenshot_path": _optional_safe_text,
        "created_at": _timestamp_str,
        "updated_at": _timestamp_str,
    })


# ---------------------------------------------------------------------------
# Property tests — Round-Trip
# ---------------------------------------------------------------------------


@given(records=st.lists(_post_record_strategy(), min_size=1, max_size=50))
@h_settings(max_examples=100)
def test_posts_round_trip(records: List[Dict[str, Any]]) -> None:
    """
    **Property 4 — Validates: Requirements 11.2, 11.5**

    Export N post records ke CSV lalu parse kembali menghasilkan data setara.
    """
    csv_bytes = export_posts(records)

    # CSV harus diawali UTF-8 BOM
    assert csv_bytes[:3] == b"\xef\xbb\xbf", "CSV harus diawali dengan UTF-8 BOM"

    parsed = parse_csv_bytes(csv_bytes)
    _assert_round_trip(POSTS_HEADERS, records, parsed)


@given(records=st.lists(_bot_log_record_strategy(), min_size=1, max_size=50))
@h_settings(max_examples=100)
def test_bot_logs_round_trip(records: List[Dict[str, Any]]) -> None:
    """
    **Property 4 — Validates: Requirements 11.2, 11.5**

    Export N bot_log records ke CSV lalu parse kembali menghasilkan data setara.
    """
    csv_bytes = export_bot_logs(records)

    assert csv_bytes[:3] == b"\xef\xbb\xbf", "CSV harus diawali dengan UTF-8 BOM"

    parsed = parse_csv_bytes(csv_bytes)
    _assert_round_trip(BOT_LOGS_HEADERS, records, parsed)


@given(records=st.lists(_interaction_record_strategy(), min_size=1, max_size=50))
@h_settings(max_examples=100)
def test_interactions_round_trip(records: List[Dict[str, Any]]) -> None:
    """
    **Property 4 — Validates: Requirements 11.2, 11.5**

    Export N interaction records ke CSV lalu parse kembali menghasilkan data setara.
    """
    csv_bytes = export_interactions(records)

    assert csv_bytes[:3] == b"\xef\xbb\xbf", "CSV harus diawali dengan UTF-8 BOM"

    parsed = parse_csv_bytes(csv_bytes)
    _assert_round_trip(INTERACTIONS_HEADERS, records, parsed)


@given(records=st.lists(_job_application_record_strategy(), min_size=1, max_size=50))
@h_settings(max_examples=100)
def test_job_applications_round_trip(records: List[Dict[str, Any]]) -> None:
    """
    **Property 4 — Validates: Requirements 11.2, 11.5**

    Export N job_application records ke CSV lalu parse kembali menghasilkan data setara.
    """
    csv_bytes = export_job_applications(records)

    assert csv_bytes[:3] == b"\xef\xbb\xbf", "CSV harus diawali dengan UTF-8 BOM"

    parsed = parse_csv_bytes(csv_bytes)
    _assert_round_trip(JOB_APPLICATIONS_HEADERS, records, parsed)


@given(records=st.lists(_bot_log_record_strategy(), min_size=1, max_size=100))
@h_settings(max_examples=50)
def test_round_trip_preserves_row_count(records: List[Dict[str, Any]]) -> None:
    """
    **Property 4 — Validates: Requirements 11.2**

    Jumlah baris dalam CSV yang di-parse harus sama persis dengan jumlah record input.
    """
    csv_bytes = export_bot_logs(records)
    parsed = parse_csv_bytes(csv_bytes)
    assert len(parsed) == len(records), (
        f"Jumlah baris tidak cocok: input={len(records)}, parsed={len(parsed)}"
    )


@given(records=st.lists(_post_record_strategy(), min_size=1, max_size=50))
@h_settings(max_examples=50)
def test_round_trip_headers_present(records: List[Dict[str, Any]]) -> None:
    """
    **Property 4 — Validates: Requirements 11.4**

    Setiap field header harus tersedia sebagai key dalam hasil parse.
    """
    csv_bytes = export_posts(records)
    parsed = parse_csv_bytes(csv_bytes)

    if parsed:
        missing = [h for h in POSTS_HEADERS if h not in parsed[0]]
        assert not missing, f"Header tidak ditemukan di parsed CSV: {missing}"


# ---------------------------------------------------------------------------
# Edge-case unit tests
# ---------------------------------------------------------------------------


def test_empty_records_produces_header_only_csv() -> None:
    """
    Export list kosong menghasilkan CSV yang hanya berisi baris header (+ BOM).
    """
    csv_bytes = export_bot_logs([])
    assert csv_bytes[:3] == b"\xef\xbb\xbf"

    parsed = parse_csv_bytes(csv_bytes)
    assert parsed == [], f"CSV kosong seharusnya menghasilkan list kosong, bukan {parsed}"


def test_none_fields_become_empty_string_in_csv() -> None:
    """
    Field dengan nilai None dalam record harus menjadi string kosong setelah round-trip.
    """
    record = {
        "id": 1,
        "post_id": None,
        "task_id": "test-task-id",
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
    csv_bytes = export_bot_logs([record])
    parsed = parse_csv_bytes(csv_bytes)

    assert len(parsed) == 1
    assert parsed[0]["post_id"] == ""
    assert parsed[0]["message"] == ""
    assert parsed[0]["error_detail"] == ""
    assert parsed[0]["duration_ms"] == ""
    assert parsed[0]["module"] == ""


def test_utf8_bom_present_in_all_exporters() -> None:
    """
    Semua fungsi export harus menghasilkan bytes yang diawali UTF-8 BOM.
    Requirements: 11.3
    """
    BOM = b"\xef\xbb\xbf"

    assert export_posts([]).startswith(BOM)
    assert export_bot_logs([]).startswith(BOM)
    assert export_interactions([]).startswith(BOM)
    assert export_job_applications([]).startswith(BOM)


def test_unicode_text_survives_round_trip() -> None:
    """
    Teks Unicode (bahasa Indonesia, emoji-free) harus bertahan melalui round-trip CSV.
    """
    record = {
        "id": 42,
        "post_id": None,
        "task_id": "unicode-test",
        "action": "generate_comment",
        "status": "success",
        "message": "Berhasil membuat komentar: Semangat terus dalam berkarya!",
        "error_detail": None,
        "stack_trace": None,
        "screenshot_path": "/static/screenshots/test.png",
        "duration_ms": 1234,
        "module": "C",
        "created_at": "2024-06-15T10:30:00+07:00",
    }
    csv_bytes = export_bot_logs([record])
    parsed = parse_csv_bytes(csv_bytes)

    assert parsed[0]["message"] == record["message"]
    assert parsed[0]["screenshot_path"] == record["screenshot_path"]


def test_single_record_round_trip_all_exporters() -> None:
    """
    Smoke test: satu record per exporter harus melalui round-trip tanpa kehilangan data.
    """
    post = {
        "id": 1, "title": "Test Post", "content": "Isi konten", "content_type": "storytelling",
        "status": "draft", "platform": "linkedin", "image_url": None, "is_thread": False,
        "thread_count": 1, "scheduled_at": None, "posted_at": None, "likes": 0,
        "comments": 0, "shares": 0, "ai_provider_used": "deepseek", "tone": "profesional",
        "linkedin_post_id": None, "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }
    parsed_posts = parse_csv_bytes(export_posts([post]))
    assert parsed_posts[0]["title"] == "Test Post"
    assert parsed_posts[0]["content_type"] == "storytelling"
    assert parsed_posts[0]["status"] == "draft"

    interaction = {
        "id": 1, "target_post_url": "https://linkedin.com/posts/test",
        "target_author": "Budi Santoso", "target_post_text": "Konten inspiratif",
        "action_type": "comment", "content_sent": "Mantap sekali sharingnya!",
        "status": "success", "skip_reason": None, "ai_provider_used": "deepseek",
        "screenshot_path": None, "created_at": "2024-01-01T00:00:00+00:00",
    }
    parsed_interactions = parse_csv_bytes(export_interactions([interaction]))
    assert parsed_interactions[0]["target_author"] == "Budi Santoso"
    assert parsed_interactions[0]["content_sent"] == "Mantap sekali sharingnya!"

    job = {
        "id": 1, "job_title": "Software Engineer", "company": "Tech Corp",
        "location": "Jakarta", "salary_range": "10-15jt", "job_url": "https://linkedin.com/jobs/1",
        "status": "applied", "has_easy_apply": True, "job_type": "full-time",
        "applied_at": "2024-01-01T00:00:00+00:00", "notes": None,
        "search_session_id": "sess-001", "screenshot_path": None,
        "created_at": "2024-01-01T00:00:00+00:00", "updated_at": "2024-01-01T00:00:00+00:00",
    }
    parsed_jobs = parse_csv_bytes(export_job_applications([job]))
    assert parsed_jobs[0]["job_title"] == "Software Engineer"
    assert parsed_jobs[0]["company"] == "Tech Corp"
    assert parsed_jobs[0]["status"] == "applied"
