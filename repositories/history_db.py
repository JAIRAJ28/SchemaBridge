from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.history_event import AuditEvent


async def create_audit_event(
    session: AsyncSession,
    *,
    project_id: UUID,
    actor_id: str,
    event_type: str,
    resource_type: str,
    resource_id: UUID | str,
    request_id: str,
    event_metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        project_id=project_id,
        actor_id=actor_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=str(resource_id),
        request_id=request_id,
        event_metadata=event_metadata or {},
    )
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


async def list_audit_events(
    session: AsyncSession,
    *,
    project_id: UUID,
    offset: int = 0,
    limit: int = 100,
) -> Sequence[AuditEvent]:
    result = await session.execute(
        select(AuditEvent)
        .where(AuditEvent.project_id == project_id)
        .order_by(AuditEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


async def count_audit_events(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.project_id == project_id)
    )
    return int(result.scalar_one())
