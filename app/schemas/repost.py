"""Pydantic schemas for Repost."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.post import PostResponse
from app.schemas.user import UserPublic


class RepostCreate(BaseModel):
    quote_text: str = Field(default="", max_length=500)


class RepostResponse(BaseModel):
    id: UUID
    quote_text: str = ""
    original_type: str = "post"
    created_at: datetime
    reposter_user: UserPublic | None = None
    original_post: PostResponse | None = None
