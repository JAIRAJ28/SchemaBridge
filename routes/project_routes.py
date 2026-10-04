from typing import Annotated

from fastapi import APIRouter, Depends, status

from contracts.project import ProjectCreate, ProjectResponse
from routes.route_helpers import (
    ActorId,
    DatabaseSession,
    get_request_id,
)
from services.project_actions import create_project_service


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_route(
    request: ProjectCreate,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
) -> ProjectResponse:
    project = await create_project_service(
        session,
        owner_id=actor_id,
        request_id=request_id,
        request=request,
    )
    return ProjectResponse.model_validate(project)
