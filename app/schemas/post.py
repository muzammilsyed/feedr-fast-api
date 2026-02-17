"""Pydantic schemas for Post."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.user import UserPublic

PostVisibility = str  # "public" | "private" | "followers_only"


class PostBase(BaseModel):
    content: str = Field(..., min_length=1)
    media_urls: list[str] | None = None
    visibility: str = Field(default="public", pattern="^(public|private|followers_only)$")


class PostCreate(PostBase):
    pass


class PostUpdate(BaseModel):
    content: str | None = Field(None, min_length=1)
    media_urls: list[str] | None = None


class PostResponse(PostBase):
    id: UUID
    user_id: UUID
    likes_count: int = 0
    comments_count: int = 0
    reposts_count: int = 0
    views_count: int = 0
    created_at: datetime
    user: UserPublic | None = None
    visibility: str = "public"
    is_liked: bool = False

    model_config = {"from_attributes": True}
