"""V1 API router aggregation."""
from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, posts, clips, feed, uploads, notifications, search, analytics

api_router = APIRouter(prefix="/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(posts.router)
api_router.include_router(clips.router)
api_router.include_router(feed.router)
api_router.include_router(uploads.router)
api_router.include_router(notifications.router)
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(analytics.router)
