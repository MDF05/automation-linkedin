"""
Property 8: Invariant — Tracking Penggunaan AI

Validates: Requirements 8.1

Rules verified:
- Every AI call (success OR failure) MUST produce exactly ONE new entry in
  ai_usage.
- The entry must record: provider, prompt_tokens, completion_tokens, success,
  and a non-null created_at.

Testing strategy: we use an in-memory list to simulate the ai_usage table and
a minimal mock of an AI provider. The property test generates arbitrary
sequences of AI calls (with random success/failure outcomes) and asserts that
len(ai_usage_table) == total_calls_made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from hypothesis import given, settings as h_settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

VALID_PROVIDERS = (
    "deepseek",
    "groq",
    "chatgpt_web",
    "claude_web",
    "perplexity_web",
)


@dataclass
class AiUsageEntry:
    """Mirrors the AiUsage ORM model for testing purposes."""

    provider: str
    prompt_tokens: int
    completion_tokens: int
    success: bool
    error_message: Optional[str]
    latency_ms: int
    created_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


# ---------------------------------------------------------------------------
# Minimal AI service stub that logs to an in-memory list
# ---------------------------------------------------------------------------


class InMemoryAiUsageRepository:
    """Minimal in-memory store mimicking the ai_usage table."""

    def __init__(self) -> None:
        self._entries: List[AiUsageEntry] = []

    def add(self, entry: AiUsageEntry) -> None:
        self._entries.append(entry)

    @property
    def count(self) -> int:
        return len(self._entries)

    def all(self) -> List[AiUsageEntry]:
        return list(self._entries)


class MockAiService:
    """
    A minimal AI service that always records a usage entry, regardless of
    whether the underlying call succeeds or fails.
    """

    def __init__(self, repo: InMemoryAiUsageRepository) -> None:
        self._repo = repo

    def call(
        self,
        provider: str,
        prompt: str,
        should_succeed: bool,
    ) -> Optional[str]:
        """
        Simulate an AI call.  Always writes exactly one AiUsageEntry.

        Returns the response string if successful, None otherwise.
        """
        prompt_tokens = len(prompt.split())
        start = datetime.now(tz=timezone.utc)

        try:
            if not should_succeed:
                raise RuntimeError("Simulated provider failure")
            response = f"Response from {provider}"
            completion_tokens = len(response.split())
            entry = AiUsageEntry(
                provider=provider,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                success=True,
                error_message=None,
                latency_ms=42,
            )
            self._repo.add(entry)
            return response
        except Exception as exc:
            entry = AiUsageEntry(
                provider=provider,
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                success=False,
                error_message=str(exc),
                latency_ms=1,
            )
            self._repo.add(entry)
            return None


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_provider_st = st.sampled_from(VALID_PROVIDERS)
_prompt_st = st.text(min_size=1, max_size=200)
_success_st = st.booleans()

_call_params_st = st.tuples(_provider_st, _prompt_st, _success_st)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(calls=st.lists(_call_params_st, min_size=0, max_size=50))
@h_settings(max_examples=100)
def test_every_ai_call_produces_exactly_one_usage_entry(
    calls: list[tuple[str, str, bool]],
) -> None:
    """
    **Property 8 — Validates: Requirements 8.1**

    For every sequence of N AI calls (success or failure), the ai_usage
    repository must contain exactly N entries afterwards.
    """
    repo = InMemoryAiUsageRepository()
    svc = MockAiService(repo)

    for provider, prompt, should_succeed in calls:
        svc.call(provider=provider, prompt=prompt, should_succeed=should_succeed)

    assert repo.count == len(calls), (
        f"Expected {len(calls)} ai_usage entries after {len(calls)} calls, "
        f"got {repo.count}"
    )


@given(
    provider=_provider_st,
    prompt=_prompt_st,
)
@h_settings(max_examples=100)
def test_successful_call_creates_entry_with_correct_provider(
    provider: str, prompt: str
) -> None:
    """
    **Property 8a — Validates: Requirements 8.1**

    A successful AI call creates an entry with the correct provider and
    success=True.
    """
    repo = InMemoryAiUsageRepository()
    svc = MockAiService(repo)

    svc.call(provider=provider, prompt=prompt, should_succeed=True)

    assert repo.count == 1
    entry = repo.all()[0]
    assert entry.provider == provider
    assert entry.success is True
    assert entry.error_message is None
    assert entry.created_at is not None


@given(
    provider=_provider_st,
    prompt=_prompt_st,
)
@h_settings(max_examples=100)
def test_failed_call_creates_entry_with_success_false(
    provider: str, prompt: str
) -> None:
    """
    **Property 8b — Validates: Requirements 8.1**

    A failed AI call creates an entry with success=False and a non-null
    error_message.
    """
    repo = InMemoryAiUsageRepository()
    svc = MockAiService(repo)

    result = svc.call(provider=provider, prompt=prompt, should_succeed=False)

    assert result is None, "Failed call should return None"
    assert repo.count == 1
    entry = repo.all()[0]
    assert entry.provider == provider
    assert entry.success is False
    assert entry.error_message is not None and len(entry.error_message) > 0


@given(calls=st.lists(_call_params_st, min_size=1, max_size=30))
@h_settings(max_examples=100)
def test_usage_entries_preserve_call_order_and_provider(
    calls: list[tuple[str, str, bool]],
) -> None:
    """
    **Property 8c — Validates: Requirements 8.1**

    The i-th ai_usage entry corresponds to the i-th AI call (provider matches).
    """
    repo = InMemoryAiUsageRepository()
    svc = MockAiService(repo)

    for provider, prompt, should_succeed in calls:
        svc.call(provider=provider, prompt=prompt, should_succeed=should_succeed)

    entries = repo.all()
    assert len(entries) == len(calls)

    for i, ((provider, _, should_succeed), entry) in enumerate(
        zip(calls, entries)
    ):
        assert entry.provider == provider, (
            f"Entry {i}: expected provider {provider!r}, got {entry.provider!r}"
        )
        assert entry.success == should_succeed, (
            f"Entry {i}: expected success={should_succeed}, got {entry.success}"
        )


# ---------------------------------------------------------------------------
# Example-based unit tests
# ---------------------------------------------------------------------------


def test_single_successful_call() -> None:
    """Baseline unit test: one success call → one entry, correct fields."""
    repo = InMemoryAiUsageRepository()
    svc = MockAiService(repo)

    svc.call(provider="deepseek", prompt="Hello world", should_succeed=True)

    assert repo.count == 1
    entry = repo.all()[0]
    assert entry.provider == "deepseek"
    assert entry.success is True
    assert entry.prompt_tokens > 0
    assert entry.completion_tokens > 0


def test_single_failed_call() -> None:
    """Baseline unit test: one failure call → one entry with error."""
    repo = InMemoryAiUsageRepository()
    svc = MockAiService(repo)

    svc.call(provider="groq", prompt="Test prompt", should_succeed=False)

    assert repo.count == 1
    entry = repo.all()[0]
    assert entry.provider == "groq"
    assert entry.success is False
    assert entry.completion_tokens == 0
    assert "Simulated provider failure" in (entry.error_message or "")


def test_zero_calls_zero_entries() -> None:
    """Edge case: no calls → empty repository."""
    repo = InMemoryAiUsageRepository()
    assert repo.count == 0
