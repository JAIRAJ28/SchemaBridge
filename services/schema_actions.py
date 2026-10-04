from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import ErrorCode
from contracts.schema import SchemaDefinition
from middleware.error_handler import ApplicationError
from repositories.history_db import create_audit_event
from repositories.project_db import get_project_by_id
from repositories.schema_db import (
    create_schema_snapshot,
    get_schema_snapshot_by_hash,
)
from services.hash_tools import calculate_canonical_hash


async def create_schema_snapshot_service(
    session: AsyncSession,
    *,
    project_id: UUID,
    actor_id: str,
    request_id: str,
    schema: SchemaDefinition,
):
    project = await get_project_by_id(
        session,
        project_id=project_id,
        owner_id=actor_id,
    )
    if project is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Project was not found.",
            status_code=404,
        )

    normalized = schema.model_dump(mode="json")
    schema_hash = calculate_canonical_hash(normalized)
    existing = await get_schema_snapshot_by_hash(
        session,
        project_id=project_id,
        schema_role=schema.schema_role,
        schema_hash=schema_hash,
    )
    if existing is not None:
        return existing

    snapshot = await create_schema_snapshot(
        session,
        project_id=project_id,
        schema_role=schema.schema_role,
        original_schema=normalized,
        normalized_schema=normalized,
        schema_hash=schema_hash,
        created_by=actor_id,
    )
    await create_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        event_type="schema.created",
        resource_type="schema_snapshot",
        resource_id=snapshot.id,
        request_id=request_id,
        event_metadata={
            "role": schema.schema_role.value,
            "version": snapshot.version,
            "hash": schema_hash,
        },
    )
    await session.commit()
    await session.refresh(snapshot)
    return snapshot
