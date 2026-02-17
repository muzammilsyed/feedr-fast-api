"""Pydantic schemas for Comment."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.user import UserPublic


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1)
    parent_id: UUID | None = None


class CommentResponse(BaseModel):
    id: UUID
    user_id: UUID
    content: str
    created_at: datetime
    parent_id: UUID | None = None
    user: UserPublic | None = None
    likes_count: int = 0
    is_liked: bool = False

    model_config = {"from_attributes": True}
