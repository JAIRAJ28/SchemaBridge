from datetime import datetime
from uuid import UUID

from pydantic import (
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from contracts.page import StrictContract
from contracts.rule import RuleStep
from contracts.schema import FIELD_NAME_PATTERN


class FieldMapping(StrictContract):
    source_fields: list[str] = Field(
        max_length=20,
    )

    target_field: str

    rules: list[RuleStep] = Field(
        min_length=1,
        max_length=20,
    )

    @field_validator("source_fields")
    @classmethod
    def validate_source_fields(
        cls,
        value: list[str],
    ) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError(
                "Source fields cannot contain duplicates."
            )

        for field_name in value:
            if not FIELD_NAME_PATTERN.fullmatch(field_name):
                raise ValueError(
                    f"Invalid source field name: {field_name}."
                )

        return value

    @field_validator("target_field")
    @classmethod
    def validate_target_field(
        cls,
        value: str,
    ) -> str:
        if not FIELD_NAME_PATTERN.fullmatch(value):
            raise ValueError(
                "Target field name is invalid."
            )

        return value


class PlanCreate(StrictContract):
    source_schema_version_id: UUID
    target_schema_version_id: UUID
    dataset_version_id: UUID

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    description: str | None = Field(
        default=None,
        max_length=1000,
    )

    mappings: list[FieldMapping] = Field(
        min_length=1,
        max_length=200,
    )

    @model_validator(mode="after")
    def validate_target_mappings(
        self,
    ) -> "PlanCreate":
        target_fields = [
            mapping.target_field
            for mapping in self.mappings
        ]

        if len(target_fields) != len(set(target_fields)):
            raise ValueError(
                "A target field can have only one mapping."
            )

        return self


class PlanResponse(StrictContract):
    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    id: UUID
    project_id: UUID
    previous_plan_id: UUID | None

    source_schema_version_id: UUID
    target_schema_version_id: UUID
    dataset_version_id: UUID

    version: int
    name: str
    description: str | None
    status: str

    plan_data: dict
    plan_hash: str
    rule_list_version: str

    created_by: str
    created_at: datetime