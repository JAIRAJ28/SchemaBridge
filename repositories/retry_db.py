from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.retry_record import IdempotencyRecord


async def get_active_idempotency_record(
    session: AsyncSession,
    *,
    actor_id: str,
    scope: str,
    idempotency_key: str,
    current_time: datetime,
) -> IdempotencyRecord | None:
    result = await session.execute(
        select(IdempotencyRecord).where(
            IdempotencyRecord.actor_id == actor_id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.idempotency_key == idempotency_key,
            IdempotencyRecord.expires_at > current_time,
        )
    )
    return result.scalar_one_or_none()


async def create_idempotency_record(
    session: AsyncSession,
    *,
    actor_id: str,
    scope: str,
    idempotency_key: str,
    request_hash: str,
    expires_at: datetime,
    resource_type: str | None = None,
    resource_id: UUID | str | None = None,
    response_status: int | None = None,
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        actor_id=actor_id,
        scope=scope,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        expires_at=expires_at,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        response_status=response_status,
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record
