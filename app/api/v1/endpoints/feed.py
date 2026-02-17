"""Unified feed endpoint (posts and reposts for home feed)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.feed import FeedItemPost, FeedItemRepost, FeedItemResponse
from app.schemas.repost import RepostResponse
from app.services.feed_service import get_feed_posts, get_user_liked_post_ids, get_following_author_ids, post_to_response
from app.services.repost_service import get_feed_reposts, repost_to_response

router = APIRouter(prefix="/feed", tags=["feed"])


def _build_unified_feed(
    posts: list,
    reposts: list,
    liked_ids: set,
    following_ids: set,
    skip: int,
    limit: int,
) -> list[FeedItemResponse]:
    """Merge posts and reposts; reposts use repost.created_at (when reposted) as feed time."""
    items: list[tuple[float, str, object]] = []
    for p in posts:
        ts = p.created_at.timestamp() if p.created_at else 0.0
        items.append((ts, "post", p))
    for r in reposts:
        ts = r.created_at.timestamp() if r.created_at else 0.0
        items.append((ts, "repost", r))
    items.sort(key=lambda x: x[0], reverse=True)
    page = items[skip : skip + limit]

    result: list[FeedItemResponse] = []
    for _, typ, obj in page:
        if typ == "post":
            p = obj
            result.append(
                FeedItemPost(post=post_to_response(p, is_liked=p.id in liked_ids, is_following_author=p.user_id in following_ids))
            )
        else:
            result.append(FeedItemRepost(repost=repost_to_response(obj)))
    return result


@router.get("", response_model=list[FeedItemResponse])
async def get_feed(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Fetch extra to allow correct interleaving (reposts as "new" items by repost time)
    fetch_limit = skip + limit
    posts = await get_feed_posts(db, current_user.id, skip=0, limit=fetch_limit * 2)
    reposts = await get_feed_reposts(db, current_user.id, skip=0, limit=fetch_limit * 2)
    liked_ids = await get_user_liked_post_ids(db, current_user.id, [p.id for p in posts])
    author_ids = list({p.user_id for p in posts})
    following_ids = await get_following_author_ids(db, current_user.id, author_ids)
    return _build_unified_feed(posts, reposts, liked_ids, following_ids, skip, limit)


@router.get("/reposts", response_model=list[RepostResponse])
async def get_feed_reposts_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reposts = await get_feed_reposts(db, current_user.id, skip=skip, limit=limit)
    return [repost_to_response(r) for r in reposts]
