from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from contracts.page import StrictContract


class AgentRunStart(StrictContract):
    dataset_id: UUID
    source_schema_id: UUID
    target_schema_id: UUID


class AgentAnswer(StrictContract):
    answer: str = Field(min_length=1, max_length=2000)


class AgentQuestionResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    agent_run_id: UUID
    revision_number: int
    question_number: int
    question: str
    reason: str
    affected_fields: list[str]
    blocking: bool
    answer: str | None
    answered_by: str | None
    answered_at: datetime | None
    created_at: datetime


class AgentRunResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    dataset_id: UUID
    source_schema_id: UUID
    target_schema_id: UUID
    plan_id: UUID | None
    status: str
    model_name: str
    prompt_version: str
    rule_list_version: str
    revision_count: int
    proposal: dict | None
    validation: dict | None
    preview: dict | None
    target_conflicts: dict | None
    tool_evidence: dict
    transcript_metadata: dict
    failure_reason: str | None
    created_by: str
    completed_at: datetime | None
    created_at: datetime
