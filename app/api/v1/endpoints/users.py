"""User profile endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_user_optional, get_current_user
from app.models.user import User
from app.models.post import Post
from app.models.clip import Clip
from app.models.engagement import Follow, FollowRequest
from app.schemas.user import UserResponse, UserUpdate, UserPublic
from app.schemas.post import PostResponse
from app.schemas.clip import ClipResponse
from app.services.auth_service import user_to_response
from app.services.feed_service import post_to_response
from app.services.clip_service import clip_to_response
from app.services.feed_service import get_following_author_ids
from app.services.notification_service import create_notification
from app.schemas.password import ChangePasswordRequest
from app.core.security import verify_password, get_password_hash

router = APIRouter(prefix="/users", tags=["users"])


async def _is_following(db: AsyncSession, follower_id: UUID, following_id: UUID) -> bool:
    result = await db.execute(
        select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.following_id == following_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def _has_pending_request(db: AsyncSession, requester_id: UUID, target_id: UUID) -> bool:
    result = await db.execute(
        select(FollowRequest).where(
            FollowRequest.requester_id == requester_id,
            FollowRequest.target_id == target_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def _can_view_private_profile(db: AsyncSession, profile_owner_id: UUID, viewer_id: UUID | None) -> bool:
    """True if viewer can see full profile (owner, or follows owner)."""
    if viewer_id is None:
        return False
    if profile_owner_id == viewer_id:
        return True
    return await _is_following(db, viewer_id, profile_owner_id)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return user_to_response(current_user, include_email=True)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.display_name is not None:
        current_user.display_name = data.display_name
    if data.bio is not None:
        current_user.bio = data.bio
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url
    if data.who_can_comment is not None:
        current_user.who_can_comment = data.who_can_comment
    if data.is_private is not None:
        current_user.is_private = data.is_private
    await db.commit()
    await db.refresh(current_user)
    return user_to_response(current_user, include_email=True)


@router.post("/me/change-password", response_model=dict)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password."""
    # Verify current password
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    # Update to new password
    current_user.password_hash = get_password_hash(data.new_password)
    await db.commit()
    return {"success": True, "message": "Password changed successfully"}


@router.get("/me/follows/{user_id}", response_model=dict)
async def check_follows_me(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if the given user follows the current user. Used for 'who can comment' privacy."""
    result = await db.execute(
        select(Follow).where(
            Follow.follower_id == user_id,
            Follow.following_id == current_user.id,
        )
    )
    follows = result.scalar_one_or_none() is not None
    return {"follows": follows}


@router.delete("/me/followers/{user_id}", response_model=dict)
async def remove_follower(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a user from your followers. They will no longer follow you."""
    result = await db.execute(
        delete(Follow).where(
            Follow.follower_id == user_id,
            Follow.following_id == current_user.id,
        )
    )
    if result.rowcount > 0:
        target_result = await db.execute(select(User).where(User.id == user_id))
        target = target_result.scalar_one_or_none()
        if target and target.following_count > 0:
            target.following_count -= 1
        if current_user.followers_count > 0:
            current_user.followers_count -= 1
        await db.commit()
    return {"removed": True}


@router.get("/me/follow-requests", response_model=list[UserPublic])
async def get_follow_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pending follow requests for the current user (people who requested to follow you)."""
    result = await db.execute(
        select(User)
        .join(FollowRequest, FollowRequest.requester_id == User.id)
        .where(FollowRequest.target_id == current_user.id)
        .order_by(desc(FollowRequest.created_at))
        .offset(skip)
        .limit(limit)
    )
    requesters = result.scalars().all()
    out = []
    for u in requesters:
        is_f = await _is_following(db, current_user.id, u.id)
        out.append(_user_to_public(u, is_following=is_f))
    return out


@router.post("/me/follow-requests/{requester_id}/accept", response_model=dict)
async def accept_follow_request(
    requester_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept a follow request. Creates the follow and notifies the requester."""
    if requester_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot accept your own request")
    req_result = await db.execute(
        select(FollowRequest).where(
            FollowRequest.requester_id == requester_id,
            FollowRequest.target_id == current_user.id,
        )
    )
    fr = req_result.scalar_one_or_none()
    if not fr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow request not found")
    requester_result = await db.execute(select(User).where(User.id == requester_id))
    requester = requester_result.scalar_one_or_none()
    if not requester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requester not found")
    await db.delete(fr)
    db.add(Follow(follower_id=requester_id, following_id=current_user.id))
    current_user.followers_count = (current_user.followers_count or 0) + 1
    requester.following_count = (requester.following_count or 0) + 1
    await create_notification(
        db,
        user_id=requester_id,
        actor_id=current_user.id,
        notification_type="follow_request_accepted",
        text=f"{current_user.display_name or current_user.username} accepted your follow request",
    )
    await db.commit()
    return {"accepted": True}


@router.post("/me/follow-requests/{requester_id}/reject", response_model=dict)
async def reject_follow_request(
    requester_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a follow request."""
    if requester_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot reject your own request")
    result = await db.execute(
        delete(FollowRequest).where(
            FollowRequest.requester_id == requester_id,
            FollowRequest.target_id == current_user.id,
        )
    )
    if result.rowcount > 0:
        await db.commit()
    return {"rejected": True}


@router.get("/me/following/{user_id}", response_model=dict)
async def check_following(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if the current user follows the given user, or has a pending follow request."""
    follows = await _is_following(db, current_user.id, user_id)
    requested = await _has_pending_request(db, current_user.id, user_id) if not follows else False
    return {"follows": follows, "requested": requested}


@router.post("/{user_id}/follow", response_model=dict)
async def follow_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Follow a user (public profile) or send follow request (private profile). Idempotent."""
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    already = await _is_following(db, current_user.id, user_id)
    if already:
        return {"follows": True, "requested": False}
    is_private = getattr(target, "is_private", False)
    if is_private:
        existing_req = await _has_pending_request(db, current_user.id, user_id)
        if not existing_req:
            db.add(FollowRequest(requester_id=current_user.id, target_id=user_id))
            await create_notification(
                db,
                user_id=user_id,
                actor_id=current_user.id,
                notification_type="follow_request",
                text=f"{current_user.display_name or current_user.username} requested to follow you",
            )
            await db.commit()
        return {"follows": False, "requested": True}
    db.add(Follow(follower_id=current_user.id, following_id=user_id))
    target.followers_count = (target.followers_count or 0) + 1
    current_user.following_count = (current_user.following_count or 0) + 1
    await create_notification(
        db,
        user_id=user_id,
        actor_id=current_user.id,
        notification_type="follow",
        text=f"{current_user.display_name or current_user.username} started following you",
    )
    await db.commit()
    return {"follows": True, "requested": False}


@router.delete("/{user_id}/follow-request", response_model=dict)
async def cancel_follow_request(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel your pending follow request to a private user."""
    result = await db.execute(
        delete(FollowRequest).where(
            FollowRequest.requester_id == current_user.id,
            FollowRequest.target_id == user_id,
        )
    )
    if result.rowcount > 0:
        await db.commit()
    return {"requested": False}


@router.delete("/{user_id}/follow", response_model=dict)
async def unfollow_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unfollow a user."""
    result = await db.execute(
        delete(Follow).where(
            Follow.follower_id == current_user.id,
            Follow.following_id == user_id,
        )
    )
    if result.rowcount > 0:
        target_result = await db.execute(select(User).where(User.id == user_id))
        target = target_result.scalar_one_or_none()
        if target and target.followers_count > 0:
            target.followers_count -= 1
        if current_user.following_count > 0:
            current_user.following_count -= 1
        await db.commit()
    return {"follows": False}


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import User as UserModel
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    viewer_id = current_user.id if current_user else None
    is_following = await _is_following(db, viewer_id, user.id) if viewer_id else False
    is_requested = await _has_pending_request(db, viewer_id, user.id) if viewer_id and not is_following else False
    can_view = not getattr(user, "is_private", False) or await _can_view_private_profile(db, user.id, viewer_id)
    return UserPublic(
        id=user.id,
        username=user.username,
        display_name=user.display_name if can_view else user.username,
        bio=user.bio if can_view else None,
        avatar_url=user.avatar_url if can_view else None,
        is_verified=user.is_verified if can_view else False,
        followers_count=user.followers_count if can_view else 0,
        following_count=user.following_count if can_view else 0,
        who_can_comment=getattr(user, "who_can_comment", "everyone") or "everyone",
        is_private=getattr(user, "is_private", False),
        is_following=is_following,
        is_requested=is_requested,
        created_at=user.created_at,
    )


@router.get("/{user_id}/posts", response_model=list[PostResponse])
async def get_user_posts(
    user_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    from app.services.feed_service import get_user_posts_visible, get_user_liked_post_ids, get_following_author_ids, post_to_response
    viewer_id = current_user.id if current_user else None
    user_result = await db.execute(select(User).where(User.id == user_id))
    target_user = user_result.scalar_one_or_none()
    if target_user and getattr(target_user, "is_private", False):
        if not await _can_view_private_profile(db, user_id, viewer_id):
            return []
    posts = await get_user_posts_visible(db, user_id, viewer_id, skip=skip, limit=limit)
    liked_ids = await get_user_liked_post_ids(db, viewer_id, [p.id for p in posts]) if viewer_id else set()
    following_ids = await get_following_author_ids(db, viewer_id, [user_id]) if viewer_id else set()
    is_following_owner = user_id in following_ids
    return [post_to_response(p, is_liked=p.id in liked_ids, is_following_author=is_following_owner) for p in posts]


@router.get("/{user_id}/clips", response_model=list[ClipResponse])
async def get_user_clips(
    user_id: UUID,
    current_user: User | None = Depends(get_current_user_optional),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    viewer_id = current_user.id if current_user else None
    user_result = await db.execute(select(User).where(User.id == user_id))
    target_user = user_result.scalar_one_or_none()
    if target_user and getattr(target_user, "is_private", False):
        if not await _can_view_private_profile(db, user_id, viewer_id):
            return []
    result = await db.execute(
        select(Clip)
        .where(Clip.user_id == user_id)
        .order_by(desc(Clip.created_at))
        .offset(skip)
        .limit(limit)
        .options(selectinload(Clip.user))
    )
    clips = result.scalars().all()
    following_ids = await get_following_author_ids(db, viewer_id, [user_id]) if viewer_id else set()
    is_following_owner = user_id in following_ids
    return [clip_to_response(c, is_following_author=is_following_owner) for c in clips]


def _user_to_public(user: User, is_following: bool = False, is_requested: bool = False) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        is_verified=user.is_verified,
        followers_count=user.followers_count or 0,
        following_count=user.following_count or 0,
        who_can_comment=getattr(user, "who_can_comment", "everyone") or "everyone",
        is_private=getattr(user, "is_private", False),
        is_following=is_following,
        is_requested=is_requested,
        created_at=user.created_at,
    )


@router.get("/{user_id}/followers", response_model=list[UserPublic])
async def get_user_followers(
    user_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get users who follow this user."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    target = user_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    viewer_id = current_user.id if current_user else None
    if getattr(target, "is_private", False) and not await _can_view_private_profile(db, user_id, viewer_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view followers of private profile")
    result = await db.execute(
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.following_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    followers = result.scalars().all()
    out = []
    for u in followers:
        is_f = await _is_following(db, viewer_id, u.id) if viewer_id else False
        is_req = await _has_pending_request(db, viewer_id, u.id) if viewer_id and not is_f else False
        out.append(_user_to_public(u, is_following=is_f, is_requested=is_req))
    return out


@router.get("/{user_id}/following", response_model=list[UserPublic])
async def get_user_following(
    user_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """Get users that this user follows."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    target = user_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    viewer_id = current_user.id if current_user else None
    if getattr(target, "is_private", False) and not await _can_view_private_profile(db, user_id, viewer_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view following of private profile")
    result = await db.execute(
        select(User)
        .join(Follow, Follow.following_id == User.id)
        .where(Follow.follower_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    following = result.scalars().all()
    out = []
    for u in following:
        is_f = await _is_following(db, viewer_id, u.id) if viewer_id else False
        is_req = await _has_pending_request(db, viewer_id, u.id) if viewer_id and not is_f else False
        out.append(_user_to_public(u, is_following=is_f, is_requested=is_req))
    return out
