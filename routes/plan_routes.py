from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from contracts.plan import PlanCreate, PlanResponse
from routes.route_helpers import ActorId, DatabaseSession, get_request_id
from services.plan_actions import create_plan_service, get_plan_service


router = APIRouter(
    prefix="/projects/{project_id}/plans",
    tags=["plans"],
)


@router.post(
    "",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_plan_route(
    project_id: UUID,
    request: PlanCreate,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
) -> PlanResponse:
    plan = await create_plan_service(
        session,
        project_id=project_id,
        actor_id=actor_id,
        request_id=request_id,
        request=request,
    )
    return PlanResponse.model_validate(plan)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan_route(
    project_id: UUID,
    plan_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
) -> PlanResponse:
    plan = await get_plan_service(
        session,
        project_id=project_id,
        plan_id=plan_id,
        actor_id=actor_id,
    )
    return PlanResponse.model_validate(plan)
