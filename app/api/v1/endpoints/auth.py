"""Auth endpoints: register, login, refresh."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

def _log(msg: str, *args):
    print(f"[Auth] {msg}", *args)

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, Token, LoginRequest, LoginByUsernameRequest, TokenRefresh
from app.services.auth_service import (
    create_user,
    get_user_by_email,
    get_user_by_username,
    authenticate_user,
    authenticate_user_by_username,
    user_to_response,
    create_tokens_for_user,
    get_user_by_id_for_refresh,
)
from app.core.security import decode_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    _log("Register attempt:", data.username, data.email)
    if await get_user_by_email(db, data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    if await get_user_by_username(db, data.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")
    user = await create_user(db, data)
    await db.commit()
    _log("Register success:", user.id, user.username)
    access_token, refresh_token = create_tokens_for_user(user)
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_to_response(user, include_email=True),
    )


@router.post("/login", response_model=Token)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    _log("Login attempt (email):", data.email)
    user = await authenticate_user(db, data.email, data.password)
    if not user:
        _log("Login failed: invalid email or password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    _log("Login success:", user.id, user.username)
    access_token, refresh_token = create_tokens_for_user(user)
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_to_response(user, include_email=True),
    )


@router.post("/login/username", response_model=Token)
async def login_by_username(
    data: LoginByUsernameRequest,
    db: AsyncSession = Depends(get_db),
):
    _log("Login attempt (username):", data.username)
    user = await authenticate_user_by_username(db, data.username, data.password)
    if not user:
        _log("Login failed: invalid username or password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    _log("Login success (username):", user.id, user.username)
    access_token, refresh_token = create_tokens_for_user(user)
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_to_response(user, include_email=True),
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    body: TokenRefresh,
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = await get_user_by_id_for_refresh(db, UUID(sub))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    new_access, new_refresh = create_tokens_for_user(user)
    return Token(
        access_token=new_access,
        refresh_token=new_refresh,
        user=user_to_response(user, include_email=True),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return user_to_response(current_user, include_email=True)
