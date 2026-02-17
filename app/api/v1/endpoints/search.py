from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.api import deps
from app.models.user import User
from app.models.post import Post
from app.models.clip import Clip
from app.schemas.user import UserPublic
from app.schemas.post import PostResponse
from app.schemas.clip import ClipResponse
from app.services.feed_service import post_to_response
from app.services.clip_service import clip_to_response

router = APIRouter()

class SearchResults(BaseModel):
    users: list[UserPublic]
    posts: list[PostResponse]
    clips: list[ClipResponse]

def _user_to_public(user: User, is_following: bool = False, is_requested: bool = False) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        is_verified=user.is_verified,
        followers_count=user.followers_count or 0,
        following_count=user.following_count or 0,
        who_can_comment=getattr(user, "who_can_comment", "everyone") or "everyone",
        is_private=getattr(user, "is_private", False),
        is_following=is_following,
        is_requested=is_requested,
        created_at=user.created_at,
    )

@router.get("/", response_model=SearchResults)
async def search(
    q: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    limit: int = 10,
) -> Any:
    """
    Search for users, posts, and clips.
    """
    query = q.strip()
    if not query:
        return SearchResults(users=[], posts=[], clips=[])
    
    # Search Users
    users_stmt = (
        select(User)
        .where(
            or_(
                User.username.ilike(f"%{query}%"),
                User.display_name.ilike(f"%{query}%")
            )
        )
        .limit(limit)
    )
    users_result = await db.execute(users_stmt)
    users = users_result.scalars().all()
    user_results = [_user_to_public(u) for u in users]

    # Search Posts
    posts_stmt = (
        select(Post)
        .where(Post.content.ilike(f"%{query}%"))
        .limit(limit)
        .options(selectinload(Post.user))
    )
    posts_result = await db.execute(posts_stmt)
    posts = posts_result.scalars().all()
    post_results = [post_to_response(p, is_liked=False, is_following_author=False) for p in posts]

    # Search Clips
    clips_stmt = (
        select(Clip)
        .where(Clip.caption.ilike(f"%{query}%"))
        .limit(limit)
        .options(selectinload(Clip.user))
    )
    clips_result = await db.execute(clips_stmt)
    clips = clips_result.scalars().all()
    clip_results = [clip_to_response(c, is_following_author=False) for c in clips]

    return SearchResults(
        users=user_results,
        posts=post_results,
        clips=clip_results,
    )
