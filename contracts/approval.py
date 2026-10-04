from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from contracts.page import StrictContract


class ApprovalCreate(StrictContract):
    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=1000)


class ApprovalResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    dry_run_id: UUID
    plan_id: UUID
    dataset_id: UUID
    source_schema_id: UUID
    target_schema_id: UUID
    decision: Literal["approved", "rejected"]
    bundle_fingerprint: str
    bundle_data: dict
    target_revision: int
    rule_list_version: str
    engine_version: str
    policy_version: str
    decided_by: str
    comment: str | None
    decided_at: datetime
    created_at: datetime
