from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import (
    APPROVAL_POLICY_VERSION,
    ErrorCode,
    TRANSFORMATION_ENGINE_VERSION,
)
from contracts.approval import ApprovalCreate
from middleware.error_handler import ApplicationError
from repositories.approval_db import (
    create_approval,
    get_approval_by_dry_run,
    get_project_for_approval,
    has_unanswered_plan_questions,
)
from repositories.dataset_db import get_dataset_snapshot_by_id
from repositories.dry_run_db import get_dry_run
from repositories.history_db import create_audit_event
from repositories.plan_db import get_plan_version_by_id
from repositories.project_db import get_project_by_id
from repositories.schema_db import get_schema_snapshot_by_id
from services.hash_tools import calculate_canonical_hash
from services.rule_list import RULE_LIST_VERSION


async def decide_dry_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    plan_id: UUID,
    dry_run_id: UUID,
    actor_id: str,
    request_id: str,
    request: ApprovalCreate,
):
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

    existing = await get_approval_by_dry_run(
        session,
        project_id=project_id,
        dry_run_id=dry_run_id,
    )
    if existing is not None:
        if (
            existing.decision == request.decision
            and existing.comment == request.comment
        ):
            return existing
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="This dry run already has an immutable decision.",
            status_code=409,
        )

    dry_run = await get_dry_run(
        session,
        project_id=project_id,
        plan_id=plan_id,
        dry_run_id=dry_run_id,
    )
    plan = await get_plan_version_by_id(
        session,
        project_id=project_id,
        plan_id=plan_id,
    )
    if dry_run is None or plan is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Dry run or migration plan was not found.",
            status_code=404,
        )
    if dry_run.status != "completed" or plan.status != "valid":
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="Only a completed dry run of a valid plan can be reviewed.",
            status_code=409,
        )
    if (
        request.decision == "approved"
        and await has_unanswered_plan_questions(session, plan_id=plan_id)
    ):
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="Blocking clarification questions must be answered first.",
            status_code=409,
        )
    if (
        dry_run.rule_list_version != RULE_LIST_VERSION
        or dry_run.engine_version != TRANSFORMATION_ENGINE_VERSION
        or dry_run.target_revision != project.target_revision
    ):
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message=(
                "The dry run is stale. Run it again before recording "
                "a decision."
            ),
            status_code=409,
        )

    dataset = await get_dataset_snapshot_by_id(
        session,
        project_id=project_id,
        dataset_id=plan.dataset_version_id,
    )
    source_schema = await get_schema_snapshot_by_id(
        session,
        project_id=project_id,
        schema_snapshot_id=plan.source_schema_version_id,
    )
    target_schema = await get_schema_snapshot_by_id(
        session,
        project_id=project_id,
        schema_snapshot_id=plan.target_schema_version_id,
    )
    if dataset is None or source_schema is None or target_schema is None:
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="An input used by this dry run is no longer available.",
            status_code=409,
        )
    if dataset.canonical_hash is None:
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="The dataset does not have a completed canonical hash.",
            status_code=409,
        )

    bundle_data = {
        "project_id": str(project_id),
        "target_namespace": project.target_namespace,
        "source_schema_id": str(source_schema.id),
        "source_schema_hash": source_schema.schema_hash,
        "target_schema_id": str(target_schema.id),
        "target_schema_hash": target_schema.schema_hash,
        "dataset_id": str(dataset.id),
        "dataset_hash": dataset.canonical_hash,
        "plan_id": str(plan.id),
        "plan_hash": plan.plan_hash,
        "rule_list_version": dry_run.rule_list_version,
        "engine_version": dry_run.engine_version,
        "policy_version": APPROVAL_POLICY_VERSION,
        "dry_run_id": str(dry_run.id),
        "dry_run_result_hash": dry_run.result_hash,
        "source_count": dry_run.source_count,
        "transformed_count": dry_run.transformed_count,
        "accepted_count": dry_run.accepted_count,
        "rejected_count": dry_run.rejected_count,
        "target_revision": dry_run.target_revision,
    }
    fingerprint = calculate_canonical_hash(bundle_data)

    approval = await create_approval(
        session,
        project_id=project_id,
        dry_run_id=dry_run.id,
        plan_id=plan.id,
        dataset_id=dataset.id,
        source_schema_id=source_schema.id,
        target_schema_id=target_schema.id,
        decision=request.decision,
        bundle_fingerprint=fingerprint,
        bundle_data=bundle_data,
        target_revision=dry_run.target_revision,
        rule_list_version=dry_run.rule_list_version,
        engine_version=dry_run.engine_version,
        policy_version=APPROVAL_POLICY_VERSION,
        decided_by=actor_id,
        comment=request.comment,
    )
    await create_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        event_type=f"approval.{request.decision}",
        resource_type="approval",
        resource_id=approval.id,
        request_id=request_id,
        event_metadata={
            "dry_run_id": str(dry_run.id),
            "plan_id": str(plan.id),
            "bundle_fingerprint": fingerprint,
            "target_revision": project.target_revision,
        },
    )
    await session.commit()
    await session.refresh(approval)
    return approval


async def get_dry_run_approval(
    session: AsyncSession,
    *,
    project_id: UUID,
    plan_id: UUID,
    dry_run_id: UUID,
    actor_id: str,
):
    project = await get_project_by_id(
        session,
        project_id=project_id,
        owner_id=actor_id,
    )
    approval = await get_approval_by_dry_run(
        session,
        project_id=project_id,
        dry_run_id=dry_run_id,
    )
    if (
        project is None
        or approval is None
        or approval.plan_id != plan_id
    ):
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Approval was not found.",
            status_code=404,
        )
    return approval
