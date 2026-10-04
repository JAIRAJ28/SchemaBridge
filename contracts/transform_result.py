from typing import Any, Literal

from pydantic import Field, model_validator

from contracts.page import StrictContract


class FieldProblem(StrictContract):
    stage: Literal[
        "transformation",
        "target_check",
        "dataset_check",
    ]
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    target_field: str | None = None
    source_fields: list[str] = Field(default_factory=list)
    rule: str | None = None
    value: Any = None


class RecordResult(StrictContract):
    valid: bool
    transformed_record: dict = Field(default_factory=dict)
    problems: list[FieldProblem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result(self) -> "RecordResult":
        if self.valid and self.problems:
            raise ValueError("A valid record cannot contain problems.")
        if not self.valid and not self.problems:
            raise ValueError("An invalid record must contain problems.")
        return self
