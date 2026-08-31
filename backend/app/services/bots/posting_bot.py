"""
Posting Bot — Module A: Eksekusi posting konten ke LinkedIn via ADB.

Komponen ini:
- Mengambil post dari database berdasarkan post_id
- Membuka LinkedIn dan menavigasi ke form post baru via ADB
- Mengetik konten dan mengupload gambar jika ada
- Menekan tombol Publish dan memperbarui status post di database
- Mencatat setiap langkah ke BotLog via log_service (Requirements 2.8, 7.1)
- Emit WebSocket progress event untuk setiap langkah (Requirements 2.10)
- Mendukung format thread dengan posting tiap bagian secara berurutan (Requirements 2.11)
- Menggunakan anti_ban delay antar aksi (Requirements 9.1)

Requirements: 2.7, 2.8, 2.10, 10.6
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot_log import BotLog
from app.models.post import Post
from app.services import anti_ban
from app.services import log_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Koordinat relatif UI LinkedIn untuk posting konten
# Sesuai LINKEDIN_UI_MAP di adb_service.py
# ---------------------------------------------------------------------------

# Tombol "Mulai Post" / new post di beranda LinkedIn (bottom bar)
_NEW_POST_BTN = (0.5, 0.92)

# Area input teks post
_POST_INPUT = (0.5, 0.35)

# Tombol "Publish" / "Post" di bagian atas form
_PUBLISH_BTN = (0.85, 0.08)

# Tombol attach / upload media (gambar)
_ATTACH_BTN = (0.1, 0.92)

# Delay antar navigasi (detik) — Requirements 9.1
_NAV_DELAY_MIN = 2.0
_NAV_DELAY_MAX = 5.0

# Delay antar tap/input (detik) — Requirements 9.1
_TAP_DELAY_MIN = 1.0
_TAP_DELAY_MAX = 3.0


# ---------------------------------------------------------------------------
# PostingBot
# ---------------------------------------------------------------------------


class PostingBot:
    """
    Bot untuk memposting konten ke LinkedIn via ADB.

    Urutan eksekusi:
    1. Validasi post (ada di DB, status draft/scheduled)
    2. Buka aplikasi LinkedIn
    3. Tap tombol New Post
    4. Input teks konten
    5. Upload gambar jika ada
    6. Tap tombol Publish
    7. Update Post.status = 'posted', Post.posted_at = now()
    8. Catat semua langkah ke BotLog

    Untuk thread post: ulangi langkah 3-6 untuk setiap thread_parts.

    Requirements: 2.7, 2.8, 2.10, 10.6
    """

    def __init__(
        self,
        adb_service: Any,
        log_service_module: Any = None,
        websocket_manager: Optional[Any] = None,
    ) -> None:
        """
        Inisialisasi PostingBot.

        Args:
            adb_service:        Instance ADBService untuk kontrol HP Android.
            log_service_module: Module log_service (opsional, default import global).
            websocket_manager:  Instance WebSocket ConnectionManager (opsional).
                                Jika None, progress tidak di-emit ke WebSocket.
        """
        self._adb = adb_service
        self._log_svc = log_service_module or log_service
        self._ws = websocket_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def post_content(self, post_id: int, db: AsyncSession) -> Post:
        """
        Ambil post dari DB dan posting ke LinkedIn via ADB.

        Pipeline:
        1. Load Post dari DB, validasi status
        2. Buka LinkedIn
        3. Navigasi ke form post baru
        4. Input konten (untuk thread: tiap bagian)
        5. Upload gambar jika image_url tersedia
        6. Tap Publish
        7. Update status Post di DB
        8. Catat semua langkah ke BotLog

        Args:
            post_id: ID post di tabel posts.
            db:      AsyncSession SQLAlchemy yang aktif.

        Returns:
            Objek Post yang sudah diperbarui.

        Raises:
            ValueError:  Jika post tidak ditemukan atau status bukan draft/scheduled.
            Exception:   Error ADB atau error tak terduga; status post diset 'failed'.

        Requirements: 2.7, 2.8, 2.10, 10.6
        """
        task_id = str(uuid.uuid4())
        post: Optional[Post] = None

        try:
            # ----------------------------------------------------------
            # Step 0: Load post dari database
            # ----------------------------------------------------------
            post = await self._load_post(post_id, db)
            await self._emit_progress(
                task_id=task_id,
                step="load_post",
                message=f"Post {post_id} ditemukan, memulai proses posting",
                post_id=post_id,
            )

            # ----------------------------------------------------------
            # Step 1: Buka LinkedIn
            # ----------------------------------------------------------
            await self._step_open_linkedin(task_id=task_id, db=db, post_id=post_id)

            # ----------------------------------------------------------
            # Step 2 & 3: Posting (thread atau single)
            # ----------------------------------------------------------
            if post.is_thread and post.thread_parts:
                await self._post_thread(
                    task_id=task_id,
                    db=db,
                    post=post,
                )
            else:
                await self._post_single(
                    task_id=task_id,
                    db=db,
                    post=post,
                )

            # ----------------------------------------------------------
            # Step final: Update status 'posted'
            # ----------------------------------------------------------
            post.status = "posted"
            post.posted_at = datetime.now(tz=timezone.utc)
            await db.flush()

            await self._log(
                db=db,
                task_id=task_id,
                action="publish_post",
                status="success",
                message=f"Post {post_id} berhasil dipublikasikan di LinkedIn",
                post_id=post_id,
                module="A",
            )
            await self._emit_progress(
                task_id=task_id,
                step="publish_post",
                message=f"Post {post_id} berhasil dipublikasikan",
                post_id=post_id,
                status="success",
            )

            logger.info("PostingBot: post_id=%d berhasil diposting (task=%s)", post_id, task_id)
            return post

        except Exception as exc:
            err_detail = str(exc)
            stack = traceback.format_exc()
            logger.error(
                "PostingBot: gagal posting post_id=%d (task=%s): %s",
                post_id, task_id, err_detail,
            )

            # Update status post menjadi 'failed' jika post sudah di-load
            if post is not None:
                try:
                    post.status = "failed"
                    await db.flush()
                except Exception as flush_err:
                    logger.error("PostingBot: gagal update status failed: %s", flush_err)

            # Catat error ke BotLog
            try:
                await self._log(
                    db=db,
                    task_id=task_id,
                    action="publish_post",
                    status="failed",
                    message=f"Gagal posting post_id={post_id}: {err_detail}",
                    error_detail=err_detail,
                    stack_trace=stack,
                    post_id=post_id,
                    module="A",
                )
            except Exception as log_err:
                logger.error("PostingBot: gagal mencatat error log: %s", log_err)

            await self._emit_progress(
                task_id=task_id,
                step="publish_post",
                message=f"Gagal: {err_detail}",
                post_id=post_id,
                status="failed",
            )
            raise

    # ------------------------------------------------------------------
    # Private — Loading & Validation
    # ------------------------------------------------------------------

    async def _load_post(self, post_id: int, db: AsyncSession) -> Post:
        """
        Muat post dari database dan validasi statusnya.

        Args:
            post_id: ID post yang akan dimuat.
            db:      AsyncSession aktif.

        Returns:
            Objek Post.

        Raises:
            ValueError: Jika post tidak ditemukan atau status bukan draft/scheduled.
        """
        result = await db.execute(select(Post).where(Post.id == post_id))
        post: Optional[Post] = result.scalar_one_or_none()

        if post is None:
            raise ValueError(f"Post dengan id={post_id} tidak ditemukan di database")

        if post.status not in ("draft", "scheduled"):
            raise ValueError(
                f"Post id={post_id} memiliki status '{post.status}', "
                "hanya draft/scheduled yang dapat diposting"
            )

        return post

    # ------------------------------------------------------------------
    # Private — Posting Steps
    # ------------------------------------------------------------------

    async def _step_open_linkedin(
        self,
        task_id: str,
        db: AsyncSession,
        post_id: int,
    ) -> None:
        """Langkah: buka aplikasi LinkedIn di HP."""
        await self._emit_progress(
            task_id=task_id,
            step="open_linkedin",
            message="Membuka aplikasi LinkedIn...",
            post_id=post_id,
        )

        await self._adb.open_app("com.linkedin.android")
        await self._log(
            db=db,
            task_id=task_id,
            action="open_linkedin",
            status="success",
            message="Aplikasi LinkedIn berhasil dibuka",
            post_id=post_id,
            module="A",
        )

        # Tunggu LinkedIn load
        delay = anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX)
        await asyncio.sleep(delay)

    async def _step_navigate_new_post(
        self,
        task_id: str,
        db: AsyncSession,
        post_id: int,
    ) -> None:
        """Langkah: tap tombol New Post di beranda LinkedIn."""
        await self._emit_progress(
            task_id=task_id,
            step="navigate_post",
            message="Navigasi ke form post baru...",
            post_id=post_id,
        )

        # Konversi koordinat relatif ke pixel
        width, height = await self._adb.get_screen_resolution()
        x = int(_NEW_POST_BTN[0] * width)
        y = int(_NEW_POST_BTN[1] * height)

        await self._adb.execute_tap(x, y)
        await self._log(
            db=db,
            task_id=task_id,
            action="navigate_post",
            status="success",
            message="Tombol new post berhasil di-tap",
            post_id=post_id,
            module="A",
        )

        delay = anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX)
        await asyncio.sleep(delay)

    async def _step_type_content(
        self,
        task_id: str,
        db: AsyncSession,
        post_id: int,
        text: str,
        part_number: Optional[int] = None,
    ) -> None:
        """Langkah: tap area input dan ketik konten."""
        label = f"bagian {part_number}" if part_number is not None else "konten"
        await self._emit_progress(
            task_id=task_id,
            step="type_content",
            message=f"Mengetik {label} ({len(text)} karakter)...",
            post_id=post_id,
        )

        # Tap area input teks
        width, height = await self._adb.get_screen_resolution()
        x = int(_POST_INPUT[0] * width)
        y = int(_POST_INPUT[1] * height)
        await self._adb.execute_tap(x, y)

        delay = anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX)
        await asyncio.sleep(delay)

        # Input teks (adb_service menangani pendek/panjang via clipboard otomatis)
        await self._adb.execute_input_text(text)
        await self._log(
            db=db,
            task_id=task_id,
            action="type_content",
            status="success",
            message=f"Teks {label} berhasil diinput ({len(text)} karakter)",
            post_id=post_id,
            module="A",
        )

        delay = anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX)
        await asyncio.sleep(delay)

    async def _step_upload_image(
        self,
        task_id: str,
        db: AsyncSession,
        post_id: int,
        image_url: str,
    ) -> None:
        """
        Langkah: upload gambar ke post.

        Saat ini tap tombol attach — URL gambar dicatat di log sebagai referensi.
        Implementasi penuh upload via intent atau adb push tergantung integrasi device.
        """
        await self._emit_progress(
            task_id=task_id,
            step="upload_image",
            message=f"Mengupload gambar: {image_url}",
            post_id=post_id,
        )

        # Tap tombol attach/media
        width, height = await self._adb.get_screen_resolution()
        x = int(_ATTACH_BTN[0] * width)
        y = int(_ATTACH_BTN[1] * height)
        await self._adb.execute_tap(x, y)

        delay = anti_ban.get_random_delay(_TAP_DELAY_MIN, _TAP_DELAY_MAX)
        await asyncio.sleep(delay)

        await self._log(
            db=db,
            task_id=task_id,
            action="upload_image",
            status="success",
            message=f"Tombol upload gambar di-tap (url={image_url})",
            post_id=post_id,
            module="A",
        )

    async def _step_publish(
        self,
        task_id: str,
        db: AsyncSession,
        post_id: int,
    ) -> None:
        """Langkah: tap tombol Publish/Post."""
        await self._emit_progress(
            task_id=task_id,
            step="publish_post",
            message="Menekan tombol Publish...",
            post_id=post_id,
        )

        width, height = await self._adb.get_screen_resolution()
        x = int(_PUBLISH_BTN[0] * width)
        y = int(_PUBLISH_BTN[1] * height)

        await self._adb.execute_tap(x, y)

        delay = anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX)
        await asyncio.sleep(delay)

        await self._log(
            db=db,
            task_id=task_id,
            action="publish_post",
            status="running",
            message="Tombol Publish berhasil di-tap, menunggu konfirmasi...",
            post_id=post_id,
            module="A",
        )

    # ------------------------------------------------------------------
    # Private — Single vs Thread posting
    # ------------------------------------------------------------------

    async def _post_single(
        self,
        task_id: str,
        db: AsyncSession,
        post: Post,
    ) -> None:
        """Posting satu post tunggal (bukan thread)."""
        await self._step_navigate_new_post(
            task_id=task_id, db=db, post_id=post.id
        )
        await self._step_type_content(
            task_id=task_id, db=db, post_id=post.id, text=post.content
        )
        if post.image_url:
            await self._step_upload_image(
                task_id=task_id, db=db, post_id=post.id, image_url=post.image_url
            )
        await self._step_publish(task_id=task_id, db=db, post_id=post.id)

    async def _post_thread(
        self,
        task_id: str,
        db: AsyncSession,
        post: Post,
    ) -> None:
        """
        Posting konten thread dengan memposting setiap bagian secara berurutan.

        Setiap bagian di thread_parts di-post sebagai satu post terpisah.
        Gambar hanya diupload pada bagian pertama jika image_url tersedia.

        Requirements: 2.11
        """
        parts: List[str] = post.thread_parts  # type: ignore[assignment]
        total = len(parts)

        await self._emit_progress(
            task_id=task_id,
            step="navigate_post",
            message=f"Memulai thread: {total} bagian",
            post_id=post.id,
        )

        for idx, part_text in enumerate(parts, start=1):
            await self._step_navigate_new_post(
                task_id=task_id, db=db, post_id=post.id
            )
            await self._step_type_content(
                task_id=task_id,
                db=db,
                post_id=post.id,
                text=part_text,
                part_number=idx,
            )

            # Upload gambar hanya di bagian pertama
            if idx == 1 and post.image_url:
                await self._step_upload_image(
                    task_id=task_id,
                    db=db,
                    post_id=post.id,
                    image_url=post.image_url,
                )

            await self._step_publish(task_id=task_id, db=db, post_id=post.id)

            await self._emit_progress(
                task_id=task_id,
                step="type_content",
                message=f"Thread bagian {idx}/{total} berhasil diposting",
                post_id=post.id,
                status="success",
            )

            # Anti-ban delay antar thread parts
            if idx < total:
                delay = anti_ban.get_random_delay(_NAV_DELAY_MIN, _NAV_DELAY_MAX)
                await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Private — Helpers
    # ------------------------------------------------------------------

    async def _log(
        self,
        db: AsyncSession,
        task_id: str,
        action: str,
        status: str,
        message: str,
        post_id: Optional[int] = None,
        error_detail: Optional[str] = None,
        stack_trace: Optional[str] = None,
        module: Optional[str] = None,
    ) -> BotLog:
        """
        Catat satu langkah ke tabel bot_logs via log_service.

        Requirements: 2.8, 7.1
        """
        return await self._log_svc.create_log(
            db,
            action=action,
            status=status,
            task_id=task_id,
            message=message,
            error_detail=error_detail,
            stack_trace=stack_trace,
            post_id=post_id,
            module=module,
        )

    async def _emit_progress(
        self,
        task_id: str,
        step: str,
        message: str,
        post_id: Optional[int] = None,
        status: str = "running",
    ) -> None:
        """
        Emit WebSocket progress event jika websocket_manager tersedia.

        Event payload:
        {
            "type": "bot_progress",
            "task_id": "<uuid>",
            "step": "<step_name>",
            "status": "running" | "success" | "failed",
            "message": "<deskripsi langkah>",
            "post_id": <int|null>
        }

        Requirements: 2.10
        """
        if self._ws is None:
            return

        payload: Dict[str, Any] = {
            "type": "bot_progress",
            "task_id": task_id,
            "step": step,
            "status": status,
            "message": message,
            "post_id": post_id,
        }

        try:
            # ConnectionManager belum diimplementasikan; panggil broadcast jika tersedia
            if hasattr(self._ws, "broadcast"):
                await self._ws.broadcast("bot_progress", payload)
        except Exception as exc:
            # Jangan biarkan WebSocket error menghentikan alur posting
            logger.warning("PostingBot: gagal emit WebSocket progress: %s", exc)
