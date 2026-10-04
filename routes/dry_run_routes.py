from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from contracts.dry_run_result import (
    DryRunRecordResponse,
    DryRunResponse,
)
from contracts.page import (
    PageMetadata,
    PaginatedResponse,
    PaginationParams,
)
from routes.route_helpers import (
    ActorId,
    DatabaseSession,
    get_pagination,
    get_request_id,
)
from services.dry_run import (
    get_dry_run_service,
    list_dry_run_records_service,
    run_dry_run,
)


router = APIRouter(
    prefix="/projects/{project_id}/plans/{plan_id}/dry-runs",
    tags=["dry runs"],
)


@router.post(
    "",
    response_model=DryRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dry_run_route(
    project_id: UUID,
    plan_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
) -> DryRunResponse:
    dry_run = await run_dry_run(
        session,
        project_id=project_id,
        plan_id=plan_id,
        actor_id=actor_id,
        request_id=request_id,
    )
    return DryRunResponse.model_validate(dry_run)


@router.get(
    "/{dry_run_id}",
    response_model=DryRunResponse,
)
async def get_dry_run_route(
    project_id: UUID,
    plan_id: UUID,
    dry_run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
) -> DryRunResponse:
    dry_run = await get_dry_run_service(
        session,
        project_id=project_id,
        plan_id=plan_id,
        dry_run_id=dry_run_id,
        actor_id=actor_id,
    )
    return DryRunResponse.model_validate(dry_run)


@router.get(
    "/{dry_run_id}/records",
    response_model=PaginatedResponse[DryRunRecordResponse],
)
async def list_dry_run_records_route(
    project_id: UUID,
    plan_id: UUID,
    dry_run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> PaginatedResponse[DryRunRecordResponse]:
    records, total, total_pages = await list_dry_run_records_service(
        session,
        project_id=project_id,
        plan_id=plan_id,
        dry_run_id=dry_run_id,
        actor_id=actor_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse[DryRunRecordResponse](
        items=[DryRunRecordResponse.model_validate(item) for item in records],
        pagination=PageMetadata(
            page=pagination.page,
            page_size=pagination.page_size,
            total_items=total,
            total_pages=total_pages,
        ),
        request_id=request_id,
    )
