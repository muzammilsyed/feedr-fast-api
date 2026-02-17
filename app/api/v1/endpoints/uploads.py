"""Upload endpoints for media files. All media is stored per-user."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import get_current_user
from app.models.user import User
from app.services.storage_service import get_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Allowed MIME types
AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
POST_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
VIDEO_TYPES = {"video/mp4", "video/quicktime"}

EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mp4",
}


def _get_ext(content_type: str | None) -> str:
    return EXT_MAP.get(content_type or "", ".jpg")


def _validate_file(file: UploadFile, allowed: set[str]) -> str:
    content_type = file.content_type or ""
    if content_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {content_type}. Allowed: {allowed}",
        )
    return _get_ext(content_type)


async def _read_and_validate_size(file: UploadFile, max_size_mb: int) -> bytes:
    data = await file.read()
    if len(data) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max {max_size_mb}MB",
        )
    return data


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload avatar image. Returns URL to store in user.avatar_url."""
    ext = _validate_file(file, AVATAR_TYPES)
    data = await _read_and_validate_size(file, max_size_mb=5)
    url = get_storage().save(str(current_user.id), "avatars", data, ext)
    return {"url": url}


@router.post("/post-media")
async def upload_post_media(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload one or more images for a post. Returns list of URLs for media_urls."""
    if len(files) > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 4 images per post",
        )
    urls: list[str] = []
    for f in files:
        ext = _validate_file(f, POST_IMAGE_TYPES)
        data = await _read_and_validate_size(f, max_size_mb=5)
        url = get_storage().save(str(current_user.id), "posts", data, ext)
        urls.append(url)
    return {"urls": urls}


@router.post("/clip")
async def upload_clip(
    video: UploadFile = File(...),
    thumbnail: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
):
    """Upload clip video and optional thumbnail. Returns video_url and thumbnail_url."""
    ext = _validate_file(video, VIDEO_TYPES)
    data = await _read_and_validate_size(video, max_size_mb=100)
    video_url = get_storage().save(str(current_user.id), "clips", data, ext)

    thumbnail_url = None
    if thumbnail and thumbnail.filename:
        thumb_ext = _validate_file(thumbnail, AVATAR_TYPES)
        thumb_data = await _read_and_validate_size(thumbnail, max_size_mb=2)
        thumbnail_url = get_storage().save(str(current_user.id), "clips", thumb_data, thumb_ext)

    return {"video_url": video_url, "thumbnail_url": thumbnail_url}
