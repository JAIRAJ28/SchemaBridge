from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.scalar(select(User).where(User.id == user_id))


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    display_name: str,
    password_hash: str,
) -> User:
    user = User(
        email=email,
        display_name=display_name,
        password_hash=password_hash,
    )
    session.add(user)
    await session.flush()
    return user
from uuid import UUID
