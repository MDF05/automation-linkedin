"""
Property 7: Invariant — Batas Anti-Ban Harian

Validates: Requirements 9.2, 9.3

Rules verified:
- Ketika N aksi dicoba (N > batas harian), jumlah aksi yang berhasil (diizinkan)
  tidak boleh melebihi batas harian yang dikonfigurasi.
- check_daily_limit(module, count_today, limits) mengembalikan False jika
  count_today >= limit untuk modul tersebut.
- check_daily_limit(module, count_today, limits) mengembalikan True jika
  count_today < limit untuk modul tersebut.

Testing strategy: menggunakan Hypothesis untuk mem-generate:
1. Nilai N dalam range [0, 100] sebagai jumlah aksi yang sudah dilakukan hari ini,
   dan verifikasi bahwa check_daily_limit konsisten dengan batas.
2. Simulasi "hari penuh" — iterasi N percobaan aksi, hitung berapa yang diizinkan,
   verifikasi jumlah <= batas.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.services.anti_ban import check_daily_limit

# ---------------------------------------------------------------------------
# Konstanta modul yang valid beserta batas default-nya
# ---------------------------------------------------------------------------

VALID_MODULES = ("post", "comment", "apply")
DEFAULT_LIMITS: Dict[str, int] = {
    "post": 3,
    "comment": 15,
    "apply": 20,
}

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy: (module, custom_limit) — limit positif
_module_with_limit_st = st.one_of(
    st.tuples(
        st.sampled_from(VALID_MODULES),
        st.integers(min_value=1, max_value=50),
    )
)

# Strategy: (module, limit, count_today) — count_today dalam [0, limit - 1] (di bawah batas)
_below_limit_st = st.one_of(*[
    st.integers(min_value=1, max_value=50).flatmap(
        lambda limit: st.tuples(
            st.just(m),
            st.just(limit),
            st.integers(min_value=0, max_value=limit - 1),
        )
    )
    for m in VALID_MODULES
])

# Strategy: (module, limit, count_today) — count_today >= limit (di atau melebihi batas)
_at_or_above_limit_st = st.one_of(*[
    st.integers(min_value=1, max_value=50).flatmap(
        lambda limit: st.tuples(
            st.just(m),
            st.just(limit),
            st.integers(min_value=limit, max_value=limit + 100),
        )
    )
    for m in VALID_MODULES
])


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(module_limit_count=_below_limit_st)
@h_settings(max_examples=200)
def test_check_daily_limit_returns_true_when_below_limit(
    module_limit_count: Tuple[str, int, int],
) -> None:
    """
    **Property 7a — Validates: Requirements 9.2, 9.3**

    Untuk semua (module, limit, count_today) di mana count_today < limit,
    check_daily_limit harus mengembalikan True (aksi diizinkan).
    """
    module, limit, count_today = module_limit_count
    limits = {module: limit}

    result = check_daily_limit(module, count_today, limits)

    assert result is True, (
        f"check_daily_limit('{module}', {count_today}, {limits}) "
        f"seharusnya True karena {count_today} < {limit}"
    )


@given(module_limit_count=_at_or_above_limit_st)
@h_settings(max_examples=200)
def test_check_daily_limit_returns_false_when_at_or_above_limit(
    module_limit_count: Tuple[str, int, int],
) -> None:
    """
    **Property 7b — Validates: Requirements 9.2, 9.3**

    Untuk semua (module, limit, count_today) di mana count_today >= limit,
    check_daily_limit harus mengembalikan False (aksi ditolak).
    """
    module, limit, count_today = module_limit_count
    limits = {module: limit}

    result = check_daily_limit(module, count_today, limits)

    assert result is False, (
        f"check_daily_limit('{module}', {count_today}, {limits}) "
        f"seharusnya False karena {count_today} >= {limit}"
    )


@given(
    module=st.sampled_from(VALID_MODULES),
    limit=st.integers(min_value=1, max_value=50),
    total_attempts=st.integers(min_value=1, max_value=150),
)
@h_settings(max_examples=300)
def test_daily_limit_invariant_count_never_exceeds_limit(
    module: str,
    limit: int,
    total_attempts: int,
) -> None:
    """
    **Property 7 — Validates: Requirements 9.2, 9.3**

    Invariant utama: Ketika N aksi dicoba (N > batas), jumlah aksi yang
    berhasil diizinkan tidak pernah melebihi batas harian yang dikonfigurasi.

    Simulasi satu hari penuh:
    - Mulai dari count_today = 0
    - Untuk setiap percobaan, cek check_daily_limit
    - Jika diizinkan, increment count_today dan catat sebagai berhasil
    - Verifikasi bahwa total_allowed <= limit di akhir simulasi
    """
    limits = {module: limit}
    count_today = 0
    total_allowed = 0

    for _ in range(total_attempts):
        allowed = check_daily_limit(module, count_today, limits)
        if allowed:
            count_today += 1
            total_allowed += 1

    assert total_allowed <= limit, (
        f"Setelah {total_attempts} percobaan dengan limit={limit} untuk modul '{module}', "
        f"total aksi yang diizinkan adalah {total_allowed}, melebihi batas {limit}."
    )


@given(
    limit=st.integers(min_value=1, max_value=50),
    n_over_limit=st.integers(min_value=1, max_value=100),
)
@h_settings(max_examples=200)
def test_all_modules_respect_their_individual_limits(
    limit: int,
    n_over_limit: int,
) -> None:
    """
    **Property 7c — Validates: Requirements 9.2, 9.3**

    Setiap modul (post, comment, apply) dengan batas kustom yang sama harus
    mematuhi batas masing-masing secara independen. Melakukan N > batas
    percobaan pada setiap modul menghasilkan paling banyak `limit` aksi berhasil
    per modul.
    """
    total_attempts = limit + n_over_limit  # Selalu > limit
    custom_limits = {m: limit for m in VALID_MODULES}

    for module in VALID_MODULES:
        count_today = 0
        allowed_count = 0

        for _ in range(total_attempts):
            if check_daily_limit(module, count_today, custom_limits):
                count_today += 1
                allowed_count += 1

        assert allowed_count <= limit, (
            f"Modul '{module}' dengan limit={limit}: "
            f"diizinkan {allowed_count} dari {total_attempts} percobaan, "
            f"melebihi batas {limit}."
        )
        # Tepat limit aksi yang harus diizinkan (tidak lebih, tidak kurang)
        assert allowed_count == limit, (
            f"Modul '{module}' dengan limit={limit} dan {total_attempts} percobaan: "
            f"seharusnya mengizinkan tepat {limit} aksi, tetapi mengizinkan {allowed_count}."
        )


@given(
    module=st.sampled_from(VALID_MODULES),
    limit=st.integers(min_value=1, max_value=50),
    n_over_limit=st.integers(min_value=1, max_value=100),
)
@h_settings(max_examples=200)
def test_allowed_actions_exactly_equals_limit_when_exceeded(
    module: str,
    limit: int,
    n_over_limit: int,
) -> None:
    """
    **Property 7d — Validates: Requirements 9.2, 9.3**

    Ketika total percobaan (N = limit + extra) melebihi batas, jumlah aksi
    yang diizinkan harus tepat sama dengan `limit` — tidak lebih, tidak kurang.
    """
    total_attempts = limit + n_over_limit
    limits = {module: limit}

    count_today = 0
    allowed_count = 0

    for _ in range(total_attempts):
        if check_daily_limit(module, count_today, limits):
            count_today += 1
            allowed_count += 1

    assert allowed_count == limit, (
        f"Dengan {total_attempts} percobaan dan limit={limit} untuk '{module}', "
        f"seharusnya tepat {limit} aksi yang diizinkan, tetapi {allowed_count}."
    )


# ---------------------------------------------------------------------------
# Unit tests (example-based) sebagai sanity check
# ---------------------------------------------------------------------------


def test_post_module_default_limit_boundary() -> None:
    """Post: batas default 3 — hari ini 2 post → diizinkan; 3 post → ditolak."""
    assert check_daily_limit("post", 2, DEFAULT_LIMITS) is True
    assert check_daily_limit("post", 3, DEFAULT_LIMITS) is False


def test_comment_module_default_limit_boundary() -> None:
    """Comment: batas default 15 — hari ini 14 komentar → diizinkan; 15 → ditolak."""
    assert check_daily_limit("comment", 14, DEFAULT_LIMITS) is True
    assert check_daily_limit("comment", 15, DEFAULT_LIMITS) is False


def test_apply_module_default_limit_boundary() -> None:
    """Apply: batas default 20 — hari ini 19 lamaran → diizinkan; 20 → ditolak."""
    assert check_daily_limit("apply", 19, DEFAULT_LIMITS) is True
    assert check_daily_limit("apply", 20, DEFAULT_LIMITS) is False


def test_simulation_with_default_limits_post() -> None:
    """
    Simulasi satu hari penuh untuk modul 'post' dengan batas default 3:
    mencoba 100 aksi → tepat 3 yang diizinkan.
    """
    count_today = 0
    allowed = 0
    for _ in range(100):
        if check_daily_limit("post", count_today, DEFAULT_LIMITS):
            count_today += 1
            allowed += 1
    assert allowed == 3


def test_simulation_with_default_limits_comment() -> None:
    """
    Simulasi satu hari penuh untuk modul 'comment' dengan batas default 15:
    mencoba 100 aksi → tepat 15 yang diizinkan.
    """
    count_today = 0
    allowed = 0
    for _ in range(100):
        if check_daily_limit("comment", count_today, DEFAULT_LIMITS):
            count_today += 1
            allowed += 1
    assert allowed == 15


def test_simulation_with_default_limits_apply() -> None:
    """
    Simulasi satu hari penuh untuk modul 'apply' dengan batas default 20:
    mencoba 100 aksi → tepat 20 yang diizinkan.
    """
    count_today = 0
    allowed = 0
    for _ in range(100):
        if check_daily_limit("apply", count_today, DEFAULT_LIMITS):
            count_today += 1
            allowed += 1
    assert allowed == 20
