from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import SchemaRole
from models.project import MigrationProject
from models.schema_version import SchemaSnapshot


async def create_schema_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
    schema_role: SchemaRole,
    original_schema: dict,
    normalized_schema: dict,
    schema_hash: str,
    created_by: str,
) -> SchemaSnapshot:
    # Lock the project row so two concurrent requests cannot create
    # the same schema version number.
    lock_statement = (
        select(MigrationProject.id)
        .where(MigrationProject.id == project_id)
        .with_for_update()
    )
    lock_result = await session.execute(lock_statement)
    lock_result.scalar_one()

    previous_schema = await get_latest_schema_snapshot(
        session,
        project_id=project_id,
        schema_role=schema_role,
    )

    version = (
        previous_schema.version + 1
        if previous_schema is not None
        else 1
    )

    snapshot = SchemaSnapshot(
        project_id=project_id,
        previous_schema_id=(
            previous_schema.id
            if previous_schema is not None
            else None
        ),
        schema_role=schema_role.value,
        version=version,
        original_schema=original_schema,
        normalized_schema=normalized_schema,
        schema_hash=schema_hash,
        created_by=created_by,
    )

    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)

    return snapshot


async def get_schema_snapshot_by_id(
    session: AsyncSession,
    *,
    project_id: UUID,
    schema_snapshot_id: UUID,
) -> SchemaSnapshot | None:
    statement = select(SchemaSnapshot).where(
        SchemaSnapshot.id == schema_snapshot_id,
        SchemaSnapshot.project_id == project_id,
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_latest_schema_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
    schema_role: SchemaRole,
) -> SchemaSnapshot | None:
    statement = (
        select(SchemaSnapshot)
        .where(
            SchemaSnapshot.project_id == project_id,
            SchemaSnapshot.schema_role == schema_role.value,
        )
        .order_by(SchemaSnapshot.version.desc())
        .limit(1)
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_schema_snapshot_by_hash(
    session: AsyncSession,
    *,
    project_id: UUID,
    schema_role: SchemaRole,
    schema_hash: str,
) -> SchemaSnapshot | None:
    statement = select(SchemaSnapshot).where(
        SchemaSnapshot.project_id == project_id,
        SchemaSnapshot.schema_role == schema_role.value,
        SchemaSnapshot.schema_hash == schema_hash,
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_schema_snapshots(
    session: AsyncSession,
    *,
    project_id: UUID,
    schema_role: SchemaRole,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[SchemaSnapshot]:
    statement = (
        select(SchemaSnapshot)
        .where(
            SchemaSnapshot.project_id == project_id,
            SchemaSnapshot.schema_role == schema_role.value,
        )
        .order_by(SchemaSnapshot.version.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(statement)
    return result.scalars().all()