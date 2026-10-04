from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import ErrorCode
from contracts.project import ProjectCreate
from middleware.error_handler import ApplicationError
from repositories.history_db import create_audit_event
from repositories.project_db import create_project, project_name_exists


async def create_project_service(
    session: AsyncSession,
    *,
    owner_id: str,
    request_id: str,
    request: ProjectCreate,
):
    if await project_name_exists(
        session,
        owner_id=owner_id,
        name=request.name,
    ):
        raise ApplicationError(
            error_code=ErrorCode.CONFLICT,
            message="A project with this name already exists.",
            status_code=409,
        )

    project = await create_project(
        session,
        owner_id=owner_id,
        name=request.name,
        description=request.description,
        target_namespace=request.target_namespace,
    )
    await create_audit_event(
        session,
        project_id=project.id,
        actor_id=owner_id,
        event_type="project.created",
        resource_type="project",
        resource_id=project.id,
        request_id=request_id,
    )
    await session.commit()
    await session.refresh(project)
    return project
