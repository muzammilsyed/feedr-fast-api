"""Notification creation and queries."""
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User


async def create_notification(
    db: AsyncSession,
    *,
    user_id: UUID,
    actor_id: UUID,
    notification_type: str,
    text: str,
    target_post_id: UUID | None = None,
    target_clip_id: UUID | None = None,
    target_comment_id: UUID | None = None,
) -> Notification | None:
    """Create a notification. Skips if actor is the same as user (no self-notify)."""
    if user_id == actor_id:
        return None
    notification = Notification(
        user_id=user_id,
        actor_id=actor_id,
        type=notification_type,
        text=text,
        target_post_id=target_post_id,
        target_clip_id=target_clip_id,
        target_comment_id=target_comment_id,
    )
    db.add(notification)
    from app.workers.notifications import send_push_notification

    send_push_notification.delay(str(user_id), "feedr", text)
    return notification


async def get_notifications(
    db: AsyncSession,
    user_id: UUID,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[tuple[Notification, User]]:
    """Get notifications for user, most recent first."""
    result = await db.execute(
        select(Notification, User)
        .join(User, Notification.actor_id == User.id)
        .where(Notification.user_id == user_id)
        .order_by(desc(Notification.created_at))
        .offset(skip)
        .limit(limit)
    )
    return result.all()


async def get_unread_count(db: AsyncSession, user_id: UUID) -> int:
    """Get count of unread notifications."""
    from sqlalchemy import func

    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
    )
    return result.scalar() or 0


async def mark_all_read(db: AsyncSession, user_id: UUID) -> int:
    """Mark all notifications as read. Returns count updated."""
    from sqlalchemy import update

    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read == False)
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    return result.rowcount or 0


async def mark_one_read(db: AsyncSession, user_id: UUID, notification_id: UUID) -> bool:
    """Mark a single notification as read. Returns True if updated."""
    from sqlalchemy import update

    stmt = (
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    return (result.rowcount or 0) > 0
