import re
import math
from typing import TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

from config.constants import (
    AdditionalFieldsPolicy,
    SCHEMA_FORMAT_VERSION,
    SchemaRole,
    SupportedDataType,
)
from config.settings import get_settings


FIELD_NAME_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]{0,127}$"
)

SCHEMA_NAME_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_-]{0,99}$"
)

JSONScalar: TypeAlias = StrictStr | StrictInt | StrictFloat | StrictBool


class FieldDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: SupportedDataType

    required: bool
    nullable: bool
    unique: bool = False
    sensitive: bool = False

    description: str | None = Field(
        default=None,
        max_length=500,
    )

    max_length: int | None = Field(
        default=None,
        gt=0,
    )

    precision: int | None = Field(
        default=None,
        ge=1,
        le=38,
    )

    scale: int | None = Field(
        default=None,
        ge=0,
        le=38,
    )

    format: str | None = Field(
        default=None,
        max_length=50,
    )

    allowed_values: list[JSONScalar] | None = None

    items_type: SupportedDataType | None = None

    @field_validator("name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError(
                "Field names cannot contain surrounding whitespace."
            )

        if not FIELD_NAME_PATTERN.fullmatch(value):
            raise ValueError(
                "Field names may contain letters, numbers and "
                "underscores, and cannot begin with a number."
            )

        return value

    @model_validator(mode="after")
    def validate_constraints(self) -> "FieldDefinition":
        if self.max_length is not None:
            if self.type != SupportedDataType.STRING:
                raise ValueError(
                    "max_length is supported only for string fields."
                )

        if self.precision is not None or self.scale is not None:
            if self.type != SupportedDataType.DECIMAL:
                raise ValueError(
                    "precision and scale are supported only for "
                    "decimal fields."
                )

        if self.scale is not None and self.precision is None:
            raise ValueError(
                "Decimal scale requires decimal precision."
            )

        if (
            self.precision is not None
            and self.scale is not None
            and self.scale > self.precision
        ):
            raise ValueError(
                "Decimal scale cannot be greater than precision."
            )

        if self.allowed_values is not None:
            if self.type in {
                SupportedDataType.ARRAY,
                SupportedDataType.OBJECT,
            }:
                raise ValueError(
                    "allowed_values is supported only for scalar fields."
                )
            if not self.allowed_values:
                raise ValueError(
                    "allowed_values cannot be empty when provided."
                )

            expected_types = {
                SupportedDataType.STRING: (str,),
                SupportedDataType.INTEGER: (int,),
                SupportedDataType.DECIMAL: (int, float),
                SupportedDataType.BOOLEAN: (bool,),
                SupportedDataType.DATE: (str,),
                SupportedDataType.DATETIME: (str,),
            }[self.type]

            for value in self.allowed_values:
                if type(value) not in expected_types:
                    raise ValueError(
                        "Every allowed value must match the declared field type."
                    )

                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(
                        "allowed_values cannot contain non-finite numbers."
                    )

            unique_values = {
                (type(value).__name__, repr(value))
                for value in self.allowed_values
            }
            if len(unique_values) != len(self.allowed_values):
                raise ValueError(
                    "allowed_values cannot contain duplicates."
                )

        if self.type == SupportedDataType.ARRAY:
            if self.items_type is None:
                raise ValueError("Array fields must define items_type.")
            if self.items_type in {
                SupportedDataType.ARRAY,
                SupportedDataType.OBJECT,
            }:
                raise ValueError("Nested collection items are not supported.")
        elif self.items_type is not None:
            raise ValueError("items_type is supported only for array fields.")

        return self


class SchemaDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    schema_role: SchemaRole
    schema_format_version: str = SCHEMA_FORMAT_VERSION
    additional_fields_policy: AdditionalFieldsPolicy

    business_key: str | None = None

    fields: list[FieldDefinition] = Field(
        min_length=1,
    )

    @field_validator("schema_name")
    @classmethod
    def validate_schema_name(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError(
                "Schema name cannot contain surrounding whitespace."
            )

        if not SCHEMA_NAME_PATTERN.fullmatch(value):
            raise ValueError(
                "Schema name contains unsupported characters."
            )

        return value

    @field_validator("schema_format_version")
    @classmethod
    def validate_schema_format_version(cls, value: str) -> str:
        if value != SCHEMA_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported schema format version: {value}. "
                f"Supported version: {SCHEMA_FORMAT_VERSION}."
            )

        return value

    @model_validator(mode="after")
    def validate_schema(self) -> "SchemaDefinition":
        if len(self.fields) > get_settings().max_schema_fields:
            raise ValueError(
                "Schema exceeds the configured maximum field count."
            )

        field_names = [field.name for field in self.fields]

        if len(field_names) != len(set(field_names)):
            raise ValueError(
                "Schema field names must be unique."
            )

        if self.schema_role == SchemaRole.SOURCE:
            if (
                self.additional_fields_policy
                != AdditionalFieldsPolicy.PROFILE
            ):
                raise ValueError(
                    "Source schemas must profile undeclared fields."
                )

        if self.schema_role == SchemaRole.TARGET:
            if (
                self.additional_fields_policy
                != AdditionalFieldsPolicy.REJECT
            ):
                raise ValueError(
                    "Target schemas must reject undeclared fields."
                )

            if not self.business_key:
                raise ValueError(
                    "Target schema must define a business key."
                )

            business_key_field = next(
                (
                    field
                    for field in self.fields
                    if field.name == self.business_key
                ),
                None,
            )

            if business_key_field is None:
                raise ValueError(
                    "Target business key must exist in target fields."
                )

            if not business_key_field.required:
                raise ValueError(
                    "Target business key must be required."
                )

            if business_key_field.nullable:
                raise ValueError(
                    "Target business key cannot be nullable."
                )

            if not business_key_field.unique:
                raise ValueError(
                    "Target business key must be unique."
                )

        return self
