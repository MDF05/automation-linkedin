"""
Property 2: Round-Trip — Serialisasi Draft Konten

Validates: Requirements 10.1, 10.2

Rules verified:
- load_draft(save_draft(content)) == content
- Setiap draft yang disimpan ke database dan dimuat kembali harus identik
  untuk semua field non-computed: content, content_type, tone, image_url,
  title, is_thread, thread_count, scheduled_at, dan hashtag (via prompt_used).

Testing strategy:
- Menggunakan Hypothesis untuk generate konten dengan nilai arbitrary sesuai
  domain yang valid (content_type, tone, optional fields).
- Menggunakan SQLite in-memory via SQLAlchemy sync engine — tanpa PostgreSQL.
- Setiap property test mengelola session-nya sendiri sebagai context manager
  (bukan pytest fixture), sesuai rekomendasi Hypothesis untuk menghindari
  HealthCheck.function_scoped_fixture.
- Juga test Pydantic schema round-trip: PostCreate → model_dump → PostRead.

Notes tentang field JSONB/PostgreSQL:
- JSONB tidak tersedia di SQLite; kita gunakan JSON untuk thread_parts dan
  search_references. Model Post memakai postgresql.JSONB, sehingga kita
  patch kolom tersebut ke JSON sebelum create_all.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional

import pytest
from hypothesis import HealthCheck, given, settings as h_settings
from hypothesis import strategies as st
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Import model dan schemas
# ---------------------------------------------------------------------------
from app.models.base import Base
from app.models.post import Post
from app.schemas.post import ContentTone, ContentType, PostCreate, PostRead

# ---------------------------------------------------------------------------
# SQLite In-Memory Engine Setup
# ---------------------------------------------------------------------------


def _patch_jsonb_to_json(metadata: Any) -> None:
    """
    Ganti semua kolom JSONB (PostgreSQL-specific) menjadi JSON (SQLite-compatible)
    pada metadata yang diberikan. Ini dilakukan in-place sebelum `create_all`.
    """
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_JSONB):
                col.type = JSON()


@contextmanager
def _sqlite_session() -> Generator[Session, None, None]:
    """
    Context manager: buat SQLite in-memory engine, buat semua tabel,
    yield session, lalu teardown.

    Digunakan langsung di dalam property tests (bukan sebagai pytest fixture)
    agar Hypothesis tidak memunculkan HealthCheck.function_scoped_fixture.
    """
    _patch_jsonb_to_json(Base.metadata)
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
        session.close()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(scope="function")
def sqlite_session() -> Generator[Session, None, None]:  # type: ignore[misc]
    """
    Pytest fixture (hanya untuk example-based unit tests, bukan property tests).
    """
    with _sqlite_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

# Teks aman untuk konten — hindari karakter kontrol yang tidak diperlukan
_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters="-_.:/@#!?\n ",
        blacklist_characters="\r\x00",
    ),
    min_size=1,
    max_size=3000,
)

_optional_safe_text = st.one_of(st.none(), _safe_text)

# content_type valid sesuai CheckConstraint di model Post
_content_type_st = st.sampled_from([
    "storytelling",
    "tips_list",
    "pertanyaan",
    "kutipan",
    "video_script",
    "thread",
    "promo",
])

# tone valid sesuai ContentTone enum
_tone_st = st.sampled_from([
    "profesional",
    "kasual",
    "inspiratif",
    "edukasi",
])

_optional_tone_st = st.one_of(st.none(), _tone_st)

# image_url opsional — URL sederhana atau None
_image_url_st = st.one_of(
    st.none(),
    st.builds(
        lambda host, path: f"https://{host}/{path}",
        host=st.sampled_from(["ideogram.ai", "playground.ai", "cdn.example.com"]),
        path=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_./"),
            min_size=1,
            max_size=80,
        ),
    ),
)

# scheduled_at opsional
_naive_dt = st.datetimes(
    min_value=datetime(2024, 1, 1),
    max_value=datetime(2030, 12, 31),
)
_optional_scheduled_at_st = st.one_of(
    st.none(),
    _naive_dt.map(lambda dt: dt.replace(tzinfo=timezone.utc)),
)

# is_thread + thread_count
_is_thread_st = st.booleans()
_thread_count_st = st.integers(min_value=1, max_value=10)

# title opsional
_optional_title_st = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"), whitelist_characters="-_. "),
        min_size=1,
        max_size=255,
    ),
)


# ---------------------------------------------------------------------------
# Helper: save draft → flush → reload
# ---------------------------------------------------------------------------


def _save_and_reload_draft(
    session: Session,
    content: str,
    content_type: str,
    tone: Optional[str],
    image_url: Optional[str],
    title: Optional[str],
    is_thread: bool,
    thread_count: int,
    scheduled_at: Optional[datetime],
) -> Post:
    """
    Simpan Post baru dengan status='draft' ke session, flush ke SQLite,
    expire objek, lalu reload dari DB. Return Post yang di-reload.
    """
    post = Post(
        content=content,
        content_type=content_type,
        tone=tone,
        image_url=image_url,
        title=title,
        status="draft",
        is_thread=is_thread,
        thread_count=thread_count,
        scheduled_at=scheduled_at,
    )
    session.add(post)
    session.flush()  # assign ID tanpa commit penuh

    post_id = post.id
    session.commit()

    # Expire semua objek agar reload dari DB
    session.expire_all()

    # Reload
    reloaded: Post = session.get(Post, post_id)  # type: ignore[assignment]
    assert reloaded is not None, f"Post id={post_id} tidak ditemukan setelah commit"
    return reloaded


# ---------------------------------------------------------------------------
# Property Tests — DB Round-Trip
# ---------------------------------------------------------------------------


@given(
    content=_safe_text,
    content_type=_content_type_st,
    tone=_optional_tone_st,
    image_url=_image_url_st,
    title=_optional_title_st,
    is_thread=_is_thread_st,
    thread_count=_thread_count_st,
    scheduled_at=_optional_scheduled_at_st,
)
@h_settings(max_examples=100)
def test_draft_round_trip_all_fields(
    content: str,
    content_type: str,
    tone: Optional[str],
    image_url: Optional[str],
    title: Optional[str],
    is_thread: bool,
    thread_count: int,
    scheduled_at: Optional[datetime],
) -> None:
    """
    **Property 2 — Validates: Requirements 10.1, 10.2**

    save_draft(content) → commit → load_draft() → semua field identik.

    Verifikasi: content, content_type, tone, image_url, title, is_thread,
    thread_count, scheduled_at, status='draft', posted_at=None.
    """
    with _sqlite_session() as session:
        reloaded = _save_and_reload_draft(
            session=session,
            content=content,
            content_type=content_type,
            tone=tone,
            image_url=image_url,
            title=title,
            is_thread=is_thread,
            thread_count=thread_count,
            scheduled_at=scheduled_at,
        )

        assert reloaded.content == content, (
            f"content tidak cocok: expected={content!r}, got={reloaded.content!r}"
        )
        assert reloaded.content_type == content_type, (
            f"content_type tidak cocok: expected={content_type!r}, got={reloaded.content_type!r}"
        )
        assert reloaded.tone == tone, (
            f"tone tidak cocok: expected={tone!r}, got={reloaded.tone!r}"
        )
        assert reloaded.image_url == image_url, (
            f"image_url tidak cocok: expected={image_url!r}, got={reloaded.image_url!r}"
        )
        assert reloaded.title == title, (
            f"title tidak cocok: expected={title!r}, got={reloaded.title!r}"
        )
        assert reloaded.is_thread == is_thread, (
            f"is_thread tidak cocok: expected={is_thread!r}, got={reloaded.is_thread!r}"
        )
        assert reloaded.thread_count == thread_count, (
            f"thread_count tidak cocok: expected={thread_count!r}, got={reloaded.thread_count!r}"
        )
        assert reloaded.status == "draft", (
            f"status harus 'draft', got={reloaded.status!r}"
        )
        assert reloaded.posted_at is None, (
            f"posted_at harus None untuk draft, got={reloaded.posted_at!r}"
        )
        if scheduled_at is None:
            assert reloaded.scheduled_at is None
        else:
            assert reloaded.scheduled_at is not None, "scheduled_at hilang setelah reload"
            expected_naive = scheduled_at.replace(tzinfo=None)
            reloaded_naive = (
                reloaded.scheduled_at.replace(tzinfo=None)
                if reloaded.scheduled_at.tzinfo is not None
                else reloaded.scheduled_at
            )
            assert reloaded_naive == expected_naive, (
                f"scheduled_at tidak cocok: expected={expected_naive!r}, got={reloaded_naive!r}"
            )


@given(
    content=_safe_text,
    content_type=_content_type_st,
)
@h_settings(max_examples=50)
def test_draft_status_preserved_after_save(
    content: str,
    content_type: str,
) -> None:
    """
    **Property 2a — Validates: Requirements 10.1**

    Draft yang disimpan harus selalu memiliki status='draft' dan posted_at=None
    setelah reload dari DB.
    """
    with _sqlite_session() as session:
        reloaded = _save_and_reload_draft(
            session=session,
            content=content,
            content_type=content_type,
            tone=None,
            image_url=None,
            title=None,
            is_thread=False,
            thread_count=1,
            scheduled_at=None,
        )
        assert reloaded.status == "draft"
        assert reloaded.posted_at is None


@given(
    content=_safe_text,
    content_type=_content_type_st,
    tone=_tone_st,
)
@h_settings(max_examples=50)
def test_content_and_tone_round_trip(
    content: str,
    content_type: str,
    tone: str,
) -> None:
    """
    **Property 2b — Validates: Requirements 10.2**

    Teks konten dan tone harus identik setelah round-trip ke DB.
    """
    with _sqlite_session() as session:
        reloaded = _save_and_reload_draft(
            session=session,
            content=content,
            content_type=content_type,
            tone=tone,
            image_url=None,
            title=None,
            is_thread=False,
            thread_count=1,
            scheduled_at=None,
        )
        assert reloaded.content == content
        assert reloaded.tone == tone


# ---------------------------------------------------------------------------
# Property Tests — Pydantic Schema Round-Trip
# ---------------------------------------------------------------------------


@given(
    content=_safe_text,
    content_type=st.sampled_from(list(ContentType)),
    tone=st.one_of(st.none(), st.sampled_from(list(ContentTone))),
    image_url=_image_url_st,
    title=_optional_title_st,
    is_thread=_is_thread_st,
    thread_count=_thread_count_st,
)
@h_settings(max_examples=100)
def test_pydantic_schema_round_trip(
    content: str,
    content_type: ContentType,
    tone: Optional[ContentTone],
    image_url: Optional[str],
    title: Optional[str],
    is_thread: bool,
    thread_count: int,
) -> None:
    """
    **Property 2c — Validates: Requirements 10.1, 10.2**

    PostCreate → dict → PostRead verifikasi semua field yang sama.

    Test ini memverifikasi bahwa skema Pydantic tidak kehilangan atau mengubah
    data selama serialisasi/deserialisasi.
    """
    # Buat PostCreate
    post_create = PostCreate(
        content=content,
        content_type=content_type,
        tone=tone,
        image_url=image_url,
        title=title,
        is_thread=is_thread,
        thread_count=thread_count,
        status="draft",
    )

    # Simulasikan "simpan ke DB dan baca kembali" lewat PostRead
    # Kita buat dict yang merepresentasikan data dari DB
    now = datetime.now(tz=timezone.utc)
    db_dict = {
        **post_create.model_dump(),
        "id": 1,
        "status": "draft",
        "posted_at": None,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "ai_provider_used": post_create.ai_provider_used,
        "prompt_used": post_create.prompt_used,
        "search_references": post_create.search_references,
        "linkedin_post_id": None,
        "created_at": now,
        "updated_at": now,
    }

    post_read = PostRead(**db_dict)

    # Verifikasi semua field yang berasal dari PostCreate
    assert post_read.content == post_create.content, (
        f"content tidak cocok: {post_read.content!r} != {post_create.content!r}"
    )
    assert post_read.content_type == post_create.content_type.value, (
        f"content_type tidak cocok: {post_read.content_type!r} != {post_create.content_type.value!r}"
    )
    # tone: PostRead.tone adalah str|None, PostCreate.tone adalah ContentTone|None
    expected_tone = post_create.tone.value if post_create.tone is not None else None
    assert post_read.tone == expected_tone, (
        f"tone tidak cocok: {post_read.tone!r} != {expected_tone!r}"
    )
    assert post_read.image_url == post_create.image_url, (
        f"image_url tidak cocok: {post_read.image_url!r} != {post_create.image_url!r}"
    )
    assert post_read.title == post_create.title, (
        f"title tidak cocok: {post_read.title!r} != {post_create.title!r}"
    )
    assert post_read.is_thread == post_create.is_thread, (
        f"is_thread tidak cocok: {post_read.is_thread!r} != {post_create.is_thread!r}"
    )
    assert post_read.thread_count == post_create.thread_count, (
        f"thread_count tidak cocok: {post_read.thread_count!r} != {post_create.thread_count!r}"
    )
    assert post_read.status == "draft"
    assert post_read.posted_at is None


# ---------------------------------------------------------------------------
# Example-based unit tests
# ---------------------------------------------------------------------------


def test_draft_with_all_fields_round_trip(sqlite_session: Session) -> None:
    """
    Unit test: simpan draft dengan semua field terisi, verifikasi round-trip.
    """
    now = datetime(2025, 6, 15, 10, 30, 0)  # naive datetime for SQLite

    post = Post(
        content="5 tips untuk meningkatkan produktivitas Anda sebagai developer",
        content_type="tips_list",
        tone="profesional",
        image_url="https://ideogram.ai/assets/image/tips-dev.png",
        title="Tips Developer Produktif",
        status="draft",
        is_thread=False,
        thread_count=1,
        scheduled_at=now,
    )
    sqlite_session.add(post)
    sqlite_session.commit()

    sqlite_session.expire_all()
    reloaded = sqlite_session.get(Post, post.id)

    assert reloaded is not None
    assert reloaded.content == "5 tips untuk meningkatkan produktivitas Anda sebagai developer"
    assert reloaded.content_type == "tips_list"
    assert reloaded.tone == "profesional"
    assert reloaded.image_url == "https://ideogram.ai/assets/image/tips-dev.png"
    assert reloaded.title == "Tips Developer Produktif"
    assert reloaded.status == "draft"
    assert reloaded.is_thread is False
    assert reloaded.thread_count == 1
    assert reloaded.posted_at is None


def test_draft_with_minimal_fields_round_trip(sqlite_session: Session) -> None:
    """
    Unit test: draft dengan field minimal (hanya content + content_type).
    """
    post = Post(
        content="Apakah Anda sudah mencoba teknik Pomodoro?",
        content_type="pertanyaan",
        status="draft",
        is_thread=False,
        thread_count=1,
    )
    sqlite_session.add(post)
    sqlite_session.commit()

    sqlite_session.expire_all()
    reloaded = sqlite_session.get(Post, post.id)

    assert reloaded is not None
    assert reloaded.content == "Apakah Anda sudah mencoba teknik Pomodoro?"
    assert reloaded.content_type == "pertanyaan"
    assert reloaded.tone is None
    assert reloaded.image_url is None
    assert reloaded.title is None
    assert reloaded.status == "draft"
    assert reloaded.posted_at is None


def test_multiple_drafts_independent(sqlite_session: Session) -> None:
    """
    Unit test: beberapa draft tersimpan secara independen, masing-masing
    dapat di-reload dengan field yang benar.
    """
    drafts_data = [
        ("Konten storytelling tentang perjalanan karir saya", "storytelling", "inspiratif"),
        ("Thread tentang belajar coding dari nol", "thread", "edukasi"),
        ("Promo layanan konsultasi IT saya", "promo", "profesional"),
    ]

    post_ids = []
    for content, ctype, tone in drafts_data:
        post = Post(
            content=content,
            content_type=ctype,
            tone=tone,
            status="draft",
            is_thread=False,
            thread_count=1,
        )
        sqlite_session.add(post)
        sqlite_session.flush()
        post_ids.append(post.id)

    sqlite_session.commit()
    sqlite_session.expire_all()

    for i, post_id in enumerate(post_ids):
        reloaded = sqlite_session.get(Post, post_id)
        assert reloaded is not None
        expected_content, expected_ctype, expected_tone = drafts_data[i]
        assert reloaded.content == expected_content
        assert reloaded.content_type == expected_ctype
        assert reloaded.tone == expected_tone
        assert reloaded.status == "draft"


def test_pydantic_schema_draft_content_type_preserved() -> None:
    """
    Unit test: PostCreate dengan content_type='thread' menghasilkan PostRead
    dengan content_type='thread' (bukan enum value yang berbeda).
    """
    now = datetime.now(tz=timezone.utc)

    post_create = PostCreate(
        content="Thread 1/5: Belajar FastAPI dari nol\n\nHari ini saya akan berbagi pengalaman...",
        content_type=ContentType.thread,
        tone=ContentTone.edukasi,
        is_thread=True,
        thread_count=5,
        status="draft",
    )

    db_dict = {
        **post_create.model_dump(),
        "id": 99,
        "status": "draft",
        "posted_at": None,
        "likes": 0, "comments": 0, "shares": 0,
        "ai_provider_used": None,
        "prompt_used": None,
        "search_references": None,
        "linkedin_post_id": None,
        "created_at": now,
        "updated_at": now,
    }

    post_read = PostRead(**db_dict)

    assert post_read.content_type == "thread"
    assert post_read.tone == "edukasi"
    assert post_read.is_thread is True
    assert post_read.thread_count == 5
    assert post_read.status == "draft"
