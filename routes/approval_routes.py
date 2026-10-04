from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from contracts.approval import ApprovalCreate, ApprovalResponse
from routes.route_helpers import ActorId, DatabaseSession, get_request_id
from services.approval_actions import decide_dry_run, get_dry_run_approval


router = APIRouter(
    prefix=(
        "/projects/{project_id}/plans/{plan_id}/"
        "dry-runs/{dry_run_id}/approval"
    ),
    tags=["approvals"],
)


@router.post(
    "",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def decide_dry_run_route(
    project_id: UUID,
    plan_id: UUID,
    dry_run_id: UUID,
    body: ApprovalCreate,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
) -> ApprovalResponse:
    approval = await decide_dry_run(
        session,
        project_id=project_id,
        plan_id=plan_id,
        dry_run_id=dry_run_id,
        actor_id=actor_id,
        request_id=request_id,
        request=body,
    )
    return ApprovalResponse.model_validate(approval)


@router.get("", response_model=ApprovalResponse)
async def get_dry_run_approval_route(
    project_id: UUID,
    plan_id: UUID,
    dry_run_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
) -> ApprovalResponse:
    approval = await get_dry_run_approval(
        session,
        project_id=project_id,
        plan_id=plan_id,
        dry_run_id=dry_run_id,
        actor_id=actor_id,
    )
    return ApprovalResponse.model_validate(approval)
