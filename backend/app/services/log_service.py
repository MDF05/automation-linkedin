"""
Log Service — mencatat setiap aksi bot ke tabel bot_logs.

Komponen ini:
- Menyediakan `create_log` untuk membuat entri log baru (Requirements 7.1, 7.2)
- Menyediakan `update_log` untuk memperbarui status/pesan log yang sudah ada (Requirements 7.1)
- Mendukung screenshot_path untuk referensi screenshot per aksi (Requirements 7.2)
- Semua operasi bersifat async menggunakan AsyncSession SQLAlchemy

Requirements: 7.1, 7.2
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot_log import BotLog


async def create_log(
    db: AsyncSession,
    *,
    action: str,
    status: str,
    task_id: str,
    message: Optional[str] = None,
    error_detail: Optional[str] = None,
    duration_ms: Optional[int] = None,
    screenshot_path: Optional[str] = None,
    post_id: Optional[int] = None,
    module: Optional[str] = None,
    stack_trace: Optional[str] = None,
) -> BotLog:
    """
    Buat entri log baru di tabel bot_logs.

    Args:
        db: AsyncSession SQLAlchemy yang aktif.
        action: Tipe aksi bot (misalnya 'publish_post', 'generate_comment').
                Harus sesuai CHECK constraint di model BotLog.
        status: Status eksekusi ('success', 'failed', 'running', 'skipped', 'timeout').
        task_id: UUID task yang menjalankan aksi ini (VARCHAR 36).
        message: Pesan hasil atau deskripsi singkat aksi. Opsional.
        error_detail: Detail error jika status='failed'. Opsional.
        duration_ms: Durasi eksekusi dalam milidetik. Opsional.
        screenshot_path: Path file screenshot yang diambil saat aksi. Opsional.
        post_id: Foreign key ke tabel posts jika aksi terkait post tertentu. Opsional.
        module: Modul bot yang menjalankan aksi ('A', 'B', 'C', 'D'). Opsional.
        stack_trace: Stack trace Python jika terjadi exception. Opsional.

    Returns:
        Objek BotLog yang baru dibuat dan sudah di-flush ke session.

    Requirements: 7.1, 7.2
    """
    log_entry = BotLog(
        action=action,
        status=status,
        task_id=task_id,
        message=message,
        error_detail=error_detail,
        duration_ms=duration_ms,
        screenshot_path=screenshot_path,
        post_id=post_id,
        module=module,
        stack_trace=stack_trace,
    )
    db.add(log_entry)
    await db.flush()  # populate id tanpa commit — caller yang commit
    return log_entry


async def update_log(
    db: AsyncSession,
    log_id: int,
    *,
    status: Optional[str] = None,
    message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    error_detail: Optional[str] = None,
    screenshot_path: Optional[str] = None,
) -> Optional[BotLog]:
    """
    Perbarui entri log yang sudah ada berdasarkan log_id.

    Berguna untuk memperbarui log dari status 'running' ke 'success' atau 'failed'
    setelah aksi selesai, atau menambahkan durasi dan screenshot setelah aksi.

    Args:
        db: AsyncSession SQLAlchemy yang aktif.
        log_id: ID entri bot_logs yang akan diperbarui.
        status: Status baru ('success', 'failed', 'running', 'skipped', 'timeout').
                Jika None, status tidak diubah.
        message: Pesan baru. Jika None, pesan tidak diubah.
        duration_ms: Durasi baru dalam milidetik. Jika None, tidak diubah.
        error_detail: Detail error baru. Jika None, tidak diubah.
        screenshot_path: Path screenshot baru. Jika None, tidak diubah.

    Returns:
        Objek BotLog yang sudah diperbarui, atau None jika log_id tidak ditemukan.

    Requirements: 7.1
    """
    result = await db.execute(select(BotLog).where(BotLog.id == log_id))
    log_entry: Optional[BotLog] = result.scalar_one_or_none()

    if log_entry is None:
        return None

    if status is not None:
        log_entry.status = status
    if message is not None:
        log_entry.message = message
    if duration_ms is not None:
        log_entry.duration_ms = duration_ms
    if error_detail is not None:
        log_entry.error_detail = error_detail
    if screenshot_path is not None:
        log_entry.screenshot_path = screenshot_path

    await db.flush()
    return log_entry
