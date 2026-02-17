"""Feed and post business logic."""
from uuid import UUID

from sqlalchemy import select, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.post import Post
from app.models.user import User
from app.models.engagement import Follow, Like
from app.schemas.post import PostCreate, PostUpdate, PostResponse
from app.schemas.user import UserPublic


async def create_post(db: AsyncSession, user_id: UUID, data: PostCreate) -> Post:
    post = Post(
        user_id=user_id,
        content=data.content,
        media_urls=data.media_urls,
        visibility=getattr(data, "visibility", "public") or "public",
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)
    return post


async def update_post(db: AsyncSession, post_id: UUID, owner_id: UUID, data: PostUpdate) -> Post | None:
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == owner_id).options(selectinload(Post.user))
    )
    post = result.scalar_one_or_none()
    if not post:
        return None
    if data.content is not None:
        post.content = data.content
    if data.media_urls is not None:
        post.media_urls = data.media_urls
    await db.flush()
    await db.refresh(post)
    return post


async def delete_post(db: AsyncSession, post_id: UUID, owner_id: UUID) -> bool:
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == owner_id)
    )
    post = result.scalar_one_or_none()
    if not post:
        return False
    await db.delete(post)
    await db.flush()
    return True


async def get_feed_posts(
    db: AsyncSession,
    current_user_id: UUID | None,
    skip: int = 0,
    limit: int = 50,
) -> list[Post]:
    # Base: all posts with user
    q = select(Post).order_by(desc(Post.created_at)).options(selectinload(Post.user))

    if current_user_id is None:
        # Guest: only public posts
        q = q.where(Post.visibility == "public")
    else:
        # Logged in: public OR (private and author) OR (followers_only and current user follows author)
        subq_following = select(Follow.following_id).where(Follow.follower_id == current_user_id)
        q = q.where(
            or_(
                Post.visibility == "public",
                and_(Post.visibility == "private", Post.user_id == current_user_id),
                and_(
                    Post.visibility == "followers_only",
                    or_(Post.user_id == current_user_id, Post.user_id.in_(subq_following)),
                ),
            )
        )

    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_following_author_ids(
    db: AsyncSession,
    follower_id: UUID,
    author_ids: list[UUID],
) -> set[UUID]:
    """Return set of author IDs that the follower follows."""
    if not author_ids:
        return set()
    result = await db.execute(
        select(Follow.following_id).where(
            Follow.follower_id == follower_id,
            Follow.following_id.in_(author_ids),
        )
    )
    return set(row[0] for row in result.all() if row[0])


async def get_user_liked_post_ids(
    db: AsyncSession,
    user_id: UUID,
    post_ids: list[UUID],
) -> set[UUID]:
    """Return set of post IDs that the user has liked."""
    if not post_ids:
        return set()
    result = await db.execute(
        select(Like.post_id).where(
            Like.user_id == user_id,
            Like.post_id.in_(post_ids),
        )
    )
    return set(row[0] for row in result.all() if row[0])


async def get_user_posts_visible(
    db: AsyncSession,
    author_id: UUID,
    viewer_id: UUID | None,
    skip: int = 0,
    limit: int = 50,
) -> list[Post]:
    """Get a user's posts with visibility filtering."""
    q = (
        select(Post)
        .where(Post.user_id == author_id)
        .order_by(desc(Post.created_at))
        .offset(skip)
        .limit(limit)
        .options(selectinload(Post.user))
    )
    if viewer_id is None:
        q = q.where(Post.visibility == "public")
    else:
        subq_following = select(Follow.following_id).where(Follow.follower_id == viewer_id)
        q = q.where(
            or_(
                Post.visibility == "public",
                and_(Post.visibility == "private", Post.user_id == viewer_id),
                and_(
                    Post.visibility == "followers_only",
                    or_(Post.user_id == viewer_id, Post.user_id.in_(subq_following)),
                ),
            )
        )
    result = await db.execute(q)
    return list(result.scalars().all())


def post_to_response(post: Post, is_liked: bool = False, is_following_author: bool = False) -> PostResponse:
    user = post.user
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
    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        content=post.content,
        media_urls=post.media_urls or [],
        likes_count=post.likes_count,
        comments_count=post.comments_count,
        reposts_count=post.reposts_count,
        views_count=post.views_count,
        created_at=post.created_at,
        user=user_public,
        visibility=getattr(post, "visibility", "public") or "public",
        is_liked=is_liked,
    )
