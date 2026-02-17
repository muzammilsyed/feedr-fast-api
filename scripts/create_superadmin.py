import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.user import User
from app.core.security import get_password_hash

async def create_superadmin(email, username, password):
    async with async_session_maker() as session:
        # Check if exists
        res = await session.execute(select(User).where((User.email == email) | (User.username == username)))
        if res.scalar_one_or_none():
            print(f"Error: User with email '{email}' or username '{username}' already exists.")
            return

        user = User(
            email=email,
            username=username,
            password_hash=get_password_hash(password),
            display_name="Super Admin",
            is_verified=True,
            is_superadmin=True
        )
        session.add(user)
        await session.commit()
        print(f"Success: Superadmin created!")
        print(f"Email: {email}")
        print(f"Username: {username}")
        print(f"Password: {password}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python scripts/create_superadmin.py <email> <username> <password>")
        sys.exit(1)
    
    email = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    asyncio.run(create_superadmin(email, username, password))
