"""Posts CRUD and feed."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sqlalchemy import desc

from app.api.deps import get_db, get_current_user, get_current_user_optional
from app.models.user import User
from app.models.post import Post
from app.models.comment import Comment
from app.models.engagement import Like
from app.schemas.post import PostCreate, PostUpdate, PostResponse
from app.schemas.comment import CommentCreate, CommentResponse
from app.schemas.user import UserPublic
from app.services.feed_service import create_post, update_post, delete_post, get_feed_posts, get_user_liked_post_ids, post_to_response
from app.services.repost_service import create_repost as create_repost_svc, repost_to_response
from app.services.notification_service import create_notification
from app.schemas.repost import RepostCreate, RepostResponse

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post_endpoint(
    data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = await create_post(db, current_user.id, data)
    await db.commit()
    await db.refresh(post)
    post.user = current_user
    return post_to_response(post, is_liked=False)


@router.get("", response_model=list[PostResponse])
async def list_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    posts = await get_feed_posts(db, current_user.id, skip=skip, limit=limit)
    liked_ids = await get_user_liked_post_ids(db, current_user.id, [p.id for p in posts])
    return [post_to_response(p, is_liked=p.id in liked_ids) for p in posts]


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.user))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    is_liked = False
    if current_user:
        liked_ids = await get_user_liked_post_ids(db, current_user.id, [post.id])
        is_liked = post.id in liked_ids
    return post_to_response(post, is_liked=is_liked)


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post_endpoint(
    post_id: UUID,
    data: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = await update_post(db, post_id, current_user.id, data)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    liked_ids = await get_user_liked_post_ids(db, current_user.id, [post.id])
    await db.commit()
    await db.refresh(post)
    return post_to_response(post, is_liked=post.id in liked_ids)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post_endpoint(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_post(db, post_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    await db.commit()
    return None


@router.post("/{post_id}/like", response_model=PostResponse)
async def like_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.user))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    existing = await db.execute(
        select(Like).where(Like.post_id == post_id, Like.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        return post_to_response(post, is_liked=True)
    like = Like(user_id=current_user.id, post_id=post_id)
    db.add(like)
    post.likes_count = (post.likes_count or 0) + 1
    await create_notification(
        db,
        user_id=post.user_id,
        actor_id=current_user.id,
        notification_type="like",
        text=f"{current_user.display_name or current_user.username} liked your post",
        target_post_id=post_id,
    )
    await db.commit()
    await db.refresh(post)
    return post_to_response(post, is_liked=True)


@router.post("/{post_id}/repost", response_model=RepostResponse, status_code=status.HTTP_201_CREATED)
async def repost_post(
    post_id: UUID,
    data: RepostCreate = RepostCreate(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await create_repost_svc(db, current_user.id, post_id, data.quote_text)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    repost, post = result
    await db.commit()
    await db.refresh(repost)
    repost.user = current_user
    repost.post = post
    return repost_to_response(repost)


@router.delete("/{post_id}/like", response_model=PostResponse)
async def unlike_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.user))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    like_result = await db.execute(
        select(Like).where(Like.post_id == post_id, Like.user_id == current_user.id)
    )
    like = like_result.scalar_one_or_none()
    if like:
        await db.delete(like)
        post.likes_count = max(0, (post.likes_count or 0) - 1)
    await db.commit()
    await db.refresh(post)
    return post_to_response(post, is_liked=False)


def comment_to_response(comment: Comment, is_liked: bool = False) -> CommentResponse:
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


async def get_user_liked_comment_ids(db: AsyncSession, user_id: UUID, comment_ids: list[UUID]) -> set[UUID]:
    if not comment_ids:
        return set()
    result = await db.execute(
        select(Like.comment_id).where(
            Like.comment_id.in_(comment_ids),
            Like.user_id == user_id,
        )
    )
    return {r[0] for r in result.all() if r[0]}


@router.get("/{post_id}/comments", response_model=list[CommentResponse])
async def list_post_comments(
    post_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Comment)
        .where(Comment.post_id == post_id)
        .order_by(desc(Comment.created_at))
        .offset(skip)
        .limit(limit)
        .options(selectinload(Comment.user))
    )
    comments = result.scalars().all()
    liked_ids = await get_user_liked_comment_ids(db, current_user.id, [c.id for c in comments]) if current_user else set()
    return [comment_to_response(c, is_liked=c.id in liked_ids) for c in comments]


@router.post("/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_post_comment(
    post_id: UUID,
    data: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id).options(selectinload(Post.user))
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    author = post.user
    author_wcc = getattr(author, "who_can_comment", "everyone") or "everyone"
    if author_wcc == "no_one" and post.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Comments are disabled on this post")
    comment = Comment(
        user_id=current_user.id,
        post_id=post_id,
        content=data.content,
        parent_id=data.parent_id,
    )
    db.add(comment)
    post.comments_count = (post.comments_count or 0) + 1
    content_preview = data.content[:50] + "..." if len(data.content) > 50 else data.content
    notify_user_id = post.user_id
    if data.parent_id:
        parent_result = await db.execute(
            select(Comment).where(Comment.id == data.parent_id)
        )
        parent = parent_result.scalar_one_or_none()
        if parent:
            notify_user_id = parent.user_id
    text = f'{current_user.display_name or current_user.username} replied to your comment: "{content_preview}"' if data.parent_id else f'{current_user.display_name or current_user.username} commented: "{content_preview}"'
    await create_notification(
        db,
        user_id=notify_user_id,
        actor_id=current_user.id,
        notification_type="comment",
        text=text,
        target_post_id=post_id,
        target_comment_id=comment.id,
    )
    await db.commit()
    await db.refresh(comment)
    comment.user = current_user
    return comment_to_response(comment, is_liked=False)


@router.post("/{post_id}/comments/{comment_id}/like", response_model=CommentResponse)
async def like_post_comment(
    post_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Comment)
        .where(Comment.id == comment_id, Comment.post_id == post_id)
        .options(selectinload(Comment.user))
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    existing = await db.execute(
        select(Like).where(Like.comment_id == comment_id, Like.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        return comment_to_response(comment, is_liked=True)
    like = Like(user_id=current_user.id, comment_id=comment_id)
    db.add(like)
    comment.likes_count = (comment.likes_count or 0) + 1
    await create_notification(
        db,
        user_id=comment.user_id,
        actor_id=current_user.id,
        notification_type="like",
        text=f"{current_user.display_name or current_user.username} liked your comment",
        target_post_id=post_id,
        target_comment_id=comment_id,
    )
    await db.commit()
    await db.refresh(comment)
    return comment_to_response(comment, is_liked=True)


@router.delete("/{post_id}/comments/{comment_id}/like", response_model=CommentResponse)
async def unlike_post_comment(
    post_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Comment)
        .where(Comment.id == comment_id, Comment.post_id == post_id)
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
    return comment_to_response(comment, is_liked=False)
