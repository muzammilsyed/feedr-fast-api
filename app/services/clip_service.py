"""Clip business logic."""
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.clip import Clip
from app.schemas.clip import ClipCreate, ClipResponse
from app.schemas.user import UserPublic


async def create_clip(db: AsyncSession, user_id: UUID, data: ClipCreate) -> Clip:
    clip = Clip(
        user_id=user_id,
        video_url=data.video_url,
        thumbnail_url=data.thumbnail_url,
        caption=data.caption,
        audio_id=data.audio_id,
        duration=data.duration,
    )
    db.add(clip)
    await db.flush()
    await db.refresh(clip)
    return clip


async def get_clips_feed(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 20,
) -> list[Clip]:
    q = select(Clip).order_by(desc(Clip.created_at)).offset(skip).limit(limit)
    q = q.options(selectinload(Clip.user))
    result = await db.execute(q)
    return list(result.scalars().all())


def clip_to_response(clip: Clip, is_following_author: bool = False) -> ClipResponse:
    user = clip.user
    user_public = UserPublic(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        is_verified=user.is_verified,
        followers_count=user.followers_count,
        following_count=user.following_count,
        who_can_comment=getattr(user, "who_can_comment", "everyone") or "everyone",
        created_at=user.created_at,
        is_following=is_following_author,
    ) if user else None
    return ClipResponse(
        id=clip.id,
        user_id=clip.user_id,
        video_url=clip.video_url,
        thumbnail_url=clip.thumbnail_url,
        caption=clip.caption,
        audio_id=clip.audio_id,
        duration=clip.duration,
        likes_count=clip.likes_count,
        comments_count=clip.comments_count,
        shares_count=clip.shares_count,
        views_count=clip.views_count,
        created_at=clip.created_at,
        user=user_public,
    )
