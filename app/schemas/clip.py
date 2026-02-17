"""Pydantic schemas for Clip."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.user import UserPublic


class ClipBase(BaseModel):
    caption: str | None = None
    duration: int | None = None


class ClipCreate(ClipBase):
    video_url: str
    thumbnail_url: str | None = None
    audio_id: UUID | None = None


class ClipUpdate(BaseModel):
    caption: str | None = None


class ClipResponse(ClipBase):
    id: UUID
    user_id: UUID
    video_url: str
    thumbnail_url: str | None = None
    audio_id: UUID | None = None
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    views_count: int = 0
    created_at: datetime
    user: UserPublic | None = None

    model_config = {"from_attributes": True}
