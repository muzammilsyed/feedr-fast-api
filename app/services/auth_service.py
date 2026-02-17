"""Authentication business logic."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        username=data.username,
        email=data.email,
        password_hash=get_password_hash(data.password),
        display_name=data.display_name or data.username,
        bio=data.bio,
        avatar_url=data.avatar_url,
        is_verified=data.is_verified,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def authenticate_user_by_username(db: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def user_to_response(user: User, include_email: bool = False) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email if include_email else None,
        display_name=user.display_name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        is_verified=user.is_verified,
        followers_count=user.followers_count,
        following_count=user.following_count,
        is_private=getattr(user, "is_private", False),
        created_at=user.created_at,
    )


def create_tokens_for_user(user: User) -> tuple[str, str]:
    return create_access_token(user.id), create_refresh_token(user.id)


async def get_user_by_id_for_refresh(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
