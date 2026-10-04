from pydantic import Field, model_validator

from contracts.page import StrictContract


class PlanProblem(StrictContract):
    code: str = Field(
        min_length=1,
        max_length=100,
    )

    message: str = Field(
        min_length=1,
        max_length=1000,
    )

    mapping_number: int | None = Field(
        default=None,
        ge=0,
    )

    source_field: str | None = None
    target_field: str | None = None
    rule: str | None = None


class PlanCheckResult(StrictContract):
    valid: bool

    problems: list[PlanProblem] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "PlanCheckResult":
        if self.valid and self.problems:
            raise ValueError(
                "A valid plan cannot contain problems."
            )

        if not self.valid and not self.problems:
            raise ValueError(
                "An invalid plan must contain problems."
            )

        return self
