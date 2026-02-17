"""Celery tasks for video processing (transcoding, thumbnails)."""
from app.core.celery_app import celery_app


@celery_app.task
def process_video_upload(clip_id: str, video_url: str) -> None:
    """Process uploaded clip (transcode, optimize). Resolve video_url to local path if needed."""
    # TODO: FFmpeg transcoding - resolve video_url to path, transcode, re-upload
    pass


@celery_app.task
def generate_thumbnail(clip_id: str, video_url: str) -> None:
    """Extract thumbnail frame from video. Resolve video_url to local path if needed."""
    # TODO: FFmpeg - extract frame, save thumbnail, update clip.thumbnail_url in DB
    pass
