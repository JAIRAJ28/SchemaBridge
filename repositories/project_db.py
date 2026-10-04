from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from sqlalchemy import Select, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.project import MigrationProject


ProjectStatus = Literal[
    "draft",
    "active",
    "completed",
    "archived",
]


async def create_project(
    session: AsyncSession,
    *,
    owner_id: str,
    name: str,
    target_namespace: str,
    description: str | None = None,
) -> MigrationProject:
    project = MigrationProject(
        owner_id=owner_id,
        name=name,
        description=description,
        target_namespace=target_namespace,
    )

    session.add(project)
    await session.flush()
    await session.refresh(project)

    return project


async def get_project_by_id(
    session: AsyncSession,
    *,
    project_id: UUID,
    owner_id: str,
) -> MigrationProject | None:
    statement = select(MigrationProject).where(
        MigrationProject.id == project_id,
        MigrationProject.owner_id == owner_id,
    )

    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_projects(
    session: AsyncSession,
    *,
    owner_id: str,
    offset: int = 0,
    limit: int = 50,
) -> Sequence[MigrationProject]:
    statement: Select[tuple[MigrationProject]] = (
        select(MigrationProject)
        .where(MigrationProject.owner_id == owner_id)
        .order_by(
            MigrationProject.created_at.desc(),
            MigrationProject.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(statement)
    return result.scalars().all()


async def project_name_exists(
    session: AsyncSession,
    *,
    owner_id: str,
    name: str,
) -> bool:
    statement = select(
        exists().where(
            MigrationProject.owner_id == owner_id,
            MigrationProject.name == name,
        )
    )

    result = await session.execute(statement)
    return bool(result.scalar())


async def update_project_status(
    session: AsyncSession,
    *,
    project: MigrationProject,
    status: ProjectStatus,
) -> MigrationProject:
    project.status = status

    await session.flush()
    await session.refresh(project)

    return project