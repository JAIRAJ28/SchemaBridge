from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from contracts.dataset_result import DatasetResponse
from routes.route_helpers import (
    ActorId,
    DatabaseSession,
    get_request_id,
)
from services.dataset_upload import ingest_dataset


router = APIRouter(
    prefix="/projects/{project_id}/datasets",
    tags=["datasets"],
)


@router.post(
    "",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset_route(
    project_id: UUID,
    request: Request,
    actor_id: ActorId,
    session: DatabaseSession,
    request_id: Annotated[str, Depends(get_request_id)],
    source_schema_snapshot_id: Annotated[UUID, Query()],
) -> DatasetResponse:
    dataset = await ingest_dataset(
        session,
        project_id=project_id,
        source_schema_snapshot_id=source_schema_snapshot_id,
        actor_id=actor_id,
        request_id=request_id,
        content=await request.body(),
    )
    return DatasetResponse.model_validate(dataset)
