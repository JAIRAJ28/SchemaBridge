from collections.abc import Sequence
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.dry_run import DryRun, DryRunRecord, TargetRecord


class DryRunRecordData(TypedDict):
    source_record_id: UUID
    row_ordinal: int
    status: str
    transformed_record: dict
    field_errors: list[dict]
    record_hash: str


async def get_target_key_hashes(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> set[str]:
    result = await session.execute(
        select(TargetRecord.business_key_hash).where(
            TargetRecord.project_id == project_id
        )
    )
    return set(result.scalars().all())


async def create_dry_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    plan_id: UUID,
    dataset_id: UUID,
    source_count: int,
    transformed_count: int,
    accepted_count: int,
    rejected_count: int,
    result_hash: str,
    rule_list_version: str,
    engine_version: str,
    target_revision: int,
    created_by: str,
) -> DryRun:
    dry_run = DryRun(
        project_id=project_id,
        plan_id=plan_id,
        dataset_id=dataset_id,
        status="completed",
        source_count=source_count,
        transformed_count=transformed_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        result_hash=result_hash,
        rule_list_version=rule_list_version,
        engine_version=engine_version,
        target_revision=target_revision,
        created_by=created_by,
    )
    session.add(dry_run)
    await session.flush()
    await session.refresh(dry_run)
    return dry_run


async def create_dry_run_records(
    session: AsyncSession,
    *,
    dry_run_id: UUID,
    records: Sequence[DryRunRecordData],
) -> list[DryRunRecord]:
    stored = [
        DryRunRecord(dry_run_id=dry_run_id, **record)
        for record in records
    ]
    session.add_all(stored)
    await session.flush()
    return stored


async def get_dry_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    plan_id: UUID,
    dry_run_id: UUID,
) -> DryRun | None:
    result = await session.execute(
        select(DryRun).where(
            DryRun.id == dry_run_id,
            DryRun.project_id == project_id,
            DryRun.plan_id == plan_id,
        )
    )
    return result.scalar_one_or_none()


async def list_dry_run_records(
    session: AsyncSession,
    *,
    dry_run_id: UUID,
    offset: int,
    limit: int,
) -> Sequence[DryRunRecord]:
    result = await session.execute(
        select(DryRunRecord)
        .where(DryRunRecord.dry_run_id == dry_run_id)
        .order_by(DryRunRecord.row_ordinal.asc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


async def list_accepted_dry_run_records(
    session: AsyncSession,
    *,
    dry_run_id: UUID,
) -> Sequence[DryRunRecord]:
    result = await session.execute(
        select(DryRunRecord)
        .where(
            DryRunRecord.dry_run_id == dry_run_id,
            DryRunRecord.status == "accepted",
        )
        .order_by(DryRunRecord.row_ordinal.asc())
    )
    return result.scalars().all()


async def count_dry_run_records(
    session: AsyncSession,
    *,
    dry_run_id: UUID,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(DryRunRecord)
        .where(DryRunRecord.dry_run_id == dry_run_id)
    )
    return int(result.scalar_one())
