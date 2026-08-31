"""
Property 3: Invariant — Kelengkapan Log

Validates: Requirements 2.8, 7.1

Rules verified:
- Setiap post dengan status='posted' HARUS memiliki minimal satu entri
  di tabel bot_logs dengan action='publish_post' dan status='success'.
- Secara formal: count(bot_logs action='publish_post' success) >= count(posts status='posted')
- Post dengan status='draft' atau 'failed' TIDAK membutuhkan success log.

Testing strategy:
- Menggunakan Hypothesis untuk generate N posts dengan status='posted' beserta
  corresponding bot_logs action='publish_post', status='success'.
- Menggunakan SQLite in-memory via SQLAlchemy sync engine — tanpa PostgreSQL.
- Setiap property test mengelola session-nya sendiri sebagai context manager
  (bukan pytest fixture), sesuai rekomendasi Hypothesis untuk menghindari
  HealthCheck.function_scoped_fixture.
- Juga test negative: post 'posted' tanpa success log → invariant violated.
- Juga test: post 'draft'/'failed' tidak memerlukan success log.

Notes tentang field JSONB/PostgreSQL:
- JSONB tidak tersedia di SQLite; kita gunakan JSON.
- Model Post dan BotLog memakai postgresql.JSONB, sehingga kita patch kolom
  tersebut ke JSON sebelum create_all (sama seperti test_content_draft_roundtrip.py).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, List

import pytest
from hypothesis import HealthCheck, given, settings as h_settings
from hypothesis import strategies as st
from sqlalchemy import JSON, create_engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Import model
# ---------------------------------------------------------------------------
from app.models.base import Base
from app.models.bot_log import BotLog
from app.models.post import Post

# ---------------------------------------------------------------------------
# SQLite In-Memory Setup (identical pattern to test_content_draft_roundtrip.py)
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
# Helpers
# ---------------------------------------------------------------------------

_CONTENT_TYPES = [
    "storytelling",
    "tips_list",
    "pertanyaan",
    "kutipan",
    "video_script",
    "thread",
    "promo",
]

_NOW = datetime(2025, 1, 1, 12, 0, 0)  # naive UTC for SQLite


def _make_posted_post(session: Session, content: str = "Test konten LinkedIn") -> Post:
    """Buat dan simpan Post dengan status='posted' ke session."""
    post = Post(
        content=content,
        content_type="storytelling",
        status="posted",
        is_thread=False,
        thread_count=1,
        posted_at=_NOW,
    )
    session.add(post)
    session.flush()
    return post


def _make_success_log(session: Session, post_id: int) -> BotLog:
    """Buat dan simpan BotLog action='publish_post', status='success'."""
    log = BotLog(
        post_id=post_id,
        task_id=str(uuid.uuid4()),
        action="publish_post",
        status="success",
        message="Post berhasil dipublikasikan",
        duration_ms=1200,
    )
    session.add(log)
    session.flush()
    return log


def _count_posted_posts(session: Session) -> int:
    """Hitung jumlah post dengan status='posted'."""
    return session.query(Post).filter(Post.status == "posted").count()


def _count_success_publish_logs(session: Session) -> int:
    """Hitung jumlah bot_logs dengan action='publish_post' dan status='success'."""
    return (
        session.query(BotLog)
        .filter(BotLog.action == "publish_post", BotLog.status == "success")
        .count()
    )


def _check_log_completeness_invariant(session: Session) -> bool:
    """
    Invariant: setiap post status='posted' harus memiliki minimal 1 bot_log
    action='publish_post' status='success'.

    Returns True jika invariant terpenuhi, False jika violated.
    """
    posted_posts = session.query(Post).filter(Post.status == "posted").all()
    for post in posted_posts:
        success_log_count = (
            session.query(BotLog)
            .filter(
                BotLog.post_id == post.id,
                BotLog.action == "publish_post",
                BotLog.status == "success",
            )
            .count()
        )
        if success_log_count < 1:
            return False
    return True


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters="-_.:/@#!?\n ",
        blacklist_characters="\r\x00",
    ),
    min_size=1,
    max_size=500,
)

_content_type_st = st.sampled_from(_CONTENT_TYPES)

# Jumlah posted posts: antara 1-5 untuk test yang cukup beragam tanpa terlalu lambat
_n_posts_st = st.integers(min_value=1, max_value=5)

# Status non-posted
_non_posted_status_st = st.sampled_from(["draft", "failed", "scheduled"])


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


@given(
    n_posts=_n_posts_st,
    contents=st.lists(_safe_text, min_size=1, max_size=5),
)
@h_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_log_completeness_invariant_holds_with_success_logs(
    n_posts: int,
    contents: List[str],
) -> None:
    """
    **Property 3 — Validates: Requirements 2.8, 7.1**

    Untuk setiap N post dengan status='posted' yang masing-masing memiliki
    minimal satu bot_log action='publish_post' status='success', invariant
    kelengkapan log HARUS terpenuhi:
      count(bot_logs action='publish_post' success) >= count(posts status='posted')

    Juga verifikasi per-post: setiap posted post memiliki tepat 1 success log.
    """
    # Pastikan jumlah konten cukup — pad jika perlu
    content_pool = contents * (n_posts // len(contents) + 1)

    with _sqlite_session() as session:
        post_ids = []
        for i in range(n_posts):
            post = _make_posted_post(session, content=content_pool[i])
            post_ids.append(post.id)

        # Buat 1 success log per posted post
        for post_id in post_ids:
            _make_success_log(session, post_id=post_id)

        session.commit()

        # Verifikasi invariant aggregat
        posted_count = _count_posted_posts(session)
        success_log_count = _count_success_publish_logs(session)

        assert success_log_count >= posted_count, (
            f"Invariant violated: {success_log_count} success logs < "
            f"{posted_count} posted posts"
        )

        # Verifikasi invariant per-post
        assert _check_log_completeness_invariant(session), (
            "Per-post invariant violated: ada posted post tanpa success log"
        )


@given(
    n_posts=_n_posts_st,
    contents=st.lists(_safe_text, min_size=1, max_size=5),
)
@h_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_log_completeness_invariant_violated_without_success_logs(
    n_posts: int,
    contents: List[str],
) -> None:
    """
    **Property 3 (negative) — Validates: Requirements 2.8, 7.1**

    Jika ada post dengan status='posted' tetapi TIDAK ada bot_log
    action='publish_post' status='success', maka sistem deteksi invariant
    HARUS mendeteksi pelanggaran tersebut (return False).

    Test ini memverifikasi bahwa fungsi pengecekan invariant bekerja benar.
    """
    content_pool = contents * (n_posts // len(contents) + 1)

    with _sqlite_session() as session:
        # Buat posted posts TANPA success logs
        for i in range(n_posts):
            _make_posted_post(session, content=content_pool[i])

        session.commit()

        # Invariant HARUS violated (return False) karena tidak ada success log
        invariant_ok = _check_log_completeness_invariant(session)
        assert not invariant_ok, (
            f"Expected invariant violation: {n_posts} posted posts tanpa success log "
            f"seharusnya mendeteksi pelanggaran, tapi invariant dinyatakan OK"
        )


@given(
    n_non_posted=st.integers(min_value=1, max_value=5),
    statuses=st.lists(
        st.sampled_from(["draft", "failed"]),
        min_size=1,
        max_size=5,
    ),
    content=_safe_text,
)
@h_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_non_posted_posts_do_not_require_success_logs(
    n_non_posted: int,
    statuses: List[str],
    content: str,
) -> None:
    """
    **Property 3 (non-posted variant) — Validates: Requirements 2.8, 7.1**

    Post dengan status='draft' atau 'failed' TIDAK memerlukan success log.
    Invariant HARUS terpenuhi (return True) meski tidak ada bot_log apapun,
    selama tidak ada posted posts.
    """
    status_pool = statuses * (n_non_posted // len(statuses) + 1)

    with _sqlite_session() as session:
        for i in range(n_non_posted):
            status = status_pool[i]
            post = Post(
                content=content,
                content_type="storytelling",
                status=status,
                is_thread=False,
                thread_count=1,
                # posted_at hanya diset untuk 'posted', bukan draft/failed
                posted_at=_NOW if status == "posted" else None,
            )
            session.add(post)

        session.commit()

        # Tidak ada posted posts → invariant trivially satisfied (vacuously true)
        invariant_ok = _check_log_completeness_invariant(session)
        assert invariant_ok, (
            f"Invariant harus terpenuhi untuk non-posted posts "
            f"(draft/failed tidak memerlukan success log)"
        )


@given(
    n_posted=_n_posts_st,
    n_draft=st.integers(min_value=0, max_value=3),
    n_failed=st.integers(min_value=0, max_value=3),
    contents=st.lists(_safe_text, min_size=1, max_size=5),
)
@h_settings(max_examples=80, suppress_health_check=[HealthCheck.too_slow])
def test_mixed_statuses_invariant_only_requires_logs_for_posted(
    n_posted: int,
    n_draft: int,
    n_failed: int,
    contents: List[str],
) -> None:
    """
    **Property 3 (mixed status) — Validates: Requirements 2.8, 7.1**

    Dengan campuran post status='posted', 'draft', dan 'failed':
    - Hanya posted posts yang memerlukan success log
    - Draft dan failed posts TIDAK perlu success log
    - Invariant terpenuhi jika dan hanya jika semua posted posts punya success log
    """
    total = n_posted + n_draft + n_failed
    if total == 0:
        return  # skip trivial case

    content_pool = contents * (total // len(contents) + 1)
    idx = 0

    with _sqlite_session() as session:
        posted_ids = []

        # Buat posted posts
        for _ in range(n_posted):
            post = Post(
                content=content_pool[idx],
                content_type="storytelling",
                status="posted",
                is_thread=False,
                thread_count=1,
                posted_at=_NOW,
            )
            session.add(post)
            session.flush()
            posted_ids.append(post.id)
            idx += 1

        # Buat draft posts (tidak butuh success log)
        for _ in range(n_draft):
            post = Post(
                content=content_pool[idx],
                content_type="tips_list",
                status="draft",
                is_thread=False,
                thread_count=1,
            )
            session.add(post)
            idx += 1

        # Buat failed posts (tidak butuh success log)
        for _ in range(n_failed):
            post = Post(
                content=content_pool[idx],
                content_type="pertanyaan",
                status="failed",
                is_thread=False,
                thread_count=1,
            )
            session.add(post)
            idx += 1

        # Buat success log hanya untuk posted posts
        for post_id in posted_ids:
            _make_success_log(session, post_id=post_id)

        session.commit()

        # Verifikasi aggregat: success logs >= posted posts
        posted_count = _count_posted_posts(session)
        success_log_count = _count_success_publish_logs(session)

        assert success_log_count >= posted_count, (
            f"Aggregat invariant violated: {success_log_count} success logs "
            f"< {posted_count} posted posts"
        )

        # Verifikasi per-post
        assert _check_log_completeness_invariant(session), (
            "Per-post invariant violated dalam mixed-status scenario"
        )

        # Verifikasi bahwa draft/failed posts TIDAK memiliki success log
        # (pastikan test tidak secara tidak sengaja membuat log untuk mereka)
        all_posts = session.query(Post).filter(
            Post.status.in_(["draft", "failed"])
        ).all()
        for non_posted in all_posts:
            log_count = (
                session.query(BotLog)
                .filter(
                    BotLog.post_id == non_posted.id,
                    BotLog.action == "publish_post",
                    BotLog.status == "success",
                )
                .count()
            )
            assert log_count == 0, (
                f"Post status={non_posted.status!r} id={non_posted.id} "
                f"tidak seharusnya memiliki success log"
            )


# ---------------------------------------------------------------------------
# Example-based unit tests
# ---------------------------------------------------------------------------


def test_single_posted_post_with_success_log_satisfies_invariant(
    sqlite_session: Session,
) -> None:
    """
    Unit test: 1 posted post + 1 success log → invariant terpenuhi.
    """
    post = _make_posted_post(sqlite_session, content="Konten posting tunggal")
    _make_success_log(sqlite_session, post_id=post.id)
    sqlite_session.commit()

    assert _check_log_completeness_invariant(sqlite_session)
    assert _count_posted_posts(sqlite_session) == 1
    assert _count_success_publish_logs(sqlite_session) == 1


def test_posted_post_without_success_log_violates_invariant(
    sqlite_session: Session,
) -> None:
    """
    Unit test: 1 posted post tanpa success log → invariant violated.
    """
    _make_posted_post(sqlite_session, content="Post tanpa log")
    sqlite_session.commit()

    assert not _check_log_completeness_invariant(sqlite_session), (
        "Harus mendeteksi violation: posted post tanpa success log"
    )


def test_multiple_posted_posts_all_with_success_logs(
    sqlite_session: Session,
) -> None:
    """
    Unit test: 3 posted posts masing-masing punya 1 success log → invariant OK.
    """
    for i in range(3):
        post = _make_posted_post(sqlite_session, content=f"Konten post ke-{i + 1}")
        _make_success_log(sqlite_session, post_id=post.id)

    sqlite_session.commit()

    assert _check_log_completeness_invariant(sqlite_session)
    assert _count_posted_posts(sqlite_session) == 3
    assert _count_success_publish_logs(sqlite_session) == 3


def test_one_of_multiple_posted_posts_missing_log_violates_invariant(
    sqlite_session: Session,
) -> None:
    """
    Unit test: 3 posted posts, hanya 2 yang punya success log → invariant violated.
    """
    posts = []
    for i in range(3):
        post = _make_posted_post(sqlite_session, content=f"Konten post ke-{i + 1}")
        posts.append(post)

    # Buat success log hanya untuk 2 dari 3 post
    _make_success_log(sqlite_session, post_id=posts[0].id)
    _make_success_log(sqlite_session, post_id=posts[1].id)
    # posts[2] tidak memiliki success log

    sqlite_session.commit()

    assert not _check_log_completeness_invariant(sqlite_session), (
        "Harus mendeteksi violation: satu posted post tanpa success log"
    )


def test_draft_posts_without_logs_satisfy_invariant(
    sqlite_session: Session,
) -> None:
    """
    Unit test: hanya draft posts, tidak ada success log → invariant OK
    (vacuously true karena tidak ada posted posts).
    """
    for i in range(3):
        post = Post(
            content=f"Draft konten {i}",
            content_type="tips_list",
            status="draft",
            is_thread=False,
            thread_count=1,
        )
        sqlite_session.add(post)

    sqlite_session.commit()

    # Tidak ada posted posts → invariant trivially satisfied
    assert _check_log_completeness_invariant(sqlite_session)
    assert _count_posted_posts(sqlite_session) == 0


def test_failed_posts_without_logs_satisfy_invariant(
    sqlite_session: Session,
) -> None:
    """
    Unit test: hanya failed posts, tidak ada success log → invariant OK.
    """
    for i in range(2):
        post = Post(
            content=f"Post gagal {i}",
            content_type="pertanyaan",
            status="failed",
            is_thread=False,
            thread_count=1,
        )
        sqlite_session.add(post)

    sqlite_session.commit()

    assert _check_log_completeness_invariant(sqlite_session)
    assert _count_posted_posts(sqlite_session) == 0


def test_failed_log_does_not_satisfy_invariant(
    sqlite_session: Session,
) -> None:
    """
    Unit test: posted post dengan bot_log action='publish_post' status='failed'
    (bukan 'success') → invariant masih violated.
    """
    post = _make_posted_post(sqlite_session, content="Post dengan failed log")

    # Buat failed log (bukan success)
    failed_log = BotLog(
        post_id=post.id,
        task_id=str(uuid.uuid4()),
        action="publish_post",
        status="failed",
        message="Gagal publish",
        duration_ms=500,
    )
    sqlite_session.add(failed_log)
    sqlite_session.commit()

    # Failed log TIDAK memenuhi invariant (butuh status='success')
    assert not _check_log_completeness_invariant(sqlite_session), (
        "Log dengan status='failed' tidak boleh dianggap memenuhi invariant kelengkapan"
    )


def test_aggregat_count_property(sqlite_session: Session) -> None:
    """
    Unit test: verifikasi properti aggregat —
    count(success logs) >= count(posted posts) saat setiap posted post memiliki log.
    """
    # 2 posted posts, masing-masing punya 2 success logs (lebih dari minimum)
    for i in range(2):
        post = _make_posted_post(sqlite_session, content=f"Post {i}")
        # Buat 2 success logs per post (multiple logs diperbolehkan)
        _make_success_log(sqlite_session, post_id=post.id)
        _make_success_log(sqlite_session, post_id=post.id)

    sqlite_session.commit()

    posted_count = _count_posted_posts(sqlite_session)
    success_log_count = _count_success_publish_logs(sqlite_session)

    assert posted_count == 2
    assert success_log_count == 4  # 2 logs per post
    assert success_log_count >= posted_count, (
        f"Aggregat: {success_log_count} success logs harus >= {posted_count} posted posts"
    )
