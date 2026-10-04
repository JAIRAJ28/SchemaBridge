from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status

from contracts.migration_run import (
    HistoryEventResponse,
    MigrationAttemptResponse,
    MigrationRunResponse,
    ReconciliationResponse,
)
from routes.route_helpers import ActorId, DatabaseSession, get_request_id
from services.migration_actions import (
    execute_approved_migration,
    get_migration_run_service,
    list_attempts_service,
    list_project_history,
    reconcile_migration,
    rollback_migration,
)


router = APIRouter(tags=["migrations"])


@router.post(
    "/projects/{project_id}/approvals/{approval_id}/execute",
    response_model=MigrationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def execute_migration_route(
    project_id: UUID,
    approval_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ],
) -> MigrationRunResponse:
    run = await execute_approved_migration(
        session,
        project_id=project_id,
        approval_id=approval_id,
        actor_id=actor_id,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )
    return MigrationRunResponse.model_validate(run)


@router.get(
    "/projects/{project_id}/migration-runs/{run_id}",
    response_model=MigrationRunResponse,
)
async def get_migration_run_route(
    project_id: UUID,
    run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
) -> MigrationRunResponse:
    run = await get_migration_run_service(
        session,
        project_id=project_id,
        run_id=run_id,
        actor_id=actor_id,
    )
    return MigrationRunResponse.model_validate(run)


@router.post(
    "/projects/{project_id}/migration-runs/{run_id}/reconcile",
    response_model=ReconciliationResponse,
)
async def reconcile_migration_route(
    project_id: UUID,
    run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
) -> ReconciliationResponse:
    details = await reconcile_migration(
        session,
        project_id=project_id,
        run_id=run_id,
        actor_id=actor_id,
        request_id=request_id,
    )
    run = await get_migration_run_service(
        session,
        project_id=project_id,
        run_id=run_id,
        actor_id=actor_id,
    )
    return ReconciliationResponse(
        migration_run_id=run.id,
        migration_status=run.status,
        valid=details["valid"],
        details=details,
    )


@router.post(
    "/projects/{project_id}/migration-runs/{run_id}/rollback",
    response_model=MigrationRunResponse,
)
async def rollback_migration_route(
    project_id: UUID,
    run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
) -> MigrationRunResponse:
    run = await rollback_migration(
        session,
        project_id=project_id,
        run_id=run_id,
        actor_id=actor_id,
        request_id=request_id,
    )
    return MigrationRunResponse.model_validate(run)


@router.get(
    "/projects/{project_id}/migration-runs/{run_id}/attempts",
    response_model=list[MigrationAttemptResponse],
)
async def list_migration_attempts_route(
    project_id: UUID,
    run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
) -> list[MigrationAttemptResponse]:
    attempts = await list_attempts_service(
        session,
        project_id=project_id,
        run_id=run_id,
        actor_id=actor_id,
    )
    return [MigrationAttemptResponse.model_validate(item) for item in attempts]


@router.get(
    "/projects/{project_id}/history",
    response_model=list[HistoryEventResponse],
)
async def list_project_history_route(
    project_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
) -> list[HistoryEventResponse]:
    events = await list_project_history(
        session,
        project_id=project_id,
        actor_id=actor_id,
        offset=0,
        limit=200,
    )
    return [HistoryEventResponse.model_validate(item) for item in events]
