"""Clips CRUD and feed."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_user, get_current_user_optional
from app.services.feed_service import get_following_author_ids
from app.models.user import User
from app.models.engagement import Like
from app.models.clip import Clip
from app.models.comment import Comment
from app.schemas.clip import ClipCreate, ClipResponse
from app.schemas.comment import CommentCreate, CommentResponse
from app.schemas.user import UserPublic
from app.services.clip_service import create_clip, get_clips_feed, clip_to_response
from app.services.notification_service import create_notification
from app.workers.video_processing import generate_thumbnail, process_video_upload

router = APIRouter(prefix="/clips", tags=["clips"])


def _comment_to_response(comment: Comment, is_liked: bool = False) -> CommentResponse:
    user = comment.user
    user_public = UserPublic(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        is_verified=user.is_verified,
        followers_count=user.followers_count,
        following_count=user.following_count,
        created_at=user.created_at,
    ) if user else None
    return CommentResponse(
        id=comment.id,
        user_id=comment.user_id,
        content=comment.content,
        created_at=comment.created_at,
        parent_id=comment.parent_id,
        user=user_public,
        likes_count=comment.likes_count or 0,
        is_liked=is_liked,
    )


async def _get_user_liked_comment_ids(db: AsyncSession, user_id: UUID, comment_ids: list[UUID]) -> set[UUID]:
    if not comment_ids:
        return set()
    result = await db.execute(
        select(Like.comment_id).where(
            Like.comment_id.in_(comment_ids),
            Like.user_id == user_id,
        )
    )
    return {r[0] for r in result.all() if r[0]}


@router.post("", response_model=ClipResponse, status_code=status.HTTP_201_CREATED)
async def create_clip_endpoint(
    data: ClipCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    clip = await create_clip(db, current_user.id, data)
    await db.commit()
    await db.refresh(clip)
    clip.user = current_user
    if clip.video_url:
        try:
            process_video_upload.delay(str(clip.id), clip.video_url)
            generate_thumbnail.delay(str(clip.id), clip.video_url)
        except Exception as e:
            print(f"[Clips] WARNING: Failed to enqueue background tasks: {e}")
            # We don't raise here because the clip record itself was successfully created/committed
    return clip_to_response(clip)


@router.get("", response_model=list[ClipResponse])
async def list_clips(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    clips = await get_clips_feed(db, skip=skip, limit=limit)
    author_ids = list({c.user_id for c in clips})
    following_ids = await get_following_author_ids(db, current_user.id, author_ids) if current_user else set()
    return [
        clip_to_response(c, is_following_author=c.user_id in following_ids)
        for c in clips
    ]


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Clip).where(Clip.id == clip_id).options(selectinload(Clip.user))
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    return clip_to_response(clip)


@router.post("/{clip_id}/view")
async def record_clip_view(
    clip_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Record a view for a clip. Increments views_count in DB. Returns updated count."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    clip.views_count = (clip.views_count or 0) + 1
    await db.commit()
    await db.refresh(clip)
    return {"views_count": clip.views_count}


@router.get("/{clip_id}/comments", response_model=list[CommentResponse])
async def list_clip_comments(
    clip_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Comment)
        .where(Comment.clip_id == clip_id)
        .order_by(desc(Comment.created_at))
        .offset(skip)
        .limit(limit)
        .options(selectinload(Comment.user))
    )
    comments = result.scalars().all()
    liked_ids = await _get_user_liked_comment_ids(db, current_user.id, [c.id for c in comments]) if current_user else set()
    return [_comment_to_response(c, is_liked=c.id in liked_ids) for c in comments]


@router.post("/{clip_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_clip_comment(
    clip_id: UUID,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Clip).where(Clip.id == clip_id).options(selectinload(Clip.user))
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    author = clip.user
    author_wcc = getattr(author, "who_can_comment", "everyone") or "everyone"
    if author_wcc == "no_one" and clip.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Comments are disabled on this clip")
    comment = Comment(
        user_id=current_user.id,
        clip_id=clip_id,
        content=data.content,
        parent_id=data.parent_id,
    )
    db.add(comment)
    clip.comments_count = (clip.comments_count or 0) + 1
    content_preview = data.content[:50] + "..." if len(data.content) > 50 else data.content
    notify_user_id = clip.user_id
    if data.parent_id:
        parent_result = await db.execute(
            select(Comment).where(Comment.id == data.parent_id)
        )
        parent = parent_result.scalar_one_or_none()
        if parent:
            notify_user_id = parent.user_id
    text = f'{current_user.display_name or current_user.username} replied to your comment: "{content_preview}"' if data.parent_id else f'{current_user.display_name or current_user.username} commented on your clip: "{content_preview}"'
    await create_notification(
        db,
        user_id=notify_user_id,
        actor_id=current_user.id,
        notification_type="comment",
        text=text,
        target_clip_id=clip_id,
        target_comment_id=comment.id,
    )
    await db.commit()
    await db.refresh(comment)
    comment.user = current_user
    return _comment_to_response(comment, is_liked=False)


@router.post("/{clip_id}/comments/{comment_id}/like", response_model=CommentResponse)
async def like_clip_comment(
    clip_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Comment)
        .where(Comment.id == comment_id, Comment.clip_id == clip_id)
        .options(selectinload(Comment.user))
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    existing = await db.execute(
        select(Like).where(Like.comment_id == comment_id, Like.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        return _comment_to_response(comment, is_liked=True)
    like = Like(user_id=current_user.id, comment_id=comment_id)
    db.add(like)
    comment.likes_count = (comment.likes_count or 0) + 1
    await create_notification(
        db,
        user_id=comment.user_id,
        actor_id=current_user.id,
        notification_type="like",
        text=f"{current_user.display_name or current_user.username} liked your comment",
        target_clip_id=clip_id,
        target_comment_id=comment_id,
    )
    await db.commit()
    await db.refresh(comment)
    return _comment_to_response(comment, is_liked=True)


@router.delete("/{clip_id}/comments/{comment_id}/like", response_model=CommentResponse)
async def unlike_clip_comment(
    clip_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Comment)
        .where(Comment.id == comment_id, Comment.clip_id == clip_id)
        .options(selectinload(Comment.user))
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    like_result = await db.execute(
        select(Like).where(Like.comment_id == comment_id, Like.user_id == current_user.id)
    )
    like = like_result.scalar_one_or_none()
    if like:
        await db.delete(like)
        comment.likes_count = max(0, (comment.likes_count or 0) - 1)
    await db.commit()
    await db.refresh(comment)
    return _comment_to_response(comment, is_liked=False)
