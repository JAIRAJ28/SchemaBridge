import asyncio
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings


settings = get_settings()


engine: AsyncEngine = create_async_engine(
    settings.database_url.get_secret_value(),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout_seconds,
    pool_recycle=settings.database_pool_recycle_seconds,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": settings.database_connect_timeout_seconds,
    },
)


session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_database_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_database_connection() -> None:
    async with asyncio.timeout(
        settings.database_connect_timeout_seconds
    ):
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))


async def close_database_connection() -> None:
    await engine.dispose()
