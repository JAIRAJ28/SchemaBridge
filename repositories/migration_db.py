from collections.abc import Sequence
from datetime import datetime
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.dry_run import TargetRecord
from models.migration_run import MigrationAttempt, MigrationRun, WriteLedger


class TargetWrite(TypedDict):
    source_record_id: UUID
    business_key: object
    business_key_hash: str
    record_data: dict
    record_hash: str


async def get_migration_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
) -> MigrationRun | None:
    result = await session.execute(
        select(MigrationRun).where(
            MigrationRun.id == run_id,
            MigrationRun.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def get_migration_run_by_approval(
    session: AsyncSession,
    *,
    approval_id: UUID,
) -> MigrationRun | None:
    result = await session.execute(
        select(MigrationRun).where(MigrationRun.approval_id == approval_id)
    )
    return result.scalar_one_or_none()


async def create_migration_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    approval_id: UUID,
    dry_run_id: UUID,
    plan_id: UUID,
    source_count: int,
    accepted_count: int,
    rejected_count: int,
    target_revision: int,
    created_by: str,
) -> MigrationRun:
    run = MigrationRun(
        project_id=project_id,
        approval_id=approval_id,
        dry_run_id=dry_run_id,
        plan_id=plan_id,
        status="running",
        source_count=source_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        inserted_count=0,
        target_revision_before=target_revision,
        target_revision_after=target_revision,
        created_by=created_by,
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)
    return run


async def insert_target_rows(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    target_revision: int,
    rows: list[TargetWrite],
) -> list[TargetRecord]:
    targets: list[TargetRecord] = []
    ledgers: list[WriteLedger] = []
    for row in rows:
        target = TargetRecord(
            project_id=project_id,
            business_key=row["business_key"],
            business_key_hash=row["business_key_hash"],
            record_data=row["record_data"],
            migration_run_id=run_id,
            source_record_id=row["source_record_id"],
            target_revision=target_revision,
        )
        session.add(target)
        await session.flush()
        targets.append(target)
        ledgers.append(
            WriteLedger(
                migration_run_id=run_id,
                source_record_id=row["source_record_id"],
                target_record_id=target.id,
                business_key_hash=row["business_key_hash"],
                expected_record_hash=row["record_hash"],
                target_revision=target_revision,
            )
        )
    session.add_all(ledgers)
    await session.flush()
    return targets


async def list_run_ledgers(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> Sequence[WriteLedger]:
    result = await session.execute(
        select(WriteLedger)
        .where(WriteLedger.migration_run_id == run_id)
        .order_by(WriteLedger.created_at, WriteLedger.id)
    )
    return result.scalars().all()


async def list_run_targets(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> Sequence[TargetRecord]:
    result = await session.execute(
        select(TargetRecord)
        .where(TargetRecord.migration_run_id == run_id)
        .order_by(TargetRecord.created_at, TargetRecord.id)
    )
    return result.scalars().all()


async def create_migration_attempt(
    session: AsyncSession,
    *,
    run_id: UUID,
    action: str,
    status: str,
    actor_id: str,
    details: dict,
    idempotency_key: str | None = None,
) -> MigrationAttempt:
    attempt = MigrationAttempt(
        migration_run_id=run_id,
        action=action,
        status=status,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        details=details,
    )
    session.add(attempt)
    await session.flush()
    await session.refresh(attempt)
    return attempt


async def list_migration_attempts(
    session: AsyncSession,
    *,
    run_id: UUID,
) -> Sequence[MigrationAttempt]:
    result = await session.execute(
        select(MigrationAttempt)
        .where(MigrationAttempt.migration_run_id == run_id)
        .order_by(MigrationAttempt.created_at, MigrationAttempt.id)
    )
    return result.scalars().all()


async def mark_ledgers_rolled_back(
    session: AsyncSession,
    *,
    ledgers: Sequence[WriteLedger],
    rolled_back_at: datetime,
) -> None:
    for ledger in ledgers:
        ledger.target_record_id = None
        ledger.rolled_back_at = rolled_back_at
    await session.flush()
