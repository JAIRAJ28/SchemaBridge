from typing import Annotated, Literal, TypeAlias

from pydantic import (
    Field,
    StrictBool,
    StrictStr,
    field_validator,
    model_validator,
)

from contracts.page import StrictContract
from contracts.schema import JSONScalar


class CopyRule(StrictContract):
    rule: Literal["copy"] = "copy"


class TrimRule(StrictContract):
    rule: Literal["trim"] = "trim"


class ParseIntegerRule(StrictContract):
    rule: Literal["parse_integer"] = "parse_integer"


class ParseDecimalRule(StrictContract):
    rule: Literal["parse_decimal"] = "parse_decimal"


class ParseDateRule(StrictContract):
    rule: Literal["parse_date"] = "parse_date"

    input_format: StrictStr = Field(
        min_length=1,
        max_length=50,
    )

    output_format: StrictStr = Field(
        default="%Y-%m-%d",
        min_length=1,
        max_length=50,
    )

    @field_validator("input_format", "output_format")
    @classmethod
    def reject_surrounding_spaces(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "Date formats cannot contain surrounding spaces."
            )

        return value


class ParseBooleanRule(StrictContract):
    rule: Literal["parse_boolean"] = "parse_boolean"

    true_values: list[StrictStr] = Field(
        default_factory=lambda: [
            "true",
            "1",
            "yes",
        ],
        min_length=1,
    )

    false_values: list[StrictStr] = Field(
        default_factory=lambda: [
            "false",
            "0",
            "no",
        ],
        min_length=1,
    )

    case_sensitive: StrictBool = False

    @model_validator(mode="after")
    def validate_boolean_values(
        self,
    ) -> "ParseBooleanRule":
        if self.case_sensitive:
            true_values = set(self.true_values)
            false_values = set(self.false_values)
        else:
            true_values = {
                value.casefold()
                for value in self.true_values
            }
            false_values = {
                value.casefold()
                for value in self.false_values
            }

        if len(true_values) != len(self.true_values):
            raise ValueError(
                "true_values cannot contain duplicates."
            )

        if len(false_values) != len(self.false_values):
            raise ValueError(
                "false_values cannot contain duplicates."
            )

        if true_values & false_values:
            raise ValueError(
                "A value cannot be both true and false."
            )

        return self


class LookupRule(StrictContract):
    rule: Literal["lookup"] = "lookup"

    values: dict[str, JSONScalar | None] = Field(
        min_length=1,
    )

    missing_value: Literal[
        "error",
        "keep_original",
    ] = "error"


class DefaultIfMissingRule(StrictContract):
    rule: Literal[
        "default_if_missing"
    ] = "default_if_missing"

    value: JSONScalar | None


class ConcatRule(StrictContract):
    rule: Literal["concat"] = "concat"

    separator: StrictStr = Field(
        default=" ",
        max_length=50,
    )


RuleStep: TypeAlias = Annotated[
    CopyRule
    | TrimRule
    | ParseIntegerRule
    | ParseDecimalRule
    | ParseDateRule
    | ParseBooleanRule
    | LookupRule
    | DefaultIfMissingRule
    | ConcatRule,
    Field(discriminator="rule"),
]