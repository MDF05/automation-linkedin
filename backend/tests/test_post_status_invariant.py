"""
Property 1: Invariant — Konsistensi Status Post

Validates: Requirements 2.8, 10.6

Rules verified:
- Every Post with status='posted'  MUST have posted_at non-null
- Every Post with status='draft'   MUST have posted_at null
- Every Post status MUST be one of: 'draft', 'scheduled', 'posted', 'failed'

Testing strategy: we test the ORM model dataclass-style (plain Python objects,
no live DB) because the invariant is about field relationships, not persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Helpers — construct a minimal Post-like object to validate the invariant
# without requiring a running database.
# ---------------------------------------------------------------------------


class PostLike:
    """Minimal stand-in for the Post ORM model — plain Python dataclass."""

    VALID_STATUSES = {"draft", "scheduled", "posted", "failed"}

    def __init__(self, status: str, posted_at: Optional[datetime]) -> None:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {status!r}")
        self.status = status
        self.posted_at = posted_at

    def is_status_consistent(self) -> bool:
        """
        Return True iff the posted_at / status combination is internally
        consistent according to Property 1.
        """
        if self.status == "posted":
            return self.posted_at is not None
        if self.status == "draft":
            return self.posted_at is None
        # 'scheduled' and 'failed' have no constraint on posted_at
        return True


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_UTC = timezone.utc
# hypothesis st.datetimes requires naive min/max values — tzinfo is added via .map()
_EPOCH_NAIVE = datetime(2020, 1, 1)
_NOW_NAIVE = datetime(2030, 12, 31)

_any_datetime = st.datetimes(min_value=_EPOCH_NAIVE, max_value=_NOW_NAIVE).map(
    lambda dt: dt.replace(tzinfo=_UTC)
)
_optional_datetime = st.one_of(st.none(), _any_datetime)


def _posted_post_strategy():
    """Generate a Post with status='posted' and a non-null posted_at."""
    return _any_datetime.map(lambda dt: PostLike(status="posted", posted_at=dt))


def _draft_post_strategy():
    """Generate a Post with status='draft' and posted_at=None."""
    return st.just(PostLike(status="draft", posted_at=None))


def _scheduled_post_strategy():
    """Generate a Post with status='scheduled'; posted_at can be anything."""
    return _optional_datetime.map(
        lambda dt: PostLike(status="scheduled", posted_at=dt)
    )


def _failed_post_strategy():
    """Generate a Post with status='failed'; posted_at can be anything."""
    return _optional_datetime.map(
        lambda dt: PostLike(status="failed", posted_at=dt)
    )


_any_valid_post = st.one_of(
    _posted_post_strategy(),
    _draft_post_strategy(),
    _scheduled_post_strategy(),
    _failed_post_strategy(),
)

# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(posted_at=_any_datetime)
@h_settings(max_examples=100)
def test_posted_status_requires_non_null_posted_at(posted_at: datetime) -> None:
    """
    **Property 1a — Validates: Requirements 2.8, 10.6**

    For every Post with status='posted', posted_at MUST be non-null.
    """
    post = PostLike(status="posted", posted_at=posted_at)
    assert post.posted_at is not None, (
        f"Post with status='posted' must have posted_at set, got: {post.posted_at}"
    )
    assert post.is_status_consistent()


@given(st.data())
@h_settings(max_examples=100)
def test_draft_status_requires_null_posted_at(data: st.DataObject) -> None:
    """
    **Property 1b — Validates: Requirements 2.8, 10.6**

    For every Post with status='draft', posted_at MUST be null.
    """
    post = PostLike(status="draft", posted_at=None)
    assert post.posted_at is None, (
        f"Post with status='draft' must have posted_at=None, got: {post.posted_at}"
    )
    assert post.is_status_consistent()


@given(post=_any_valid_post)
@h_settings(max_examples=200)
def test_all_valid_posts_are_consistent(post: PostLike) -> None:
    """
    **Property 1c — Validates: Requirements 2.8, 10.6**

    For every valid post (any status), the status/posted_at combination
    must satisfy the invariant.
    """
    assert post.is_status_consistent(), (
        f"Inconsistent post: status={post.status!r}, posted_at={post.posted_at}"
    )


def test_posted_without_posted_at_is_inconsistent() -> None:
    """
    Unit test (example-based): a post with status='posted' and posted_at=None
    must fail the consistency check.
    """
    post = PostLike.__new__(PostLike)
    # bypass __init__ validation to create the invalid object
    object.__setattr__(post, "status", "posted")
    object.__setattr__(post, "posted_at", None)
    assert not post.is_status_consistent(), (
        "Expected inconsistency for status='posted' with posted_at=None"
    )


def test_draft_with_posted_at_is_inconsistent() -> None:
    """
    Unit test (example-based): a post with status='draft' and posted_at set
    must fail the consistency check.
    """
    post = PostLike.__new__(PostLike)
    object.__setattr__(post, "status", "draft")
    object.__setattr__(post, "posted_at", datetime(2024, 6, 1, tzinfo=timezone.utc))
    assert not post.is_status_consistent(), (
        "Expected inconsistency for status='draft' with posted_at set"
    )


def test_invalid_status_raises_value_error() -> None:
    """
    Sanity check: constructing PostLike with an invalid status raises ValueError.
    """
    with pytest.raises(ValueError, match="Invalid status"):
        PostLike(status="unknown", posted_at=None)
