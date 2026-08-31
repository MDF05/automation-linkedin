"""
Content Router — API endpoints untuk pembuatan dan manajemen konten LinkedIn.

Requirements: 2.1–2.11, 3.1–3.7, 10.1–10.6
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.post import Post
from app.schemas.post import (
    PostCreate,
    PostGenerateRequest,
    PostGenerateResponse,
    PostRead,
    PostUpdate,
)

router = APIRouter(prefix="/content", tags=["content"])


# ---------------------------------------------------------------------------
# Generate Content
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=PostGenerateResponse)
async def generate_content(
    request: PostGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    POST /api/content/generate

    Generate 3 variasi konten LinkedIn berdasarkan topik dan parameter.
    Memanggil search_service + ai_service.

    Requirements: 2.1–2.4, 2.9
    """
    try:
        from app.services.content_generator import generate_content as gen_content
        variants, references, provider = await gen_content(
            topic=request.topic,
            description=request.description,
            content_type=request.content_type.value,
            tone=request.tone.value,
            length=request.length.value,
            db=db,
        )

        image_url: Optional[str] = None
        if request.generate_image and request.content_type.value in ("kutipan", "tips_list"):
            try:
                from app.services.image_service import generate_image
                image_url = await generate_image(
                    prompt=f"{request.topic} - {request.content_type.value}",
                    provider="ideogram",
                )
            except Exception:
                pass  # Gambar opsional, jangan gagalkan request

        return PostGenerateResponse(
            variants=variants,
            image_url=image_url,
            search_references=references,
            ai_provider_used=provider,
        )

    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Posts CRUD
# ---------------------------------------------------------------------------


@router.post("/posts", response_model=PostRead, status_code=201)
async def create_post(
    body: PostCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    POST /api/content/posts

    Simpan post baru (draft atau jadwal).

    Requirements: 10.1
    """
    post = Post(
        title=body.title,
        content=body.content,
        content_type=body.content_type.value,
        tone=body.tone.value if body.tone else None,
        status=body.status.value,
        image_url=body.image_url,
        is_thread=body.is_thread,
        thread_parts=body.thread_parts,
        thread_count=body.thread_count,
        scheduled_at=body.scheduled_at,
        ai_provider_used=body.ai_provider_used,
        prompt_used=body.prompt_used,
        search_references=body.search_references,
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)
    return post


@router.get("/posts", response_model=List[PostRead])
async def list_posts(
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/content/posts

    List posts dengan filter status dan tanggal.

    Requirements: 10.1
    """
    q = select(Post)
    if status:
        q = q.where(Post.status == status)
    if date_from:
        q = q.where(Post.created_at >= date_from)
    if date_to:
        q = q.where(Post.created_at <= date_to)
    q = q.order_by(Post.created_at.desc()).offset((page - 1) * limit).limit(limit)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/posts/export")
async def export_posts_csv(
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    GET /api/content/posts/export

    Download CSV posts dengan filter.

    Requirements: 11.1, 11.2
    """
    from fastapi.responses import Response

    from app.services.csv_exporter import export_posts
    csv_bytes = await export_posts(
        db, status=status, date_from=date_from, date_to=date_to
    )
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8-bom",
        headers={"Content-Disposition": "attachment; filename=posts.csv"},
    )


@router.get("/posts/{post_id}", response_model=PostRead)
async def get_post(post_id: int, db: AsyncSession = Depends(get_db)) -> Any:
    """
    GET /api/content/posts/{id}

    Detail satu post.

    Requirements: 10.2
    """
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post tidak ditemukan")
    return post


@router.patch("/posts/{post_id}", response_model=PostRead)
async def update_post(
    post_id: int,
    body: PostUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    PATCH /api/content/posts/{id}

    Update sebagian field post (draft editing).

    Requirements: 10.5
    """
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post tidak ditemukan")

    for field_name, value in body.model_dump(exclude_unset=True).items():
        if value is not None or field_name in ("image_url", "scheduled_at"):
            setattr(post, field_name, value)

    await db.flush()
    await db.refresh(post)
    return post


@router.post("/posts/{post_id}/publish")
async def publish_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    POST /api/content/posts/{id}/publish

    Trigger posting bot untuk memposting ke LinkedIn.

    Requirements: 2.7, 2.8, 2.10
    """
    import uuid
    from app.services.adb_service import ADBService, ADBTimeoutError
    from app.services.bots.posting_bot import PostingBot

    try:
        from app.core.websocket_manager import manager as ws_manager
        adb = ADBService()
        bot = PostingBot(adb_service=adb, websocket_manager=ws_manager)
        task_id = str(uuid.uuid4())

        # Run in background — di produksi gunakan BackgroundTasks
        import asyncio
        asyncio.create_task(bot.post_content(post_id, db))

        return {
            "task_id": task_id,
            "post_id": post_id,
            "status": "started",
            "started_at": datetime.now().isoformat(),
        }
    except ADBTimeoutError as exc:
        raise HTTPException(status_code=503, detail=f"HP tidak terhubung: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/image/generate")
async def generate_image_endpoint(
    body: Dict[str, str],
) -> Dict[str, Any]:
    """
    POST /api/content/image/generate

    Generate gambar via image_service.

    Requirements: 2.5, 3.4
    """
    try:
        from app.services.image_service import generate_image
        prompt = body.get("prompt", "")
        provider = body.get("provider", "ideogram")
        image_url = await generate_image(prompt=prompt, provider=provider)
        return {"image_url": image_url, "provider": provider}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
