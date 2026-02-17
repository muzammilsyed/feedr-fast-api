"""Pydantic schemas for Notification."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.user import UserPublic


class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    actor_id: UUID
    type: str
    text: str
    target_post_id: UUID | None = None
    target_clip_id: UUID | None = None
    target_comment_id: UUID | None = None
    is_read: bool = False
    created_at: datetime
    actor: UserPublic | None = None

    model_config = {"from_attributes": True}
