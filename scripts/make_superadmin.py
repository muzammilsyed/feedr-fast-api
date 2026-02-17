import asyncio
import sys
import os
from uuid import UUID

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from app.db.session import engine, async_session_maker
from app.models.user import User

async def promote_user(identifier: str):
    """
    Promote a user to superadmin status.
    identifier can be email or username.
    """
    async with async_session_maker() as session:
        # Find user
        if "@" in identifier:
            stmt = select(User).where(User.email == identifier)
        else:
            stmt = select(User).where(User.username == identifier)
        
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"Error: User '{identifier}' not found.")
            return

        # Update user
        user.is_superadmin = True
        await session.commit()
        print(f"Success: User '{user.username}' ({user.email}) is now a superadmin.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/make_superadmin.py <email_or_username>")
        sys.exit(1)
    
    target = sys.argv[1]
    asyncio.run(promote_user(target))
