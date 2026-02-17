import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.user import User

async def list_users():
    async with async_session_maker() as session:
        result = await session.execute(select(User.email, User.username, User.is_superadmin))
        users = result.all()
        if not users:
            print("No users found in database.")
        else:
            print("Current Users:")
            for email, username, is_admin in users:
                print(f"- {username} ({email}) | Admin: {is_admin}")

if __name__ == "__main__":
    asyncio.run(list_users())
