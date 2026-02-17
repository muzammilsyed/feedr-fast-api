from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api import deps
from app.models.user import User
from app.models.post import Post
from app.models.clip import Clip
from app.models.engagement import Like
from app.models.comment import Comment

router = APIRouter(prefix="/analytics", tags=["analytics"])

class DashboardStats(BaseModel):
    total_users: int
    total_posts: int
    total_clips: int
    total_likes: int
    total_comments: int

class GrowthItem(BaseModel):
    date: str
    users: int
    posts: int
    clips: int

class EngagementItem(BaseModel):
    id: str
    type: str # "post" or "clip"
    content: str
    likes_count: int
    user_handle: str

class UserAnalytics(BaseModel):
    id: str
    username: str
    email: str
    display_name: str | None
    created_at: str
    is_verified: bool
    is_superadmin: bool
    is_restricted: bool
    posts_count: int
    clips_count: int
    followers_count: int
    following_count: int

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_superadmin),
) -> Any:
    """Get aggregated totals for the dashboard."""
    users_count = await db.scalar(select(func.count(User.id)))
    posts_count = await db.scalar(select(func.count(Post.id)))
    clips_count = await db.scalar(select(func.count(Clip.id)))
    likes_count = await db.scalar(select(func.count(Like.id)))
    comments_count = await db.scalar(select(func.count(Comment.id)))

    return DashboardStats(
        total_users=users_count or 0,
        total_posts=posts_count or 0,
        total_clips=clips_count or 0,
        total_likes=likes_count or 0,
        total_comments=comments_count or 0,
    )

@router.get("/growth", response_model=list[GrowthItem])
async def get_growth_data(
    days: int = 30,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_superadmin),
) -> Any:
    """Get daily growth metrics for the last X days."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Query for daily counts
    def daily_query(model):
        return (
            select(func.date(model.created_at).label("day"), func.count(model.id).label("count"))
            .where(model.created_at >= start_date)
            .group_by(func.date(model.created_at))
            .order_by(func.date(model.created_at))
        )

    users_growth = await db.execute(daily_query(User))
    posts_growth = await db.execute(daily_query(Post))
    clips_growth = await db.execute(daily_query(Clip))

    # Merge results into a daily series
    growth_map = {}
    for i in range(days + 1):
        d = (start_date + timedelta(days=i)).date().isoformat()
        growth_map[d] = {"users": 0, "posts": 0, "clips": 0}

    for row in users_growth:
        day_str = str(row.day)
        if day_str in growth_map: growth_map[day_str]["users"] = row.count
    for row in posts_growth:
        day_str = str(row.day)
        if day_str in growth_map: growth_map[day_str]["posts"] = row.count
    for row in clips_growth:
        day_str = str(row.day)
        if day_str in growth_map: growth_map[day_str]["clips"] = row.count

    return [
        GrowthItem(date=d, **counts)
        for d, counts in sorted(growth_map.items())
    ]

@router.get("/users", response_model=list[UserAnalytics])
async def get_users_list(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_superadmin),
) -> Any:
    """List all users with detailed engagement metrics."""
    # Subqueries for counts
    posts_sub = select(Post.user_id, func.count(Post.id).label("cnt")).group_by(Post.user_id).subquery()
    clips_sub = select(Clip.user_id, func.count(Clip.id).label("cnt")).group_by(Clip.user_id).subquery()

    stmt = (
        select(
            User,
            func.coalesce(posts_sub.c.cnt, 0).label("posts_count"),
            func.coalesce(clips_sub.c.cnt, 0).label("clips_count")
        )
        .outerjoin(posts_sub, User.id == posts_sub.c.user_id)
        .outerjoin(clips_sub, User.id == clips_sub.c.user_id)
        .order_by(desc(User.created_at))
    )
    
    result = await db.execute(stmt)
    user_data = []
    for user, p_count, c_count in result:
        user_data.append(UserAnalytics(
            id=str(user.id),
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            created_at=user.created_at.isoformat(),
            is_verified=user.is_verified,
            is_superadmin=getattr(user, "is_superadmin", False),
            is_restricted=getattr(user, "is_restricted", False),
            posts_count=p_count,
            clips_count=c_count,
            followers_count=user.followers_count or 0,
            following_count=user.following_count or 0,
        ))
    return user_data

@router.patch("/users/{user_id}/toggle-restriction", response_model=UserAnalytics)
async def toggle_user_restriction(
    user_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_superadmin),
) -> Any:
    """Toggle a user's restricted status."""
    from uuid import UUID
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    
    # Can't restrict a superadmin
    if user.is_superadmin:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Cannot restrict a superadmin")
        
    user.is_restricted = not user.is_restricted
    await db.commit()
    await db.refresh(user)
    
    # Get counts for response
    posts_count = await db.scalar(select(func.count(Post.id)).where(Post.user_id == user.id))
    clips_count = await db.scalar(select(func.count(Clip.id)).where(Clip.user_id == user.id))
    
    return UserAnalytics(
        id=str(user.id),
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at.isoformat(),
        is_verified=user.is_verified,
        is_superadmin=user.is_superadmin,
        is_restricted=user.is_restricted,
        posts_count=posts_count or 0,
        clips_count=clips_count or 0,
        followers_count=user.followers_count or 0,
        following_count=user.following_count or 0,
    )
