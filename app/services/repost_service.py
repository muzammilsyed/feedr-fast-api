"""Repost business logic."""
from uuid import UUID

from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.engagement import Repost, Follow
from app.models.post import Post
from app.schemas.repost import RepostResponse
from app.schemas.user import UserPublic
from app.services.feed_service import post_to_response


def repost_to_response(repost) -> RepostResponse:
    """Build API response from Repost ORM object (must have user and post loaded)."""
    reposter_user = UserPublic(
        id=repost.user.id,
        username=repost.user.username,
        display_name=repost.user.display_name,
        bio=repost.user.bio,
        avatar_url=repost.user.avatar_url,
        is_verified=repost.user.is_verified,
        followers_count=repost.user.followers_count,
        following_count=repost.user.following_count,
        who_can_comment=getattr(repost.user, "who_can_comment", "everyone") or "everyone",
        created_at=repost.user.created_at,
        is_following=False,
    ) if repost.user else None
    original = post_to_response(repost.post, is_liked=False) if (repost.post and repost.post.user) else None
    return RepostResponse(
        id=repost.id,
        quote_text=repost.quote_text or "",
        original_type="post",
        created_at=repost.created_at,
        reposter_user=reposter_user,
        original_post=original,
    )


async def create_repost(
    db: AsyncSession,
    user_id: UUID,
    post_id: UUID,
    quote_text: str = "",
) -> tuple[Repost, Post] | None:
    """Create a repost and increment post.reposts_count. Returns (repost, post) for response building."""
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.user))
    )
    post = result.scalar_one_or_none()
    if not post:
        return None
    repost = Repost(user_id=user_id, post_id=post_id, quote_text=(quote_text or "").strip())
    db.add(repost)
    post.reposts_count = (post.reposts_count or 0) + 1
    await db.flush()
    await db.refresh(repost)
    return (repost, post)


async def get_feed_reposts(
    db: AsyncSession,
    current_user_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[Repost]:
    """Get reposts from:
    (1) current user's own reposts
    (2) reposts by users the current user follows
    (3) reposts of posts by users the current user follows (see "X reposted Y's post" when you follow Y)
    (4) reposts of public posts (see reposts of any public content)
    """
    subq_following = select(Follow.following_id).where(Follow.follower_id == current_user_id)
    q = (
        select(Repost)
        .join(Post, Repost.post_id == Post.id)
        .where(
            or_(
                Repost.user_id == current_user_id,
                Repost.user_id.in_(subq_following),
                Post.user_id.in_(subq_following),
                Post.user_id == current_user_id,
                Post.visibility == "public",
            )
        )
        .order_by(desc(Repost.created_at))
        .offset(skip)
        .limit(limit)
        .options(
            selectinload(Repost.user),
            selectinload(Repost.post).selectinload(Post.user),
        )
    )
    result = await db.execute(q)
    return list(result.scalars().all())
