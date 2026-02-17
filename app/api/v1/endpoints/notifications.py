"""Notifications API."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.notification import NotificationResponse
from app.schemas.user import UserPublic
from app.services.notification_service import (
    get_notifications,
    get_unread_count,
    mark_all_read,
    mark_one_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _user_to_public(u: User) -> UserPublic:
    return UserPublic(
        id=u.id,
        username=u.username,
        display_name=u.display_name,
        bio=u.bio,
        avatar_url=u.avatar_url,
        is_verified=u.is_verified,
        followers_count=u.followers_count,
        following_count=u.following_count,
        created_at=u.created_at,
    )


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await get_notifications(db, current_user.id, skip=skip, limit=limit)
    return [
        NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            actor_id=n.actor_id,
            type=n.type,
            text=n.text,
            target_post_id=n.target_post_id,
            target_clip_id=n.target_clip_id,
            target_comment_id=n.target_comment_id,
            is_read=n.is_read,
            created_at=n.created_at,
            actor=_user_to_public(actor) if actor else None,
        )
        for n, actor in rows
    ]


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await get_unread_count(db, current_user.id)
    return {"count": count}


@router.post("/mark-all-read")
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await mark_all_read(db, current_user.id)
    return {"updated": updated}


@router.patch("/{notification_id}/read")
async def mark_one_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await mark_one_read(db, current_user.id, notification_id)
    return {"updated": updated}
