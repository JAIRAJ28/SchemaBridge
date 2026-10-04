from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import (
    APPROVAL_POLICY_VERSION,
    ErrorCode,
    TRANSFORMATION_ENGINE_VERSION,
)
from contracts.schema import SchemaDefinition
from middleware.error_handler import ApplicationError
from models.migration_run import MigrationRun
from repositories.approval_db import get_approval_by_id, get_project_for_approval
from repositories.dataset_db import get_dataset_snapshot_by_id
from repositories.dry_run_db import (
    get_dry_run,
    get_target_key_hashes,
    list_accepted_dry_run_records,
)
from repositories.history_db import create_audit_event, list_audit_events
from repositories.migration_db import (
    TargetWrite,
    create_migration_attempt,
    create_migration_run,
    get_migration_run,
    get_migration_run_by_approval,
    insert_target_rows,
    list_migration_attempts,
    list_run_ledgers,
    list_run_targets,
    mark_ledgers_rolled_back,
)
from repositories.plan_db import get_plan_version_by_id
from repositories.project_db import get_project_by_id
from repositories.retry_db import create_idempotency_record, get_idempotency_record
from repositories.schema_db import get_schema_snapshot_by_id
from services.dataset_check import business_key_hash
from services.hash_tools import calculate_canonical_hash
from services.rule_list import RULE_LIST_VERSION


async def _owned_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    actor_id: str,
) -> MigrationRun:
    project = await get_project_by_id(
        session,
        project_id=project_id,
        owner_id=actor_id,
    )
    run = await get_migration_run(
        session,
        project_id=project_id,
        run_id=run_id,
    )
    if project is None or run is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Migration run was not found.",
            status_code=404,
        )
    return run


async def _calculate_reconciliation(
    session: AsyncSession,
    *,
    run: MigrationRun,
) -> dict:
    expected = await list_accepted_dry_run_records(
        session,
        dry_run_id=run.dry_run_id,
    )
    ledgers = await list_run_ledgers(session, run_id=run.id)
    targets = await list_run_targets(session, run_id=run.id)

    if run.status == "rolled_back":
        valid = len(targets) == 0 and all(
            ledger.rolled_back_at is not None for ledger in ledgers
        )
        return {
            "valid": valid,
            "state": "rolled_back",
            "expected_target_count": 0,
            "actual_target_count": len(targets),
            "ledger_count": len(ledgers),
        }

    expected_by_source = {
        str(record.source_record_id): record for record in expected
    }
    ledger_by_source = {
        str(ledger.source_record_id): ledger for ledger in ledgers
    }
    target_by_id = {str(target.id): target for target in targets}

    missing_sources = sorted(set(expected_by_source) - set(ledger_by_source))
    unexpected_sources = sorted(set(ledger_by_source) - set(expected_by_source))
    missing_targets: list[str] = []
    ownership_mismatches: list[str] = []
    hash_mismatches: list[str] = []
    key_mismatches: list[str] = []

    for source_id, ledger in ledger_by_source.items():
        target = (
            target_by_id.get(str(ledger.target_record_id))
            if ledger.target_record_id is not None
            else None
        )
        if target is None:
            missing_targets.append(source_id)
            continue
        if target.migration_run_id != run.id:
            ownership_mismatches.append(source_id)
        if calculate_canonical_hash(target.record_data) != ledger.expected_record_hash:
            hash_mismatches.append(source_id)
        if target.business_key_hash != ledger.business_key_hash:
            key_mismatches.append(source_id)

    valid = not any(
        (
            missing_sources,
            unexpected_sources,
            missing_targets,
            ownership_mismatches,
            hash_mismatches,
            key_mismatches,
        )
    ) and len(expected) == len(ledgers) == len(targets)

    return {
        "valid": valid,
        "state": "executed",
        "source_count": run.source_count,
        "accepted_count": run.accepted_count,
        "rejected_count": run.rejected_count,
        "expected_target_count": len(expected),
        "ledger_count": len(ledgers),
        "actual_target_count": len(targets),
        "missing_source_ids": missing_sources[:100],
        "unexpected_source_ids": unexpected_sources[:100],
        "missing_target_source_ids": missing_targets[:100],
        "ownership_mismatch_source_ids": ownership_mismatches[:100],
        "hash_mismatch_source_ids": hash_mismatches[:100],
        "key_mismatch_source_ids": key_mismatches[:100],
    }


async def execute_approved_migration(
    session: AsyncSession,
    *,
    project_id: UUID,
    approval_id: UUID,
    actor_id: str,
    request_id: str,
    idempotency_key: str,
) -> MigrationRun:
    project = await get_project_for_approval(
        session,
        project_id=project_id,
        owner_id=actor_id,
    )
    if project is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Project was not found.",
            status_code=404,
        )

    approval = await get_approval_by_id(
        session,
        project_id=project_id,
        approval_id=approval_id,
    )
    if approval is None or approval.decision != "approved":
        raise ApplicationError(
            error_code=ErrorCode.APPROVAL_REQUIRED,
            message="An approved dry run is required before execution.",
            status_code=409,
        )

    request_hash = calculate_canonical_hash(
        {"project_id": str(project_id), "approval_id": str(approval_id)}
    )
    scope = f"project:{project_id}:migration-execution"
    idempotency = await get_idempotency_record(
        session,
        actor_id=actor_id,
        scope=scope,
        idempotency_key=idempotency_key,
    )
    if idempotency is not None and idempotency.request_hash != request_hash:
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="The idempotency key was already used for another request.",
            status_code=409,
        )

    existing_run = await get_migration_run_by_approval(
        session,
        approval_id=approval_id,
    )
    if existing_run is not None:
        if idempotency is None:
            await create_idempotency_record(
                session,
                actor_id=actor_id,
                scope=scope,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                resource_type="migration_run",
                resource_id=existing_run.id,
                response_status=200,
            )
        await create_migration_attempt(
            session,
            run_id=existing_run.id,
            action="retry",
            status="succeeded",
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            details={"message": "Existing migration run returned."},
        )
        await create_audit_event(
            session,
            project_id=project_id,
            actor_id=actor_id,
            event_type="migration.retry_returned_existing",
            resource_type="migration_run",
            resource_id=existing_run.id,
            request_id=request_id,
        )
        await session.commit()
        await session.refresh(existing_run)
        return existing_run

    if approval.bundle_fingerprint != calculate_canonical_hash(approval.bundle_data):
        raise ApplicationError(
            error_code=ErrorCode.BUNDLE_MISMATCH,
            message="The approval fingerprint does not match its reviewed bundle.",
            status_code=409,
        )
    if (
        approval.target_revision != project.target_revision
        or approval.rule_list_version != RULE_LIST_VERSION
        or approval.engine_version != TRANSFORMATION_ENGINE_VERSION
        or approval.policy_version != APPROVAL_POLICY_VERSION
    ):
        raise ApplicationError(
            error_code=ErrorCode.STALE_TARGET_REVISION,
            message="The approved bundle is stale. Run and approve a new dry run.",
            status_code=409,
        )

    dry_run = await get_dry_run(
        session,
        project_id=project_id,
        plan_id=approval.plan_id,
        dry_run_id=approval.dry_run_id,
    )
    plan = await get_plan_version_by_id(
        session,
        project_id=project_id,
        plan_id=approval.plan_id,
    )
    dataset = await get_dataset_snapshot_by_id(
        session,
        project_id=project_id,
        dataset_id=approval.dataset_id,
    )
    source_schema = await get_schema_snapshot_by_id(
        session,
        project_id=project_id,
        schema_snapshot_id=approval.source_schema_id,
    )
    target_schema_record = await get_schema_snapshot_by_id(
        session,
        project_id=project_id,
        schema_snapshot_id=approval.target_schema_id,
    )
    if any(item is None for item in (dry_run, plan, dataset, source_schema, target_schema_record)):
        raise ApplicationError(
            error_code=ErrorCode.BUNDLE_MISMATCH,
            message="An approved migration input was not found.",
            status_code=409,
        )
    if (
        dry_run.result_hash != approval.bundle_data["dry_run_result_hash"]
        or plan.plan_hash != approval.bundle_data["plan_hash"]
        or dataset.canonical_hash != approval.bundle_data["dataset_hash"]
        or source_schema.schema_hash != approval.bundle_data["source_schema_hash"]
        or target_schema_record.schema_hash != approval.bundle_data["target_schema_hash"]
    ):
        raise ApplicationError(
            error_code=ErrorCode.BUNDLE_MISMATCH,
            message="An approved migration input no longer matches its fingerprint.",
            status_code=409,
        )

    target_schema = SchemaDefinition.model_validate(
        target_schema_record.normalized_schema
    )
    business_key_name = target_schema.business_key
    if business_key_name is None:
        raise ApplicationError(
            error_code=ErrorCode.BUNDLE_MISMATCH,
            message="The approved target schema has no business key.",
            status_code=409,
        )

    accepted = await list_accepted_dry_run_records(
        session,
        dry_run_id=dry_run.id,
    )
    writes: list[TargetWrite] = []
    for record in accepted:
        business_key = record.transformed_record[business_key_name]
        writes.append(
            {
                "source_record_id": record.source_record_id,
                "business_key": business_key,
                "business_key_hash": business_key_hash(business_key),
                "record_data": record.transformed_record,
                "record_hash": record.record_hash,
            }
        )

    current_keys = await get_target_key_hashes(session, project_id=project_id)
    conflicting_keys = sorted(
        {row["business_key_hash"] for row in writes} & current_keys
    )
    if conflicting_keys:
        raise ApplicationError(
            error_code=ErrorCode.TARGET_KEY_CONFLICT,
            message="A business key already exists in the mock target.",
            status_code=409,
        )

    run = await create_migration_run(
        session,
        project_id=project_id,
        approval_id=approval.id,
        dry_run_id=dry_run.id,
        plan_id=plan.id,
        source_count=dry_run.source_count,
        accepted_count=dry_run.accepted_count,
        rejected_count=dry_run.rejected_count,
        target_revision=project.target_revision,
        created_by=actor_id,
    )
    new_revision = project.target_revision + (1 if writes else 0)
    await insert_target_rows(
        session,
        project_id=project_id,
        run_id=run.id,
        target_revision=new_revision,
        rows=writes,
    )
    project.target_revision = new_revision
    run.inserted_count = len(writes)
    run.target_revision_after = new_revision
    run.reconciliation = await _calculate_reconciliation(session, run=run)
    run.status = (
        "completed" if run.reconciliation["valid"] else "reconciliation_failed"
    )
    run.completed_at = datetime.now(timezone.utc)

    await create_migration_attempt(
        session,
        run_id=run.id,
        action="execute",
        status="succeeded",
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        details={
            "inserted_count": run.inserted_count,
            "target_revision": new_revision,
        },
    )
    await create_idempotency_record(
        session,
        actor_id=actor_id,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        resource_type="migration_run",
        resource_id=run.id,
        response_status=201,
    )
    await create_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        event_type="migration.executed",
        resource_type="migration_run",
        resource_id=run.id,
        request_id=request_id,
        event_metadata={
            "approval_id": str(approval.id),
            "inserted_count": run.inserted_count,
            "target_revision_before": run.target_revision_before,
            "target_revision_after": run.target_revision_after,
        },
    )
    await session.commit()
    await session.refresh(run)
    return run


async def get_migration_run_service(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    actor_id: str,
) -> MigrationRun:
    return await _owned_run(
        session,
        project_id=project_id,
        run_id=run_id,
        actor_id=actor_id,
    )


async def reconcile_migration(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    actor_id: str,
    request_id: str,
) -> dict:
    run = await _owned_run(
        session,
        project_id=project_id,
        run_id=run_id,
        actor_id=actor_id,
    )
    result = await _calculate_reconciliation(session, run=run)
    run.reconciliation = result
    if run.status in {"completed", "reconciliation_failed"}:
        run.status = "completed" if result["valid"] else "reconciliation_failed"
    await create_migration_attempt(
        session,
        run_id=run.id,
        action="reconcile",
        status="succeeded" if result["valid"] else "failed",
        actor_id=actor_id,
        details=result,
    )
    await create_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        event_type="migration.reconciled",
        resource_type="migration_run",
        resource_id=run.id,
        request_id=request_id,
        event_metadata={"valid": result["valid"]},
    )
    await session.commit()
    return result


async def rollback_migration(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    actor_id: str,
    request_id: str,
) -> MigrationRun:
    project = await get_project_for_approval(
        session,
        project_id=project_id,
        owner_id=actor_id,
    )
    run = await get_migration_run(
        session,
        project_id=project_id,
        run_id=run_id,
    )
    if project is None or run is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Migration run was not found.",
            status_code=404,
        )
    if run.status == "rolled_back":
        await create_migration_attempt(
            session,
            run_id=run.id,
            action="rollback",
            status="succeeded",
            actor_id=actor_id,
            details={"message": "Migration was already rolled back."},
        )
        await session.commit()
        return run
    if run.status not in {
        "completed",
        "reconciliation_failed",
        "rollback_conflict",
    }:
        raise ApplicationError(
            error_code=ErrorCode.ILLEGAL_STATE,
            message="This migration cannot be rolled back in its current state.",
            status_code=409,
        )

    ledgers = await list_run_ledgers(session, run_id=run.id)
    targets = await list_run_targets(session, run_id=run.id)
    targets_by_id = {str(target.id): target for target in targets}
    conflicts: list[str] = []
    for ledger in ledgers:
        target = (
            targets_by_id.get(str(ledger.target_record_id))
            if ledger.target_record_id is not None
            else None
        )
        if (
            target is None
            or target.migration_run_id != run.id
            or target.business_key_hash != ledger.business_key_hash
            or calculate_canonical_hash(target.record_data)
            != ledger.expected_record_hash
        ):
            conflicts.append(str(ledger.source_record_id))

    now = datetime.now(timezone.utc)
    if conflicts:
        run.status = "rollback_conflict"
        await create_migration_attempt(
            session,
            run_id=run.id,
            action="rollback",
            status="failed",
            actor_id=actor_id,
            details={"conflicting_source_ids": conflicts[:100]},
        )
        await create_audit_event(
            session,
            project_id=project_id,
            actor_id=actor_id,
            event_type="migration.rollback_conflict",
            resource_type="migration_run",
            resource_id=run.id,
            request_id=request_id,
            event_metadata={"conflict_count": len(conflicts)},
        )
        await session.commit()
        await session.refresh(run)
        return run

    for target in targets:
        await session.delete(target)
    await session.flush()
    await mark_ledgers_rolled_back(
        session,
        ledgers=ledgers,
        rolled_back_at=now,
    )
    if targets:
        project.target_revision += 1
    run.target_revision_after = project.target_revision
    run.status = "rolled_back"
    run.rolled_back_at = now
    run.reconciliation = await _calculate_reconciliation(session, run=run)
    await create_migration_attempt(
        session,
        run_id=run.id,
        action="rollback",
        status="succeeded",
        actor_id=actor_id,
        details={
            "deleted_count": len(targets),
            "target_revision": project.target_revision,
        },
    )
    await create_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        event_type="migration.rolled_back",
        resource_type="migration_run",
        resource_id=run.id,
        request_id=request_id,
        event_metadata={
            "deleted_count": len(targets),
            "target_revision": project.target_revision,
        },
    )
    await session.commit()
    await session.refresh(run)
    return run


async def list_attempts_service(
    session: AsyncSession,
    *,
    project_id: UUID,
    run_id: UUID,
    actor_id: str,
):
    await _owned_run(
        session,
        project_id=project_id,
        run_id=run_id,
        actor_id=actor_id,
    )
    return await list_migration_attempts(session, run_id=run_id)


async def list_project_history(
    session: AsyncSession,
    *,
    project_id: UUID,
    actor_id: str,
    offset: int,
    limit: int,
):
    project = await get_project_by_id(
        session,
        project_id=project_id,
        owner_id=actor_id,
    )
    if project is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Project was not found.",
            status_code=404,
        )
    return await list_audit_events(
        session,
        project_id=project_id,
        offset=offset,
        limit=limit,
    )
