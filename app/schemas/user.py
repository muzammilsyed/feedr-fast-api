"""Pydantic schemas for User."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    display_name: str | None = Field(None, max_length=100)
    bio: str | None = None
    avatar_url: str | None = None
    is_verified: bool = False


class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    bio: str | None = None
    avatar_url: str | None = None
    who_can_comment: str | None = Field(None, pattern="^(everyone|people_you_follow|no_one)$")
    is_private: bool | None = None


class UserResponse(UserBase):
    id: UUID
    email: str | None = None  # Only in own profile
    followers_count: int = 0
    following_count: int = 0
    is_private: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPublic(UserBase):
    id: UUID
    followers_count: int = 0
    following_count: int = 0
    who_can_comment: str = "everyone"
    is_private: bool = False
    is_following: bool = False  # Set by API when viewer is authenticated
    is_requested: bool = False  # True when viewer has a pending follow request to this user
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenRefresh(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginByUsernameRequest(BaseModel):
    username: str
    password: str
