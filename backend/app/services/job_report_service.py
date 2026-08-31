"""
Job Report Service — Laporan ringkasan sesi Job Hunter.

Menghasilkan laporan setelah setiap sesi pencarian / lamaran kerja yang mencakup:
- Jumlah lowongan ditemukan
- Jumlah berhasil dilamar
- Jumlah dilewati dan alasan lewat
- Breakdown status seluruh aplikasi dalam sesi

Requirements: 5.9
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_application import JobApplication


async def generate_session_report(
    session_id: str,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    Buat laporan ringkasan untuk satu sesi job hunting.

    Mengambil semua JobApplication dengan search_session_id yang sesuai
    dan menghitung jumlah per status, serta mengumpulkan alasan lewat.

    Args:
        session_id: UUID sesi (search_session_id di tabel job_applications).
        db:         AsyncSession SQLAlchemy.

    Returns:
        Dict dengan struktur:
        {
            "session_id": str,
            "total_found": int,
            "total_applied": int,
            "total_skipped": int,
            "status_breakdown": {"found": N, "applied": N, "skipped": N, ...},
            "skip_reasons": [{"reason": str, "count": int}, ...],
            "jobs": [{"job_title": str, "company": str, "status": str, "notes": str}, ...]
        }

    Requirements: 5.9
    """
    result = await db.execute(
        select(JobApplication).where(
            JobApplication.search_session_id == session_id
        )
    )
    jobs: List[JobApplication] = list(result.scalars().all())

    if not jobs:
        return {
            "session_id": session_id,
            "total_found": 0,
            "total_applied": 0,
            "total_skipped": 0,
            "status_breakdown": {},
            "skip_reasons": [],
            "jobs": [],
        }

    # Hitung status breakdown
    status_counter: Counter = Counter(job.status for job in jobs)

    # Hitung alasan skip
    skip_statuses = {"skipped", "skipped_incomplete_form", "skipped_no_easy_apply"}
    skip_reasons: Counter = Counter()
    for job in jobs:
        if job.status in skip_statuses:
            reason = job.notes or job.status
            skip_reasons[reason] += 1

    total_found = len(jobs)
    total_applied = status_counter.get("applied", 0)
    total_skipped = sum(status_counter.get(s, 0) for s in skip_statuses)

    return {
        "session_id": session_id,
        "total_found": total_found,
        "total_applied": total_applied,
        "total_skipped": total_skipped,
        "status_breakdown": dict(status_counter),
        "skip_reasons": [
            {"reason": reason, "count": count}
            for reason, count in skip_reasons.most_common()
        ],
        "jobs": [
            {
                "id": job.id,
                "job_title": job.job_title,
                "company": job.company,
                "location": job.location,
                "status": job.status,
                "notes": job.notes,
                "applied_at": job.applied_at.isoformat() if job.applied_at else None,
            }
            for job in jobs
        ],
    }
