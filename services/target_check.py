import math
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from config.constants import SchemaRole, SupportedDataType
from contracts.plan import PlanCreate
from contracts.schema import FieldDefinition, SchemaDefinition
from contracts.transform_result import FieldProblem, RecordResult
from services.rule_run import transform_record


def value_matches_type(value: Any, data_type: SupportedDataType) -> bool:
    if data_type == SupportedDataType.STRING:
        return isinstance(value, str)
    if data_type == SupportedDataType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if data_type == SupportedDataType.DECIMAL:
        if isinstance(value, bool):
            return False
        if isinstance(value, Decimal):
            return value.is_finite()
        if isinstance(value, int):
            return True
        if isinstance(value, float):
            return math.isfinite(value)
        return False
    if data_type == SupportedDataType.BOOLEAN:
        return isinstance(value, bool)
    if data_type in {SupportedDataType.DATE, SupportedDataType.DATETIME}:
        return isinstance(value, str)
    if data_type == SupportedDataType.ARRAY:
        return isinstance(value, list)
    if data_type == SupportedDataType.OBJECT:
        return isinstance(value, dict)
    return False


def value_has_correct_type(*, value: Any, field: FieldDefinition) -> bool:
    if not value_matches_type(value, field.type):
        return False
    if field.type == SupportedDataType.ARRAY and field.items_type is not None:
        return all(value_matches_type(item, field.items_type) for item in value)
    return True


def check_date_value(*, value: str, field: FieldDefinition) -> bool:
    try:
        if field.format:
            datetime.strptime(value, field.format)
        elif field.type == SupportedDataType.DATE:
            datetime.strptime(value, "%Y-%m-%d")
        else:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def decimal_size(value: Any) -> tuple[int, int] | None:
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation:
        return None
    if not decimal_value.is_finite():
        return None
    _, digits, exponent = decimal_value.as_tuple()
    scale = max(-exponent, 0)
    integer_digits = max(len(digits) + exponent, 0)
    return integer_digits + scale, scale


def check_target_record(
    *,
    record: dict,
    target_schema: SchemaDefinition,
) -> list[FieldProblem]:
    problems: list[FieldProblem] = []
    if target_schema.schema_role != SchemaRole.TARGET:
        return [
            FieldProblem(
                stage="target_check",
                code="INVALID_TARGET_SCHEMA_ROLE",
                message="The selected schema is not a target schema.",
            )
        ]

    target_fields = {field.name: field for field in target_schema.fields}
    for field_name, value in record.items():
        if field_name not in target_fields:
            problems.append(
                FieldProblem(
                    stage="target_check",
                    code="UNKNOWN_TARGET_FIELD",
                    message=f"Target field '{field_name}' is not declared.",
                    target_field=field_name,
                    value=value,
                )
            )

    for field in target_schema.fields:
        if field.name not in record:
            if field.required:
                problems.append(
                    FieldProblem(
                        stage="target_check",
                        code="REQUIRED_TARGET_FIELD_MISSING",
                        message=f"Required target field '{field.name}' is missing.",
                        target_field=field.name,
                    )
                )
            continue

        value = record[field.name]
        if value is None:
            if not field.nullable:
                problems.append(
                    FieldProblem(
                        stage="target_check",
                        code="TARGET_FIELD_CANNOT_BE_NULL",
                        message=f"Target field '{field.name}' cannot be null.",
                        target_field=field.name,
                        value=value,
                    )
                )
            continue

        if not value_has_correct_type(value=value, field=field):
            problems.append(
                FieldProblem(
                    stage="target_check",
                    code="TARGET_TYPE_MISMATCH",
                    message=(
                        f"Target field '{field.name}' requires type "
                        f"'{field.type.value}'."
                    ),
                    target_field=field.name,
                    value=value,
                )
            )
            continue

        if (
            field.max_length is not None
            and isinstance(value, str)
            and len(value) > field.max_length
        ):
            problems.append(
                FieldProblem(
                    stage="target_check",
                    code="TARGET_TEXT_TOO_LONG",
                    message=(
                        f"Target field '{field.name}' exceeds the maximum "
                        f"length of {field.max_length}."
                    ),
                    target_field=field.name,
                    value=value,
                )
            )

        if field.allowed_values is not None and value not in field.allowed_values:
            problems.append(
                FieldProblem(
                    stage="target_check",
                    code="TARGET_VALUE_NOT_ALLOWED",
                    message=(
                        f"Target field '{field.name}' contains a value "
                        "that is not allowed."
                    ),
                    target_field=field.name,
                    value=value,
                )
            )

        if (
            field.type in {SupportedDataType.DATE, SupportedDataType.DATETIME}
            and isinstance(value, str)
            and not check_date_value(value=value, field=field)
        ):
            problems.append(
                FieldProblem(
                    stage="target_check",
                    code="TARGET_DATE_INVALID",
                    message=f"Target field '{field.name}' contains an invalid date.",
                    target_field=field.name,
                    value=value,
                )
            )

        if field.type == SupportedDataType.DECIMAL and field.precision is not None:
            size = decimal_size(value)
            if size is None:
                problems.append(
                    FieldProblem(
                        stage="target_check",
                        code="TARGET_DECIMAL_INVALID",
                        message=f"Target field '{field.name}' contains an invalid decimal.",
                        target_field=field.name,
                        value=value,
                    )
                )
            else:
                total_digits, scale = size
                if total_digits > field.precision:
                    problems.append(
                        FieldProblem(
                            stage="target_check",
                            code="TARGET_DECIMAL_PRECISION_EXCEEDED",
                            message=(
                                f"Target field '{field.name}' exceeds precision "
                                f"{field.precision}."
                            ),
                            target_field=field.name,
                            value=value,
                        )
                    )
                if field.scale is not None and scale > field.scale:
                    problems.append(
                        FieldProblem(
                            stage="target_check",
                            code="TARGET_DECIMAL_SCALE_EXCEEDED",
                            message=(
                                f"Target field '{field.name}' exceeds scale "
                                f"{field.scale}."
                            ),
                            target_field=field.name,
                            value=value,
                        )
                    )

    return problems


def transform_and_check_record(
    *,
    plan: PlanCreate,
    source_record: dict,
    target_schema: SchemaDefinition,
) -> RecordResult:
    transformation = transform_record(plan=plan, source_record=source_record)
    target_problems = check_target_record(
        record=transformation.transformed_record,
        target_schema=target_schema,
    )
    all_problems = [*transformation.problems, *target_problems]
    return RecordResult(
        valid=not all_problems,
        transformed_record=transformation.transformed_record,
        problems=all_problems,
    )
