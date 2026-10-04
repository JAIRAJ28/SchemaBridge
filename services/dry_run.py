import math
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import (
    DatasetStatus,
    ErrorCode,
    TRANSFORMATION_ENGINE_VERSION,
)
from config.settings import get_settings
from contracts.plan import PlanCreate
from contracts.schema import SchemaDefinition
from middleware.error_handler import ApplicationError
from repositories.dataset_db import (
    get_dataset_snapshot_by_id,
    list_source_records,
)
from repositories.dry_run_db import (
    DryRunRecordData,
    count_dry_run_records,
    create_dry_run,
    create_dry_run_records,
    get_dry_run,
    get_target_key_hashes,
    list_dry_run_records,
)
from repositories.history_db import create_audit_event
from repositories.plan_db import get_plan_version_by_id
from repositories.project_db import get_project_by_id
from repositories.schema_db import get_schema_snapshot_by_id
from services.dataset_check import RecordToCheck, check_dataset_keys
from services.hash_tools import calculate_canonical_hash
from services.target_check import transform_and_check_record
from services.rule_list import RULE_LIST_VERSION


async def run_dry_run(
    session: AsyncSession,
    *,
    project_id: UUID,
    plan_id: UUID,
    actor_id: str,
    request_id: str,
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

    plan_record = await get_plan_version_by_id(
        session, project_id=project_id, plan_id=plan_id
    )
    if plan_record is None or plan_record.status != "valid":
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="A valid migration plan was not found.",
            status_code=404,
        )
    if plan_record.rule_list_version != RULE_LIST_VERSION:
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="The plan uses an unavailable transformation-rule version.",
            status_code=409,
        )

    dataset = await get_dataset_snapshot_by_id(
        session,
        project_id=project_id,
        dataset_id=plan_record.dataset_version_id,
    )
    target_snapshot = await get_schema_snapshot_by_id(
        session,
        project_id=project_id,
        schema_snapshot_id=plan_record.target_schema_version_id,
    )
    if (
        dataset is None
        or dataset.status != DatasetStatus.READY.value
        or target_snapshot is None
    ):
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="The plan dataset or target schema is not ready.",
            status_code=409,
        )

    plan = PlanCreate.model_validate(plan_record.plan_data)
    target_schema = SchemaDefinition.model_validate(
        target_snapshot.normalized_schema
    )
    source_records = await list_source_records(
        session,
        dataset_id=dataset.id,
        limit=get_settings().max_record_count,
    )

    transformed: list[RecordToCheck] = []
    for source in source_records:
        result = transform_and_check_record(
            plan=plan,
            source_record=source.canonical_record,
            target_schema=target_schema,
        )
        transformed.append(
            RecordToCheck(
                source_record_id=source.id,
                row_ordinal=source.row_ordinal,
                result=result,
            )
        )

    checked = check_dataset_keys(
        records=transformed,
        target_schema=target_schema,
        existing_target_key_hashes=await get_target_key_hashes(
            session, project_id=project_id
        ),
    )

    result_rows: list[dict] = []
    stored_rows: list[DryRunRecordData] = []
    transformed_count = 0
    accepted_count = 0
    for item in checked:
        if not any(
            problem.stage == "transformation"
            for problem in item.result.problems
        ):
            transformed_count += 1
        status = "accepted" if item.result.valid else "rejected"
        if item.result.valid:
            accepted_count += 1
        transformed_record = item.result.model_dump(mode="json")[
            "transformed_record"
        ]
        field_errors = [
            problem.model_dump(mode="json")
            for problem in item.result.problems
        ]
        record_hash = calculate_canonical_hash(transformed_record)
        row = {
            "source_record_id": str(item.source_record_id),
            "row_ordinal": item.row_ordinal,
            "status": status,
            "transformed_record": transformed_record,
            "field_errors": field_errors,
            "record_hash": record_hash,
        }
        result_rows.append(row)
        stored_rows.append(
            {
                **row,
                "source_record_id": item.source_record_id,
            }
        )

    source_count = len(checked)
    rejected_count = source_count - accepted_count
    result_hash = calculate_canonical_hash(
        {
            "plan_hash": plan_record.plan_hash,
            "dataset_hash": dataset.canonical_hash,
            "records": result_rows,
        }
    )
    dry_run = await create_dry_run(
        session,
        project_id=project_id,
        plan_id=plan_id,
        dataset_id=dataset.id,
        source_count=source_count,
        transformed_count=transformed_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        result_hash=result_hash,
        rule_list_version=RULE_LIST_VERSION,
        engine_version=TRANSFORMATION_ENGINE_VERSION,
        target_revision=project.target_revision,
        created_by=actor_id,
    )
    await create_dry_run_records(
        session, dry_run_id=dry_run.id, records=stored_rows
    )
    await create_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        event_type="dry_run.completed",
        resource_type="dry_run",
        resource_id=dry_run.id,
        request_id=request_id,
        event_metadata={
            "plan_id": str(plan_id),
            "source_count": source_count,
            "transformed_count": transformed_count,
            "accepted_count": accepted_count,
            "rejected_count": rejected_count,
            "result_hash": result_hash,
        },
    )
    await session.commit()
    await session.refresh(dry_run)
    return dry_run


async def get_dry_run_service(
    session: AsyncSession,
    *,
    project_id: UUID,
    plan_id: UUID,
    dry_run_id: UUID,
    actor_id: str,
):
    project = await get_project_by_id(
        session, project_id=project_id, owner_id=actor_id
    )
    dry_run = await get_dry_run(
        session,
        project_id=project_id,
        plan_id=plan_id,
        dry_run_id=dry_run_id,
    )
    if project is None or dry_run is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Dry run was not found.",
            status_code=404,
        )
    return dry_run


async def list_dry_run_records_service(
    session: AsyncSession,
    *,
    project_id: UUID,
    plan_id: UUID,
    dry_run_id: UUID,
    actor_id: str,
    page: int,
    page_size: int,
):
    await get_dry_run_service(
        session,
        project_id=project_id,
        plan_id=plan_id,
        dry_run_id=dry_run_id,
        actor_id=actor_id,
    )
    total = await count_dry_run_records(session, dry_run_id=dry_run_id)
    records = await list_dry_run_records(
        session,
        dry_run_id=dry_run_id,
        offset=(page - 1) * page_size,
        limit=page_size,
    )
    return records, total, math.ceil(total / page_size) if total else 0
