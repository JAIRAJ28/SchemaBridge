from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from contracts.page import StrictContract
from contracts.transform_result import FieldProblem


class DryRunResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    plan_id: UUID
    dataset_id: UUID
    status: str
    source_count: int
    transformed_count: int
    accepted_count: int
    rejected_count: int
    result_hash: str
    rule_list_version: str
    engine_version: str
    target_revision: int
    created_by: str
    created_at: datetime


class DryRunRecordResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    dry_run_id: UUID
    source_record_id: UUID
    row_ordinal: int
    status: Literal["accepted", "rejected"]
    transformed_record: dict
    field_errors: list[FieldProblem] = Field(default_factory=list)
    record_hash: str
    created_at: datetime
