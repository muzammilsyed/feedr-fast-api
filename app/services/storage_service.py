"""Storage service for media files.

Uses local disk for now. Designed to swap for S3/MinIO later via StorageBackend interface.
All media is organized by user_id: users/{user_id}/{type}/{filename}
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import settings


class StorageBackend(Protocol):
    """Protocol for storage backends. Implement LocalStorage now, S3Storage later."""

    def save(self, user_id: str, media_type: str, data: bytes, ext: str) -> str:
        """Save file and return public URL."""
        ...

    def delete(self, url: str) -> bool:
        """Delete file by URL. Returns True if deleted."""
        ...


class LocalStorage:
    """Store files on local disk. Path: uploads/users/{user_id}/{type}/{uuid}.{ext}"""

    def __init__(self, base_dir: str | None = None, base_url: str | None = None):
        self.base_dir = Path(base_dir or settings.UPLOAD_DIR).resolve()
        self.base_url = (base_url or settings.MEDIA_BASE_URL).rstrip("/")

    def _user_path(self, user_id: str, media_type: str) -> Path:
        path = self.base_dir / "users" / str(user_id) / media_type
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self, user_id: str, media_type: str, data: bytes, ext: str) -> str:
        """Save file and return public URL."""
        path = self._user_path(user_id, media_type)
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = path / filename
        filepath.write_bytes(data)
        rel = f"users/{user_id}/{media_type}/{filename}"
        return f"{self.base_url}/uploads/{rel}"

    def save_from_path(self, user_id: str, media_type: str, src_path: str | Path, ext: str) -> str:
        """Copy file from path and return public URL."""
        path = self._user_path(user_id, media_type)
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = path / filename
        shutil.copy2(src_path, filepath)
        rel = f"users/{user_id}/{media_type}/{filename}"
        return f"{self.base_url}/uploads/{rel}"

    def delete(self, url: str) -> bool:
        """Delete file by URL. Returns True if deleted."""
        if "/uploads/" not in url:
            return False
        try:
            rel = url.split("/uploads/", 1)[1]
            filepath = self.base_dir / rel
            if filepath.exists():
                filepath.unlink()
                return True
        except Exception:
            pass
        return False


# Singleton - swap implementation here when moving to S3
_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage
