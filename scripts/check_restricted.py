import asyncio
from app.db.session import async_session_maker
from app.models.user import User
from sqlalchemy import select

async def check_restricted():
    async with async_session_maker() as db:
        result = await db.execute(select(User.username, User.is_restricted, User.is_superadmin))
        users = result.all()
        for username, is_restricted, is_superadmin in users:
            print(f"{username}: restricted={is_restricted}, superadmin={is_superadmin}")

if __name__ == "__main__":
    asyncio.run(check_restricted())
