from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.data_summary import DatasetProfile
from models.dataset_version import DatasetSnapshot


ProfileStatus = Literal["pending", "running", "completed", "failed"]


async def create_dataset_profile(
    session: AsyncSession,
    *,
    dataset_id: UUID,
) -> DatasetProfile:
    lock_result = await session.execute(
        select(DatasetSnapshot.id)
        .where(DatasetSnapshot.id == dataset_id)
        .with_for_update()
    )
    lock_result.scalar_one()

    previous = await get_latest_dataset_profile(
        session,
        dataset_id=dataset_id,
    )
    profile = DatasetProfile(
        dataset_id=dataset_id,
        profile_version=previous.profile_version + 1 if previous else 1,
        status="pending",
        summary={},
        field_statistics={},
        duplicate_summary={},
    )
    session.add(profile)
    await session.flush()
    await session.refresh(profile)
    return profile


async def get_latest_dataset_profile(
    session: AsyncSession,
    *,
    dataset_id: UUID,
) -> DatasetProfile | None:
    result = await session.execute(
        select(DatasetProfile)
        .where(DatasetProfile.dataset_id == dataset_id)
        .order_by(DatasetProfile.profile_version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def update_dataset_profile(
    session: AsyncSession,
    *,
    profile: DatasetProfile,
    status: ProfileStatus,
    summary: dict | None = None,
    field_statistics: dict | None = None,
    duplicate_summary: dict | None = None,
    profile_hash: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> DatasetProfile:
    profile.status = status
    if summary is not None:
        profile.summary = summary
    if field_statistics is not None:
        profile.field_statistics = field_statistics
    if duplicate_summary is not None:
        profile.duplicate_summary = duplicate_summary
    if profile_hash is not None:
        profile.profile_hash = profile_hash
    if started_at is not None:
        profile.started_at = started_at
    if completed_at is not None:
        profile.completed_at = completed_at

    await session.flush()
    await session.refresh(profile)
    return profile
