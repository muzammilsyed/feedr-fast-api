import asyncio
from app.db.session import async_session_maker
from app.models.engagement import Like
from app.models.post import Post
from app.models.user import User
from sqlalchemy import select, func

async def check_likes():
    async with async_session_maker() as db:
        # Count total likes
        total_likes = await db.scalar(select(func.count(Like.id)))
        print(f"Total likes in database: {total_likes}")
        
        # Get recent likes with details
        result = await db.execute(
            select(Like, User.username, Post.content)
            .join(User, Like.user_id == User.id)
            .outerjoin(Post, Like.post_id == Post.id)
            .limit(10)
        )
        likes = result.all()
        
        if likes:
            print("\nRecent likes:")
            for like, username, post_content in likes:
                content_preview = (post_content[:30] + "...") if post_content and len(post_content) > 30 else (post_content or "N/A")
                print(f"  - {username} liked: {content_preview}")
        else:
            print("\nNo likes found in database!")

if __name__ == "__main__":
    asyncio.run(check_likes())
