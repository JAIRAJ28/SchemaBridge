from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import ErrorCode
from contracts.errors import ErrorDetail
from contracts.plan import PlanCreate
from contracts.schema import SchemaDefinition
from middleware.error_handler import ApplicationError
from repositories.dataset_db import get_dataset_snapshot_by_id
from repositories.history_db import create_audit_event
from repositories.plan_db import (
    create_plan_version,
    get_plan_version_by_hash,
    update_plan_status,
)
from repositories.project_db import get_project_by_id
from repositories.schema_db import get_schema_snapshot_by_id
from services.hash_tools import calculate_canonical_hash
from services.plan_check import check_plan
from services.rule_list import RULE_LIST_VERSION


async def create_plan_service(
    session: AsyncSession,
    *,
    project_id: UUID,
    actor_id: str,
    request_id: str,
    request: PlanCreate,
):
    project = await get_project_by_id(
        session, project_id=project_id, owner_id=actor_id
    )
    if project is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Project was not found.",
            status_code=404,
        )

    source_snapshot = await get_schema_snapshot_by_id(
        session,
        project_id=project_id,
        schema_snapshot_id=request.source_schema_version_id,
    )
    target_snapshot = await get_schema_snapshot_by_id(
        session,
        project_id=project_id,
        schema_snapshot_id=request.target_schema_version_id,
    )
    dataset = await get_dataset_snapshot_by_id(
        session,
        project_id=project_id,
        dataset_id=request.dataset_version_id,
    )
    if source_snapshot is None or target_snapshot is None or dataset is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="A schema or dataset selected by the plan was not found.",
            status_code=404,
        )
    if dataset.source_schema_snapshot_id != source_snapshot.id:
        raise ApplicationError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="The dataset does not use the selected source schema.",
            status_code=422,
        )

    source_schema = SchemaDefinition.model_validate(
        source_snapshot.normalized_schema
    )
    target_schema = SchemaDefinition.model_validate(
        target_snapshot.normalized_schema
    )
    check = check_plan(
        plan=request,
        source_schema=source_schema,
        target_schema=target_schema,
    )
    if not check.valid:
        raise ApplicationError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="The migration plan is invalid.",
            status_code=422,
            details=[
                ErrorDetail(
                    field=problem.target_field or problem.source_field,
                    location=["body", "mappings"],
                    information={
                        "code": problem.code,
                        "message": problem.message,
                    },
                )
                for problem in check.problems
            ],
        )

    plan_data = request.model_dump(mode="json")
    plan_hash = calculate_canonical_hash(
        {"plan": plan_data, "rule_list_version": RULE_LIST_VERSION}
    )
    existing = await get_plan_version_by_hash(
        session, project_id=project_id, plan_hash=plan_hash
    )
    if existing is not None:
        return existing

    plan = await create_plan_version(
        session,
        project_id=project_id,
        source_schema_version_id=request.source_schema_version_id,
        target_schema_version_id=request.target_schema_version_id,
        dataset_version_id=request.dataset_version_id,
        name=request.name,
        description=request.description,
        plan_data=plan_data,
        plan_hash=plan_hash,
        rule_list_version=RULE_LIST_VERSION,
        created_by=actor_id,
    )
    await update_plan_status(session, plan=plan, status="valid")
    await create_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        event_type="plan.created",
        resource_type="migration_plan_version",
        resource_id=plan.id,
        request_id=request_id,
        event_metadata={"version": plan.version, "plan_hash": plan.plan_hash},
    )
    await session.commit()
    await session.refresh(plan)
    return plan
