"""
Property 5: Metamorphic — Filter Lowongan

Validates: Requirements 5.1, 5.2

Rules verified:
- Jika kriteria A lebih ketat dari kriteria B (A ⊂ B), maka results(A) ⊆ results(B)
- Jumlah lowongan dengan filter ketat selalu <= jumlah dengan filter lebih longgar.

Testing strategy: menggunakan fungsi filter in-memory yang merepresentasikan
logika filtering job search (tanpa DB nyata), kemudian memverifikasi
properti metamorfik subset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from hypothesis import assume, given, settings as h_settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Domain model — minimal job representation
# ---------------------------------------------------------------------------


@dataclass
class Job:
    """Representasi minimal lowongan kerja untuk tujuan testing filter."""

    job_url: str
    job_title: str
    company: str
    location: str
    job_type: str          # "full-time", "part-time", "kontrak", "freelance"
    skills: List[str] = field(default_factory=list)
    salary_min: int = 0    # dalam ribu IDR


@dataclass
class SearchCriteria:
    """Kriteria pencarian lowongan — sesuai JobCriteria schema."""

    titles: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    location: Optional[str] = None
    job_type: Optional[str] = None
    min_salary: int = 0


# ---------------------------------------------------------------------------
# Filter function (simulates job search filtering logic)
# ---------------------------------------------------------------------------


def filter_jobs(jobs: List[Job], criteria: SearchCriteria) -> List[Job]:
    """
    Filter lowongan berdasarkan kriteria pencarian.

    Aturan:
    - titles: minimal satu kata dari criteria.titles harus muncul di job_title (case-insensitive)
              Jika titles kosong, semua judul lolos.
    - location: harus cocok persis (case-insensitive) atau criteria.location adalah None/kosong
    - job_type: harus cocok persis atau criteria.job_type adalah None
    - skills: minimal satu skill dari criteria.skills harus ada di job.skills
              Jika criteria.skills kosong, semua skill lolos.
    - min_salary: job.salary_min >= criteria.min_salary

    Returns:
        List Job yang memenuhi semua kriteria.
    """
    results = []

    for job in jobs:
        # Filter by title
        if criteria.titles:
            title_match = any(
                kw.lower() in job.job_title.lower()
                for kw in criteria.titles
            )
            if not title_match:
                continue

        # Filter by location
        if criteria.location:
            if job.location.lower() != criteria.location.lower() and criteria.location.lower() != "remote":
                continue

        # Filter by job_type
        if criteria.job_type:
            if job.job_type.lower() != criteria.job_type.lower():
                continue

        # Filter by skills
        if criteria.skills:
            job_skills_lower = {s.lower() for s in job.skills}
            skill_match = any(s.lower() in job_skills_lower for s in criteria.skills)
            if not skill_match:
                continue

        # Filter by min_salary
        if criteria.min_salary > 0:
            if job.salary_min < criteria.min_salary:
                continue

        results.append(job)

    return results


def get_job_urls(jobs: List[Job]) -> Set[str]:
    """Kembalikan set job_url dari list lowongan."""
    return {job.job_url for job in jobs}


def is_subset_criteria(a: SearchCriteria, b: SearchCriteria) -> bool:
    """
    Cek apakah kriteria A lebih ketat (subset) dari kriteria B.

    A lebih ketat jika A menambahkan constraint yang tidak ada di B.
    Untuk tujuan test ini: A lebih ketat jika A.min_salary > B.min_salary,
    atau A.job_type lebih spesifik, atau A.location lebih spesifik.
    """
    # A lebih ketat salary
    if a.min_salary > b.min_salary:
        return True
    # A memiliki lokasi, B tidak
    if a.location and not b.location:
        return True
    # A memiliki job_type, B tidak
    if a.job_type and not b.job_type:
        return True
    # A memiliki lebih banyak skill required
    if len(a.skills) > len(b.skills) and set(b.skills).issubset(set(a.skills)):
        return True
    return False


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

_TITLES = ["Software Engineer", "Data Scientist", "Product Manager", "Backend Developer",
           "Frontend Developer", "DevOps", "ML Engineer", "QA Engineer"]
_LOCATIONS = ["Jakarta", "Bandung", "Surabaya", "Remote", "Yogyakarta"]
_JOB_TYPES = ["full-time", "part-time", "kontrak", "freelance"]
_SKILLS = ["Python", "JavaScript", "TypeScript", "SQL", "Docker", "React",
           "FastAPI", "PostgreSQL", "Redis", "Kubernetes"]

_job_strategy = st.builds(
    Job,
    job_url=st.from_regex(r"https://linkedin\.com/jobs/view/\d{7}", fullmatch=True),
    job_title=st.sampled_from(_TITLES),
    company=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=3, max_size=20),
    location=st.sampled_from(_LOCATIONS),
    job_type=st.sampled_from(_JOB_TYPES),
    skills=st.lists(st.sampled_from(_SKILLS), min_size=0, max_size=5, unique=True),
    salary_min=st.integers(min_value=0, max_value=50_000),
)

_jobs_list_strategy = st.lists(_job_strategy, min_size=5, max_size=30)

_criteria_strategy = st.builds(
    SearchCriteria,
    titles=st.lists(st.sampled_from(_TITLES), min_size=0, max_size=3, unique=True),
    skills=st.lists(st.sampled_from(_SKILLS), min_size=0, max_size=3, unique=True),
    location=st.one_of(st.none(), st.sampled_from(_LOCATIONS)),
    job_type=st.one_of(st.none(), st.sampled_from(_JOB_TYPES)),
    min_salary=st.integers(min_value=0, max_value=30_000),
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    jobs=_jobs_list_strategy,
    criteria_b=_criteria_strategy,
    extra_salary=st.integers(min_value=1, max_value=20_000),
)
@h_settings(max_examples=200)
def test_stricter_salary_yields_subset(
    jobs: List[Job],
    criteria_b: SearchCriteria,
    extra_salary: int,
) -> None:
    """
    **Property 5a — Validates: Requirements 5.1, 5.2**

    Kriteria A (salary lebih tinggi) ⊂ Kriteria B → results(A) ⊆ results(B)
    """
    # Buat kriteria A yang lebih ketat: min_salary lebih tinggi
    criteria_a = SearchCriteria(
        titles=criteria_b.titles,
        skills=criteria_b.skills,
        location=criteria_b.location,
        job_type=criteria_b.job_type,
        min_salary=criteria_b.min_salary + extra_salary,
    )

    results_a = get_job_urls(filter_jobs(jobs, criteria_a))
    results_b = get_job_urls(filter_jobs(jobs, criteria_b))

    assert results_a.issubset(results_b), (
        f"results(A_strict_salary) ⊄ results(B_loose_salary)\n"
        f"A hanya: {results_a - results_b}"
    )
    assert len(results_a) <= len(results_b), (
        f"Filter ketat (salary={criteria_a.min_salary}) harus menghasilkan "
        f"<= hasil filter longgar (salary={criteria_b.min_salary}). "
        f"A={len(results_a)}, B={len(results_b)}"
    )


@given(
    jobs=_jobs_list_strategy,
    criteria_b=_criteria_strategy,
    job_type=st.sampled_from(_JOB_TYPES),
)
@h_settings(max_examples=200)
def test_stricter_job_type_yields_subset(
    jobs: List[Job],
    criteria_b: SearchCriteria,
    job_type: str,
) -> None:
    """
    **Property 5b — Validates: Requirements 5.1, 5.2**

    Kriteria A (job_type ditentukan) ⊂ Kriteria B (job_type=None) → results(A) ⊆ results(B)
    """
    # Buat criteria_b tanpa job_type constraint
    criteria_b_loose = SearchCriteria(
        titles=criteria_b.titles,
        skills=criteria_b.skills,
        location=criteria_b.location,
        job_type=None,  # lebih longgar
        min_salary=criteria_b.min_salary,
    )
    # criteria_a menambahkan job_type filter
    criteria_a = SearchCriteria(
        titles=criteria_b.titles,
        skills=criteria_b.skills,
        location=criteria_b.location,
        job_type=job_type,  # lebih ketat
        min_salary=criteria_b.min_salary,
    )

    results_a = get_job_urls(filter_jobs(jobs, criteria_a))
    results_b = get_job_urls(filter_jobs(jobs, criteria_b_loose))

    assert results_a.issubset(results_b), (
        f"results(A_with_job_type={job_type!r}) ⊄ results(B_no_job_type)\n"
        f"A hanya: {results_a - results_b}"
    )


@given(
    jobs=_jobs_list_strategy,
    criteria_b=_criteria_strategy,
    extra_skill=st.sampled_from(_SKILLS),
)
@h_settings(max_examples=200)
def test_stricter_skill_requirement_yields_subset(
    jobs: List[Job],
    criteria_b: SearchCriteria,
    extra_skill: str,
) -> None:
    """
    **Property 5c — Validates: Requirements 5.1, 5.2**

    Kriteria A (skill tambahan) ⊂ Kriteria B → results(A) ⊆ results(B)
    """
    assume(extra_skill not in criteria_b.skills)

    # criteria_a memerlukan extra_skill PLUS semua skills dari B
    criteria_a = SearchCriteria(
        titles=criteria_b.titles,
        skills=criteria_b.skills + [extra_skill],  # lebih ketat
        location=criteria_b.location,
        job_type=criteria_b.job_type,
        min_salary=criteria_b.min_salary,
    )

    results_a = get_job_urls(filter_jobs(jobs, criteria_a))
    results_b = get_job_urls(filter_jobs(jobs, criteria_b))

    assert results_a.issubset(results_b), (
        f"results(A_with_extra_skill) ⊄ results(B)\n"
        f"A hanya: {results_a - results_b}"
    )


@given(jobs=_jobs_list_strategy, criteria=_criteria_strategy)
@h_settings(max_examples=100)
def test_empty_criteria_returns_all_jobs(
    jobs: List[Job], criteria: SearchCriteria
) -> None:
    """
    **Property 5d — Validates: Requirements 5.1**

    Kriteria kosong (semua None/kosong) harus mengembalikan semua lowongan.
    """
    empty_criteria = SearchCriteria()
    results = filter_jobs(jobs, empty_criteria)
    assert len(results) == len(jobs), (
        f"Kriteria kosong harus mengembalikan semua {len(jobs)} lowongan, "
        f"dapat {len(results)}"
    )


@given(jobs=_jobs_list_strategy, criteria=_criteria_strategy)
@h_settings(max_examples=100)
def test_filter_is_deterministic(jobs: List[Job], criteria: SearchCriteria) -> None:
    """
    **Property 5e — Validates: Requirements 5.1**

    Filter yang sama pada input yang sama selalu menghasilkan output yang sama.
    """
    results1 = get_job_urls(filter_jobs(jobs, criteria))
    results2 = get_job_urls(filter_jobs(jobs, criteria))
    assert results1 == results2, "Filter harus deterministik"


# ---------------------------------------------------------------------------
# Unit tests (example-based)
# ---------------------------------------------------------------------------


def _make_jobs() -> List[Job]:
    return [
        Job("url1", "Software Engineer", "CompA", "Jakarta", "full-time",
            ["Python", "Docker"], 10_000),
        Job("url2", "Data Scientist", "CompB", "Bandung", "full-time",
            ["Python", "SQL"], 8_000),
        Job("url3", "Frontend Developer", "CompC", "Remote", "kontrak",
            ["JavaScript", "React"], 5_000),
        Job("url4", "Backend Developer", "CompD", "Jakarta", "full-time",
            ["Python", "FastAPI"], 12_000),
    ]


def test_location_filter_narrows_results() -> None:
    jobs = _make_jobs()
    all_results = filter_jobs(jobs, SearchCriteria())
    jakarta_results = filter_jobs(jobs, SearchCriteria(location="Jakarta"))

    assert len(jakarta_results) < len(all_results)
    assert get_job_urls(jakarta_results).issubset(get_job_urls(all_results))


def test_salary_filter_narrows_results() -> None:
    jobs = _make_jobs()
    low_salary = filter_jobs(jobs, SearchCriteria(min_salary=0))
    high_salary = filter_jobs(jobs, SearchCriteria(min_salary=10_000))

    assert len(high_salary) <= len(low_salary)
    assert get_job_urls(high_salary).issubset(get_job_urls(low_salary))


def test_combined_stricter_criteria_is_subset() -> None:
    jobs = _make_jobs()

    loose = SearchCriteria(location="Jakarta")
    strict = SearchCriteria(location="Jakarta", job_type="full-time", min_salary=10_000)

    results_loose = get_job_urls(filter_jobs(jobs, loose))
    results_strict = get_job_urls(filter_jobs(jobs, strict))

    assert results_strict.issubset(results_loose)
