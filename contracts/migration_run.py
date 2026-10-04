from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict

from contracts.page import StrictContract


class MigrationRunResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    approval_id: UUID
    dry_run_id: UUID
    plan_id: UUID
    status: str
    source_count: int
    accepted_count: int
    rejected_count: int
    inserted_count: int
    target_revision_before: int
    target_revision_after: int
    reconciliation: dict
    created_by: str
    completed_at: datetime | None
    rolled_back_at: datetime | None
    created_at: datetime


class MigrationAttemptResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    migration_run_id: UUID
    action: Literal["execute", "retry", "reconcile", "rollback"]
    status: Literal["succeeded", "failed"]
    actor_id: str
    idempotency_key: str | None
    details: dict
    completed_at: datetime
    created_at: datetime


class ReconciliationResponse(StrictContract):
    migration_run_id: UUID
    migration_status: str
    valid: bool
    details: dict


class HistoryEventResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    actor_id: str
    event_type: str
    resource_type: str
    resource_id: str
    event_metadata: dict
    request_id: str
    created_at: datetime
