from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.plan_version import MigrationPlanVersion
from models.project import MigrationProject


async def create_plan_version(
    session: AsyncSession,
    *,
    project_id: UUID,
    source_schema_version_id: UUID,
    target_schema_version_id: UUID,
    dataset_version_id: UUID,
    name: str,
    description: str | None,
    plan_data: dict,
    plan_hash: str,
    rule_list_version: str,
    created_by: str,
) -> MigrationPlanVersion:
    lock_result = await session.execute(
        select(MigrationProject.id)
        .where(MigrationProject.id == project_id)
        .with_for_update()
    )
    lock_result.scalar_one()

    previous_plan = await get_latest_plan_version(
        session,
        project_id=project_id,
    )

    plan = MigrationPlanVersion(
        project_id=project_id,
        previous_plan_id=(
            previous_plan.id
            if previous_plan is not None
            else None
        ),
        source_schema_version_id=source_schema_version_id,
        target_schema_version_id=target_schema_version_id,
        dataset_version_id=dataset_version_id,
        version=(
            previous_plan.version + 1
            if previous_plan is not None
            else 1
        ),
        name=name,
        description=description,
        status="draft",
        plan_data=plan_data,
        plan_hash=plan_hash,
        rule_list_version=rule_list_version,
        created_by=created_by,
    )

    session.add(plan)
    await session.flush()
    await session.refresh(plan)

    return plan


async def get_plan_version_by_id(
    session: AsyncSession,
    *,
    project_id: UUID,
    plan_id: UUID,
) -> MigrationPlanVersion | None:
    result = await session.execute(
        select(MigrationPlanVersion).where(
            MigrationPlanVersion.id == plan_id,
            MigrationPlanVersion.project_id == project_id,
        )
    )

    return result.scalar_one_or_none()


async def get_latest_plan_version(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> MigrationPlanVersion | None:
    result = await session.execute(
        select(MigrationPlanVersion)
        .where(
            MigrationPlanVersion.project_id == project_id
        )
        .order_by(MigrationPlanVersion.version.desc())
        .limit(1)
    )

    return result.scalar_one_or_none()


async def get_plan_version_by_hash(
    session: AsyncSession,
    *,
    project_id: UUID,
    plan_hash: str,
) -> MigrationPlanVersion | None:
    result = await session.execute(
        select(MigrationPlanVersion).where(
            MigrationPlanVersion.project_id == project_id,
            MigrationPlanVersion.plan_hash == plan_hash,
        )
    )

    return result.scalar_one_or_none()


async def list_plan_versions(
    session: AsyncSession,
    *,
    project_id: UUID,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[MigrationPlanVersion]:
    result = await session.execute(
        select(MigrationPlanVersion)
        .where(
            MigrationPlanVersion.project_id == project_id
        )
        .order_by(MigrationPlanVersion.version.desc())
        .offset(offset)
        .limit(limit)
    )

    return result.scalars().all()


async def update_plan_status(
    session: AsyncSession,
    *,
    plan: MigrationPlanVersion,
    status: str,
) -> MigrationPlanVersion:
    if status not in {"valid", "invalid"}:
        raise ValueError("Plan status must be valid or invalid.")
    plan.status = status
    await session.flush()
    await session.refresh(plan)
    return plan
