from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from contracts.page import StrictContract
from contracts.plan import FieldMapping


class MappingRisk(StrictContract):
    code: str = Field(
        min_length=1,
        max_length=100,
    )
    message: str = Field(
        min_length=1,
        max_length=1000,
    )
    severity: Literal[
        "low",
        "medium",
        "high",
    ]
    source_fields: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    target_field: str | None = None


class ClarificationQuestion(StrictContract):
    question: str = Field(
        min_length=1,
        max_length=1000,
    )

    reason: str = Field(
        min_length=1,
        max_length=1000,
    )

    affected_fields: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    blocking: bool = True


class AgentPlanProposal(StrictContract):
    source_schema_version_id: UUID
    target_schema_version_id: UUID
    dataset_version_id: UUID

    plan_name: str = Field(
        min_length=1,
        max_length=200,
    )

    explanation: str = Field(
        min_length=1,
        max_length=2000,
    )

    mappings: list[FieldMapping] = Field(
        default_factory=list,
        max_length=200,
    )

    missing_source_fields: list[str] = Field(
        default_factory=list,
        max_length=200,
    )

    incompatible_fields: list[str] = Field(
        default_factory=list,
        max_length=200,
    )

    risks: list[MappingRisk] = Field(
        default_factory=list,
        max_length=200,
    )

    questions: list[ClarificationQuestion] = Field(
        default_factory=list,
        max_length=100,
    )

    status: Literal[
        "needs_clarification",
        "ready_for_validation",
    ]

    @model_validator(mode="after")
    def validate_proposal_status(
        self,
    ) -> "AgentPlanProposal":
        has_blocking_question = any(
            question.blocking
            for question in self.questions
        )

        if (
            has_blocking_question
            and self.status != "needs_clarification"
        ):
            raise ValueError(
                "A proposal with blocking questions must use "
                "the needs_clarification status."
            )

        if (
            not has_blocking_question
            and self.status == "needs_clarification"
        ):
            raise ValueError(
                "The needs_clarification status requires at least "
                "one blocking question."
            )

        return self
