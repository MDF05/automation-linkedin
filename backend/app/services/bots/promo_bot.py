"""
Promo Bot — Module B: Posting Konten Promosi ke LinkedIn.

Komponen ini adalah wrapper tipis di atas PostingBot yang:
- Memastikan content_type post diset ke 'promo' sebelum posting (Requirements 3.6)
- Mencoba upload gambar jika post memiliki image_url; jika image_service gagal,
  melanjutkan posting tanpa gambar (fallback per Requirements 3.7)
- Mendelegasikan semua langkah ADB ke PostingBot.post_content()

Alur eksekusi:
1. Load post dari database
2. Pastikan content_type = 'promo'
3. Jika post memiliki image_url: coba generate/validasi gambar via image_service
   - Jika image_service gagal: log warning, hapus image_url dari post (fallback)
4. Delegasikan ke PostingBot.post_content() untuk eksekusi ADB

Requirements: 3.6, 3.7
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.services.bots.posting_bot import PostingBot

logger = logging.getLogger(__name__)


class PromoBot:
    """
    Bot untuk memposting konten promosi ke LinkedIn via ADB.

    Wrapper tipis di atas PostingBot yang menambahkan:
    - Validasi dan assignment content_type = 'promo'
    - Fallback tanpa gambar jika image_service gagal (Requirements 3.7)

    Semua langkah ADB dan logging didelegasikan ke PostingBot.

    Requirements: 3.6, 3.7
    """

    def __init__(
        self,
        adb_service: Any,
        log_service: Any = None,
        image_service: Optional[Any] = None,
        websocket_manager: Optional[Any] = None,
    ) -> None:
        """
        Inisialisasi PromoBot.

        Args:
            adb_service:       Instance ADBService untuk kontrol HP Android.
            log_service:       Module log_service (opsional, diteruskan ke PostingBot).
            image_service:     Module atau callable image_service untuk validasi/generate
                               gambar. Jika None, image step dilewati.
            websocket_manager: Instance WebSocket ConnectionManager (opsional).
                               Diteruskan ke PostingBot untuk emit progress.
        """
        self._image_service = image_service
        self._posting_bot = PostingBot(
            adb_service=adb_service,
            log_service_module=log_service,
            websocket_manager=websocket_manager,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def post_promo(self, post_id: int, db: AsyncSession) -> Post:
        """
        Posting konten promosi ke LinkedIn.

        Pipeline:
        1. Load Post dari database
        2. Set content_type = 'promo' jika belum diset
        3. Jika post memiliki image_url: coba upload gambar
           - Jika image_service gagal: log warning, lanjutkan tanpa gambar (Req 3.7)
        4. Delegasikan ke PostingBot.post_content() untuk eksekusi ADB

        Args:
            post_id: ID post di tabel posts.
            db:      AsyncSession SQLAlchemy yang aktif.

        Returns:
            Objek Post yang sudah diperbarui (status='posted').

        Raises:
            ValueError: Jika post tidak ditemukan atau status bukan draft/scheduled.
            Exception:  Error ADB atau error tak terduga; status post diset 'failed'.

        Requirements: 3.6, 3.7
        """
        # ------------------------------------------------------------------
        # Step 1: Load post dan pastikan content_type = 'promo'
        # ------------------------------------------------------------------
        result = await db.execute(select(Post).where(Post.id == post_id))
        post: Optional[Post] = result.scalar_one_or_none()

        if post is None:
            raise ValueError(f"Post dengan id={post_id} tidak ditemukan di database")

        if post.status not in ("draft", "scheduled"):
            raise ValueError(
                f"Post id={post_id} memiliki status '{post.status}', "
                "hanya draft/scheduled yang dapat diposting"
            )

        # Requirements 3.6: pastikan content_type diset ke 'promo'
        if post.content_type != "promo":
            logger.info(
                "PromoBot: mengubah content_type post_id=%d dari '%s' ke 'promo'",
                post_id,
                post.content_type,
            )
            post.content_type = "promo"
            await db.flush()

        # ------------------------------------------------------------------
        # Step 2: Fallback gambar jika image_service gagal (Requirements 3.7)
        # ------------------------------------------------------------------
        if post.image_url and self._image_service is not None:
            await self._try_image_or_fallback(post, db)

        # ------------------------------------------------------------------
        # Step 3: Delegasikan ke PostingBot
        # ------------------------------------------------------------------
        return await self._posting_bot.post_content(post_id=post_id, db=db)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _try_image_or_fallback(self, post: Post, db: AsyncSession) -> None:
        """
        Coba validasi ketersediaan gambar via image_service.

        Jika image_service melempar exception apapun, log warning dan hapus
        image_url dari post agar PostingBot melanjutkan tanpa gambar.

        Args:
            post: Objek Post yang sudah di-load.
            db:   AsyncSession aktif.

        Requirements: 3.7
        """
        try:
            # image_service bisa berupa module dengan fungsi generate_image,
            # atau objek dengan method generate_image.
            # PromoBot hanya memverifikasi bahwa gambar dapat diakses —
            # upload aktual tetap ditangani oleh PostingBot._step_upload_image
            # yang menggunakan image_url yang sudah ada di post.
            #
            # Jika image_service memiliki callable `validate_image_url`, gunakan itu.
            # Fallback: jika tidak ada validator, asumsikan URL valid (no-op).
            if hasattr(self._image_service, "validate_image_url"):
                await self._image_service.validate_image_url(post.image_url)
            # Jika tidak ada metode validasi, image dianggap valid; tidak ada aksi.

        except Exception as exc:
            # Requirements 3.7: fallback tanpa gambar
            logger.warning(
                "PromoBot: image_service gagal untuk post_id=%d (url=%s): %s — "
                "melanjutkan posting tanpa gambar (fallback).",
                post.id,
                post.image_url,
                exc,
            )
            post.image_url = None
            await db.flush()
