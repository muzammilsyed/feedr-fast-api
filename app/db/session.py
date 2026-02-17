"""Async database session and engine."""
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Mask password in logs (show only host/db part)
_db_display = settings.DATABASE_URL.split("@")[-1].split("?")[0] if "@" in settings.DATABASE_URL else "configured"
print(f"[DB] Database URL: ...@{_db_display}")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"timeout": 10},
)


class Base(DeclarativeBase):
    pass


async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def uuid_to_str(value: UUID | None) -> str | None:
    return str(value) if value else None
