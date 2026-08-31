"""
Property 11: Provider Chain Fallback — ai_usage tetap tercatat

Validates: Requirements 8.4, 8.5

Rules verified:
- Ketika primary provider gagal (success=False), ProviderChain mencoba provider berikutnya.
- Setiap provider yang dipanggil (gagal atau berhasil) menciptakan tepat satu entri ai_usage.
- Jika K provider pertama gagal dan provider ke-(K+1) berhasil → ada K+1 entri ai_usage.
- Jika SEMUA provider gagal → AllProvidersExhaustedError dilempar.

Property test (Hypothesis):
- Untuk N provider dengan K pertama gagal:
  - Chain mencoba tepat K+1 provider (K gagal + 1 sukses).
  - Jumlah entri ai_usage == K+1.
- Untuk semua provider gagal:
  - AllProvidersExhaustedError dilempar.
  - Jumlah entri ai_usage == N (semua dicoba).

Testing strategy:
- MockProvider yang dapat dikonfigurasi untuk gagal/berhasil.
- DB di-mock menggunakan unittest.mock untuk menghindari koneksi database nyata.
- ProviderChain._get_usage_percent di-mock agar selalu mengembalikan 0.0
  (tidak ada threshold warning yang memotong eksekusi).
"""

from __future__ import annotations

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

from app.services.ai_service import (
    AIRequest,
    AIResponse,
    AllProvidersExhaustedError,
    BaseAIProvider,
    ProviderChain,
)

# ---------------------------------------------------------------------------
# Helpers — MockProvider
# ---------------------------------------------------------------------------

VALID_PROVIDER_NAMES = [
    "deepseek",
    "groq",
    "chatgpt_web",
    "claude_web",
    "perplexity_web",
]


class MockProvider(BaseAIProvider):
    """
    Provider palsu yang dapat dikonfigurasi untuk berhasil atau gagal.

    Args:
        name:       Nama provider (harus sesuai VALID_PROVIDER_NAMES agar
                    ai_usage constraint tidak error).
        should_succeed: Jika True, generate() mengembalikan success=True.
                        Jika False, mengembalikan success=False.
    """

    def __init__(self, name: str, should_succeed: bool) -> None:
        self.provider_name = name
        self._should_succeed = should_succeed
        self.call_count = 0

    async def generate(self, request: AIRequest) -> AIResponse:
        self.call_count += 1
        if self._should_succeed:
            return AIResponse(
                content="Mocked response",
                provider=self.provider_name,
                prompt_tokens=10,
                completion_tokens=20,
                cost_estimate=0.0001,
                success=True,
                error=None,
                latency_ms=5,
            )
        else:
            return AIResponse(
                content="",
                provider=self.provider_name,
                prompt_tokens=0,
                completion_tokens=0,
                cost_estimate=0.0,
                success=False,
                error="Simulated provider failure",
                latency_ms=1,
            )

    async def is_available(self) -> bool:
        return True  # selalu tersedia agar tidak di-skip oleh chain

    def get_token_limit(self) -> int:
        return 1_000_000


# ---------------------------------------------------------------------------
# Helper — membuat ProviderChain dengan DB yang di-mock
# ---------------------------------------------------------------------------


def make_chain(providers: List[MockProvider]) -> tuple[ProviderChain, list]:
    """
    Buat ProviderChain dengan mock DB session.

    Mengembalikan (chain, usage_entries) di mana usage_entries adalah list
    yang diisi oleh mock db.add() — mirip dengan in-memory ai_usage table.

    DB mock:
    - db.add(entry) → append entry ke list
    - db.flush() → no-op AsyncMock
    - db.execute() → AsyncMock yang mengembalikan scalar 0 (untuk _get_usage_percent)
    """
    usage_entries: list = []

    mock_db = MagicMock()
    mock_db.add = MagicMock(side_effect=lambda entry: usage_entries.append(entry))
    mock_db.flush = AsyncMock(return_value=None)

    # Mock execute untuk _get_usage_percent agar selalu return 0 (tidak ada quota issue)
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0
    mock_db.execute = AsyncMock(return_value=mock_result)

    chain = ProviderChain(providers=providers, db=mock_db)
    return chain, usage_entries


def run_async(coro):
    """Helper untuk menjalankan coroutine di test sinkron."""
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy untuk memilih nama provider yang valid
_provider_name_st = st.sampled_from(VALID_PROVIDER_NAMES)

# Strategy: (k_fail, n_total) di mana 0 <= k_fail < n_total
# k_fail = jumlah provider yang gagal sebelum satu yang berhasil
# n_total = total provider dalam chain (minimal 2: ada yang gagal dan ada yang berhasil)
_fail_then_succeed_st = st.integers(min_value=1, max_value=4).flatmap(
    lambda n_total: st.tuples(
        st.integers(min_value=0, max_value=n_total - 1),  # k_fail
        st.just(n_total),
    )
)

# Strategy: n_fail = jumlah provider yang semua gagal (1..5)
_all_fail_st = st.integers(min_value=1, max_value=5)


# ---------------------------------------------------------------------------
# Unit tests (example-based)
# ---------------------------------------------------------------------------


def test_primary_fails_secondary_succeeds_two_usage_entries() -> None:
    """
    Unit test: primary gagal, secondary berhasil → 2 entri ai_usage.
    Respon berasal dari secondary.
    """
    providers = [
        MockProvider(name="deepseek", should_succeed=False),
        MockProvider(name="groq", should_succeed=True),
    ]
    chain, usage_entries = make_chain(providers)

    response = run_async(chain.generate(AIRequest(prompt="Hello")))

    assert response.success is True
    assert response.provider == "groq"
    assert len(usage_entries) == 2, (
        f"Expected 2 ai_usage entries (1 failed + 1 success), got {len(usage_entries)}"
    )
    assert usage_entries[0].provider == "deepseek"
    assert usage_entries[0].success is False
    assert usage_entries[1].provider == "groq"
    assert usage_entries[1].success is True


def test_all_providers_fail_raises_error_and_all_logged() -> None:
    """
    Unit test: semua provider gagal → AllProvidersExhaustedError dilempar.
    Semua provider tetap tercatat di ai_usage.
    """
    providers = [
        MockProvider(name="deepseek", should_succeed=False),
        MockProvider(name="groq", should_succeed=False),
        MockProvider(name="chatgpt_web", should_succeed=False),
    ]
    chain, usage_entries = make_chain(providers)

    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        run_async(chain.generate(AIRequest(prompt="Hello")))

    assert len(usage_entries) == 3, (
        f"Expected 3 ai_usage entries (all failed), got {len(usage_entries)}"
    )
    assert all(e.success is False for e in usage_entries)
    assert "deepseek" in exc_info.value.providers_tried
    assert "groq" in exc_info.value.providers_tried
    assert "chatgpt_web" in exc_info.value.providers_tried


def test_first_provider_succeeds_one_usage_entry() -> None:
    """
    Unit test: provider pertama langsung berhasil → 1 entri ai_usage.
    """
    providers = [
        MockProvider(name="deepseek", should_succeed=True),
        MockProvider(name="groq", should_succeed=True),  # tidak akan dipanggil
    ]
    chain, usage_entries = make_chain(providers)

    response = run_async(chain.generate(AIRequest(prompt="Hello")))

    assert response.success is True
    assert response.provider == "deepseek"
    assert len(usage_entries) == 1, (
        f"Expected 1 ai_usage entry (first success), got {len(usage_entries)}"
    )
    # Groq tidak boleh dipanggil
    assert providers[1].call_count == 0


def test_error_message_recorded_for_failed_provider() -> None:
    """
    Unit test: ai_usage untuk provider yang gagal menyimpan error_message non-null.
    """
    providers = [
        MockProvider(name="deepseek", should_succeed=False),
        MockProvider(name="groq", should_succeed=True),
    ]
    chain, usage_entries = make_chain(providers)

    run_async(chain.generate(AIRequest(prompt="Test error recording")))

    failed_entry = usage_entries[0]
    assert failed_entry.success is False
    assert failed_entry.error_message is not None
    assert len(failed_entry.error_message) > 0


def test_chain_stops_at_first_success() -> None:
    """
    Unit test: chain berhenti di provider pertama yang berhasil, tidak memanggil sisanya.
    """
    providers = [
        MockProvider(name="deepseek", should_succeed=False),
        MockProvider(name="groq", should_succeed=True),
        MockProvider(name="chatgpt_web", should_succeed=True),  # tidak dipanggil
    ]
    chain, usage_entries = make_chain(providers)

    response = run_async(chain.generate(AIRequest(prompt="Hello")))

    assert response.provider == "groq"
    assert providers[2].call_count == 0, "Provider setelah yang berhasil tidak boleh dipanggil"
    assert len(usage_entries) == 2  # deepseek (fail) + groq (success)


# ---------------------------------------------------------------------------
# Property tests (Hypothesis)
# ---------------------------------------------------------------------------


@given(fail_count_total=_fail_then_succeed_st)
@h_settings(max_examples=200)
def test_k_failures_then_success_creates_k_plus_one_usage_entries(
    fail_count_total: tuple[int, int],
) -> None:
    """
    **Property 11a — Validates: Requirements 8.4, 8.5**

    Untuk N provider di mana K pertama gagal dan provider ke-(K+1) berhasil:
    - Chain mencoba tepat K+1 provider
    - Jumlah entri ai_usage == K+1
    - K entri pertama memiliki success=False
    - Entri terakhir memiliki success=True

    Ini memvalidasi bahwa fallback bekerja benar DAN setiap call tercatat.
    """
    k_fail, n_total = fail_count_total
    # Pilih nama provider dari daftar valid, cycling jika lebih dari 5
    all_names = VALID_PROVIDER_NAMES
    providers: List[MockProvider] = []
    for i in range(n_total):
        name = all_names[i % len(all_names)]
        should_succeed = i == k_fail  # hanya provider ke-(k_fail) yang berhasil
        # Jika ada nama duplikat karena cycling, tambahkan suffix untuk dibedakan secara internal
        # tapi provider_name tetap valid untuk constraint DB
        providers.append(MockProvider(name=name, should_succeed=should_succeed))

    chain, usage_entries = make_chain(providers)
    response = run_async(chain.generate(AIRequest(prompt="test prompt")))

    expected_count = k_fail + 1

    assert response.success is True, (
        f"Response harus sukses karena provider ke-{k_fail + 1} berhasil"
    )
    assert len(usage_entries) == expected_count, (
        f"Dengan {k_fail} gagal + 1 sukses, harus ada {expected_count} ai_usage entries, "
        f"tapi ada {len(usage_entries)}"
    )

    # K entri pertama harus gagal
    for i in range(k_fail):
        assert usage_entries[i].success is False, (
            f"Entry ke-{i} (provider gagal) harus success=False"
        )

    # Entri terakhir harus berhasil
    assert usage_entries[-1].success is True, (
        "Entry terakhir (provider sukses) harus success=True"
    )


@given(n_fail=_all_fail_st)
@h_settings(max_examples=150)
def test_all_providers_fail_raises_exhausted_and_logs_all(n_fail: int) -> None:
    """
    **Property 11b — Validates: Requirements 8.4, 8.5**

    Untuk N provider yang semuanya gagal:
    - AllProvidersExhaustedError dilempar
    - Jumlah entri ai_usage == N (semua provider tercatat)
    - Semua entri memiliki success=False
    """
    all_names = VALID_PROVIDER_NAMES
    providers = [
        MockProvider(name=all_names[i % len(all_names)], should_succeed=False)
        for i in range(n_fail)
    ]

    chain, usage_entries = make_chain(providers)

    with pytest.raises(AllProvidersExhaustedError):
        run_async(chain.generate(AIRequest(prompt="all fail test")))

    assert len(usage_entries) == n_fail, (
        f"Semua {n_fail} provider gagal, harus ada {n_fail} ai_usage entries, "
        f"tapi ada {len(usage_entries)}"
    )
    assert all(e.success is False for e in usage_entries), (
        "Semua entri ai_usage harus success=False ketika semua provider gagal"
    )


@given(
    k_fail=st.integers(min_value=0, max_value=4),
    n_extra=st.integers(min_value=1, max_value=3),
)
@h_settings(max_examples=200)
def test_providers_after_first_success_are_never_called(
    k_fail: int, n_extra: int
) -> None:
    """
    **Property 11c — Validates: Requirements 8.5**

    Setelah provider pertama berhasil, provider sisanya TIDAK boleh dipanggil.
    Ini memvalidasi bahwa chain berhenti di sukses pertama (tidak mencoba semua).

    Setup: k_fail provider gagal, 1 sukses, lalu n_extra provider (tidak akan dipanggil).
    """
    all_names = VALID_PROVIDER_NAMES
    n_total = k_fail + 1 + n_extra

    providers: List[MockProvider] = []
    for i in range(n_total):
        name = all_names[i % len(all_names)]
        # Provider ke-k_fail adalah yang berhasil, sisanya gagal
        should_succeed = i == k_fail
        providers.append(MockProvider(name=name, should_succeed=should_succeed))

    chain, usage_entries = make_chain(providers)
    response = run_async(chain.generate(AIRequest(prompt="stop at first success")))

    assert response.success is True

    # Provider setelah sukses tidak boleh dipanggil
    for i in range(k_fail + 1, n_total):
        assert providers[i].call_count == 0, (
            f"Provider ke-{i} tidak boleh dipanggil setelah sukses di ke-{k_fail}"
        )

    # Hanya k_fail + 1 entri yang harus ada
    assert len(usage_entries) == k_fail + 1, (
        f"Hanya {k_fail + 1} entri ai_usage yang diharapkan, tapi ada {len(usage_entries)}"
    )


@given(n_fail=_all_fail_st)
@h_settings(max_examples=100)
def test_exhausted_error_contains_all_tried_provider_names(n_fail: int) -> None:
    """
    **Property 11d — Validates: Requirements 8.4**

    AllProvidersExhaustedError harus menyertakan nama semua provider yang telah dicoba
    dalam atribut providers_tried.
    """
    all_names = VALID_PROVIDER_NAMES
    expected_names = [all_names[i % len(all_names)] for i in range(n_fail)]
    providers = [
        MockProvider(name=name, should_succeed=False)
        for name in expected_names
    ]

    chain, _ = make_chain(providers)

    with pytest.raises(AllProvidersExhaustedError) as exc_info:
        run_async(chain.generate(AIRequest(prompt="track tried providers")))

    error = exc_info.value
    assert len(error.providers_tried) == n_fail, (
        f"providers_tried harus berisi {n_fail} nama, tapi berisi {len(error.providers_tried)}"
    )
    for name in expected_names:
        assert name in error.providers_tried, (
            f"'{name}' harus ada di providers_tried: {error.providers_tried}"
        )
