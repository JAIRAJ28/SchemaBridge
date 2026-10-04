from collections.abc import Sequence
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import DatasetStatus, SchemaRole
from models.dataset_version import DatasetSnapshot
from models.project import MigrationProject
from models.schema_version import SchemaSnapshot
from models.source_record import SourceRecord


class SourceRecordData(TypedDict):
    source_record_id: str
    row_ordinal: int
    original_record: dict
    canonical_record: dict
    record_hash: str
    schema_valid: bool


async def create_dataset_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
    source_schema_snapshot_id: UUID,
    original_object_key: str,
    original_checksum: str,
    parser_version: str,
    upload_size_bytes: int,
    created_by: str,
) -> DatasetSnapshot:
    # Serializes dataset version creation for this project.
    project_statement = (
        select(MigrationProject.id)
        .where(MigrationProject.id == project_id)
        .with_for_update()
    )
    project_result = await session.execute(project_statement)
    project_result.scalar_one()

    # Confirms that the selected schema belongs to this project
    # and is a source schema.
    schema_statement = select(SchemaSnapshot.id).where(
        SchemaSnapshot.id == source_schema_snapshot_id,
        SchemaSnapshot.project_id == project_id,
        SchemaSnapshot.schema_role == SchemaRole.SOURCE.value,
    )
    schema_result = await session.execute(schema_statement)
    schema_result.scalar_one()

    previous_dataset = await get_latest_dataset_snapshot(
        session,
        project_id=project_id,
    )

    version = (
        previous_dataset.version + 1
        if previous_dataset is not None
        else 1
    )

    dataset = DatasetSnapshot(
        project_id=project_id,
        source_schema_snapshot_id=source_schema_snapshot_id,
        version=version,
        original_object_key=original_object_key,
        original_checksum=original_checksum,
        parser_version=parser_version,
        upload_size_bytes=upload_size_bytes,
        created_by=created_by,
    )

    session.add(dataset)
    await session.flush()
    await session.refresh(dataset)

    return dataset


async def get_dataset_snapshot_by_id(
    session: AsyncSession,
    *,
    project_id: UUID,
    dataset_id: UUID,
) -> DatasetSnapshot | None:
    statement = select(DatasetSnapshot).where(
        DatasetSnapshot.id == dataset_id,
        DatasetSnapshot.project_id == project_id,
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_latest_dataset_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> DatasetSnapshot | None:
    statement = (
        select(DatasetSnapshot)
        .where(DatasetSnapshot.project_id == project_id)
        .order_by(DatasetSnapshot.version.desc())
        .limit(1)
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_dataset_snapshot_by_checksum(
    session: AsyncSession,
    *,
    project_id: UUID,
    original_checksum: str,
) -> DatasetSnapshot | None:
    statement = (
        select(DatasetSnapshot)
        .where(
            DatasetSnapshot.project_id == project_id,
            DatasetSnapshot.original_checksum == original_checksum,
        )
        .order_by(DatasetSnapshot.version.desc())
        .limit(1)
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_dataset_snapshots(
    session: AsyncSession,
    *,
    project_id: UUID,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[DatasetSnapshot]:
    statement = (
        select(DatasetSnapshot)
        .where(DatasetSnapshot.project_id == project_id)
        .order_by(DatasetSnapshot.version.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(statement)
    return result.scalars().all()


async def update_dataset_status(
    session: AsyncSession,
    *,
    dataset: DatasetSnapshot,
    status: DatasetStatus,
    record_count: int | None = None,
    canonical_hash: str | None = None,
) -> DatasetSnapshot:
    dataset.status = status.value

    if record_count is not None:
        dataset.record_count = record_count

    if canonical_hash is not None:
        dataset.canonical_hash = canonical_hash

    await session.flush()
    await session.refresh(dataset)

    return dataset


async def create_source_records(
    session: AsyncSession,
    *,
    dataset_id: UUID,
    records: Sequence[SourceRecordData],
    batch_size: int = 500,
) -> Sequence[SourceRecord]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    source_records = [
        SourceRecord(
            dataset_id=dataset_id,
            source_record_id=record["source_record_id"],
            row_ordinal=record["row_ordinal"],
            original_record=record["original_record"],
            canonical_record=record["canonical_record"],
            record_hash=record["record_hash"],
            schema_valid=record["schema_valid"],
        )
        for record in records
    ]

    for start in range(0, len(source_records), batch_size):
        batch = source_records[start : start + batch_size]
        session.add_all(batch)
        await session.flush()

    return source_records


async def get_source_record(
    session: AsyncSession,
    *,
    dataset_id: UUID,
    source_record_id: str,
) -> SourceRecord | None:
    statement = select(SourceRecord).where(
        SourceRecord.dataset_id == dataset_id,
        SourceRecord.source_record_id == source_record_id,
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_source_records(
    session: AsyncSession,
    *,
    dataset_id: UUID,
    offset: int = 0,
    limit: int = 100,
) -> Sequence[SourceRecord]:
    statement = (
        select(SourceRecord)
        .where(SourceRecord.dataset_id == dataset_id)
        .order_by(SourceRecord.row_ordinal.asc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(statement)
    return result.scalars().all()


async def count_source_records(
    session: AsyncSession,
    *,
    dataset_id: UUID,
) -> int:
    statement = (
        select(func.count())
        .select_from(SourceRecord)
        .where(SourceRecord.dataset_id == dataset_id)
    )

    result = await session.execute(statement)
    return int(result.scalar_one())
