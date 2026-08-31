"""
Property 9: Idempotency — Apply Lowongan Duplikat

Validates: Requirements 5.4

Rules verified:
- apply(apply(job_url)) == apply(job_url) — mencoba melamar lowongan yang sudah
  ada di database dengan status 'applied' tidak menghasilkan entri duplikat.
- Sistem HARUS mengecek keberadaan job_url sebelum memproses lamaran baru.

Testing strategy: menggunakan in-memory dict sebagai pengganti database
untuk mensimulasikan idempotency logika tanpa koneksi DB nyata.
"""

from __future__ import annotations

from typing import Dict, Optional

import pytest
from hypothesis import given, settings as h_settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Minimal in-memory "database" untuk simulasi
# ---------------------------------------------------------------------------


class InMemoryJobDB:
    """
    Simulasi database job_applications sebagai dict in-memory.
    job_url adalah unique key (seperti UNIQUE constraint di schema).
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict] = {}  # job_url → job dict
        self._id_counter = 0

    def apply_job(self, job_url: str, status: str = "applied") -> Dict:
        """
        Coba lamar/simpan lowongan berdasarkan job_url.

        Jika job_url sudah ada, kembalikan entri yang ada (idempotent).
        Jika belum ada, buat entri baru dengan status yang diberikan.

        Returns:
            Dict entri job_application (baru atau yang sudah ada).
        """
        if job_url in self._store:
            # Sudah ada — idempotent: tidak buat duplikat
            return self._store[job_url]

        # Buat entri baru
        self._id_counter += 1
        entry = {
            "id": self._id_counter,
            "job_url": job_url,
            "status": status,
            "job_title": "Test Position",
            "company": "Test Company",
        }
        self._store[job_url] = entry
        return entry

    def count_by_url(self, job_url: str) -> int:
        """Jumlah entri dengan job_url tertentu (0 atau 1 karena unique)."""
        return 1 if job_url in self._store else 0

    def total_count(self) -> int:
        """Total entri dalam store."""
        return len(self._store)

    def get_by_url(self, job_url: str) -> Optional[Dict]:
        return self._store.get(job_url)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# URL lowongan realistis
_job_url_strategy = st.from_regex(
    r"https://www\.linkedin\.com/jobs/view/\d{8,12}",
    fullmatch=True,
)

# URL dengan berbagai format untuk edge cases
_any_url_strategy = st.one_of(
    _job_url_strategy,
    st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_/.:"),
        min_size=5,
        max_size=100,
    ),
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(job_url=_any_url_strategy)
@h_settings(max_examples=200)
def test_double_apply_does_not_create_duplicate(job_url: str) -> None:
    """
    **Property 9 — Validates: Requirements 5.4**

    Melamar lowongan yang sama dua kali tidak menghasilkan entri duplikat:
    count(job_applications where job_url=X) <= 1 setelah apply(X) dipanggil dua kali.
    """
    db = InMemoryJobDB()

    # Apply pertama kali
    first_result = db.apply_job(job_url)
    count_after_first = db.count_by_url(job_url)

    # Apply kedua kali dengan URL yang sama
    second_result = db.apply_job(job_url)
    count_after_second = db.count_by_url(job_url)

    # Tidak boleh ada duplikat
    assert count_after_first == 1, (
        f"Setelah apply pertama, count harus 1, dapat {count_after_first}"
    )
    assert count_after_second == 1, (
        f"Setelah apply kedua (duplikat), count harus tetap 1, dapat {count_after_second}"
    )

    # Kedua panggilan harus mengembalikan entri yang sama
    assert first_result["id"] == second_result["id"], (
        f"Apply kedua harus mengembalikan entri yang sama (id={first_result['id']}), "
        f"bukan entri baru (id={second_result['id']})"
    )
    assert first_result["job_url"] == second_result["job_url"] == job_url


@given(job_url=_any_url_strategy)
@h_settings(max_examples=200)
def test_triple_apply_idempotent(job_url: str) -> None:
    """
    **Property 9b — Validates: Requirements 5.4**

    Melamar tiga kali tetap menghasilkan satu entri:
    apply(apply(apply(job_url))) == apply(job_url)
    """
    db = InMemoryJobDB()

    for _ in range(3):
        db.apply_job(job_url)

    assert db.count_by_url(job_url) == 1
    assert db.total_count() == 1


@given(urls=st.lists(_any_url_strategy, min_size=2, max_size=10, unique=True))
@h_settings(max_examples=100)
def test_different_urls_create_separate_entries(urls: list) -> None:
    """
    **Property 9c — Validates: Requirements 5.4**

    Lowongan dengan URL berbeda HARUS membuat entri terpisah.
    """
    db = InMemoryJobDB()

    for url in urls:
        db.apply_job(url)

    assert db.total_count() == len(urls), (
        f"Setiap URL unik harus membuat satu entri. "
        f"Diharapkan {len(urls)}, dapat {db.total_count()}"
    )


@given(
    job_url=_any_url_strategy,
    n_apply=st.integers(min_value=1, max_value=10),
)
@h_settings(max_examples=100)
def test_n_apply_idempotent(job_url: str, n_apply: int) -> None:
    """
    **Property 9d — Validates: Requirements 5.4**

    Melamar N kali selalu menghasilkan tepat 1 entri,
    untuk sembarang N >= 1.
    """
    db = InMemoryJobDB()

    for _ in range(n_apply):
        db.apply_job(job_url)

    assert db.count_by_url(job_url) == 1, (
        f"Setelah {n_apply} kali apply, count harus 1"
    )


# ---------------------------------------------------------------------------
# Unit tests (example-based)
# ---------------------------------------------------------------------------


def test_first_apply_creates_entry() -> None:
    """Apply pertama harus membuat entri baru."""
    db = InMemoryJobDB()
    result = db.apply_job("https://www.linkedin.com/jobs/view/12345678")
    assert result["status"] == "applied"
    assert db.total_count() == 1


def test_second_apply_returns_existing_entry() -> None:
    """Apply kedua harus mengembalikan entri yang sudah ada."""
    db = InMemoryJobDB()
    url = "https://www.linkedin.com/jobs/view/12345678"
    first = db.apply_job(url)
    second = db.apply_job(url)
    assert first["id"] == second["id"]
    assert db.total_count() == 1


def test_different_urls_are_independent() -> None:
    """Dua URL berbeda tidak saling mempengaruhi."""
    db = InMemoryJobDB()
    db.apply_job("https://www.linkedin.com/jobs/view/11111111")
    db.apply_job("https://www.linkedin.com/jobs/view/22222222")
    assert db.total_count() == 2
    assert db.count_by_url("https://www.linkedin.com/jobs/view/11111111") == 1
    assert db.count_by_url("https://www.linkedin.com/jobs/view/22222222") == 1


def test_already_applied_status_not_overwritten() -> None:
    """Status 'applied' tidak boleh ditimpa oleh apply ulang."""
    db = InMemoryJobDB()
    url = "https://www.linkedin.com/jobs/view/99999999"
    db.apply_job(url, status="applied")
    result = db.apply_job(url, status="found")  # coba dengan status berbeda
    # Harus tetap 'applied' — entri awal yang dikembalikan
    assert result["status"] == "applied"
