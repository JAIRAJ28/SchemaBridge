from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from contracts.data_summary_result import DatasetProfileResponse
from routes.route_helpers import (
    ActorId,
    DatabaseSession,
    get_request_id,
)
from services.data_summary import profile_dataset


router = APIRouter(
    prefix="/projects/{project_id}/datasets/{dataset_id}/profile",
    tags=["profiles"],
)


@router.post(
    "",
    response_model=DatasetProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile_route(
    project_id: UUID,
    dataset_id: UUID,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
) -> DatasetProfileResponse:
    profile = await profile_dataset(
        session,
        project_id=project_id,
        dataset_id=dataset_id,
        actor_id=actor_id,
        request_id=request_id,
    )
    return DatasetProfileResponse.model_validate(profile)
