import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from contracts.plan import FieldMapping, PlanCreate
from contracts.rule import (
    ConcatRule,
    CopyRule,
    DefaultIfMissingRule,
    EmptyToNullRule,
    GetPathRule,
    LowercaseRule,
    LookupRule,
    ParseBooleanRule,
    ParseDateRule,
    ParseDecimalRule,
    ParseIntegerRule,
    RuleStep,
    RemoveCharactersRule,
    SplitRule,
    ToStringRule,
    TrimRule,
    UppercaseRule,
)
from contracts.transform_result import FieldProblem, RecordResult


INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
DECIMAL_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


class MissingValue:
    pass


MISSING = MissingValue()


class RuleRunError(ValueError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        value: Any = None,
        rule: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.value = value
        self.rule = rule


def require_one_value(values: list[Any], *, rule_name: str) -> Any:
    if len(values) != 1:
        raise RuleRunError(
            code="INVALID_INPUT_COUNT",
            message=f"Rule '{rule_name}' requires exactly one input.",
            value=values,
        )
    return values[0]


def scalar_to_text(value: Any) -> str:
    if isinstance(value, MissingValue):
        raise RuleRunError(
            code="SOURCE_VALUE_MISSING",
            message="The source value is missing.",
        )
    if value is None:
        raise RuleRunError(
            code="SOURCE_VALUE_NULL",
            message="A null value cannot be converted to text.",
        )
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def run_copy(rule: CopyRule, values: list[Any]) -> Any:
    value = require_one_value(values, rule_name=rule.rule)
    if isinstance(value, MissingValue):
        raise RuleRunError(
            code="SOURCE_VALUE_MISSING",
            message="The source value is missing.",
        )
    return value


def run_trim(rule: TrimRule, values: list[Any]) -> str:
    value = require_one_value(values, rule_name=rule.rule)
    if isinstance(value, MissingValue):
        raise RuleRunError(
            code="SOURCE_VALUE_MISSING",
            message="The source value is missing.",
        )
    if not isinstance(value, str):
        raise RuleRunError(
            code="TRIM_REQUIRES_TEXT",
            message="The trim rule requires a text value.",
            value=value,
        )
    return value.strip()


def run_parse_integer(rule: ParseIntegerRule, values: list[Any]) -> int:
    value = require_one_value(values, rule_name=rule.rule)
    if isinstance(value, bool):
        raise RuleRunError(
            code="INTEGER_PARSE_FAILED",
            message="A boolean cannot be converted to an integer.",
            value=value,
        )
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not INTEGER_PATTERN.fullmatch(value):
        raise RuleRunError(
            code="INTEGER_PARSE_FAILED",
            message=f"Value {value!r} cannot be converted to an integer.",
            value=value,
        )
    return int(value)


def run_parse_decimal(rule: ParseDecimalRule, values: list[Any]) -> Decimal:
    value = require_one_value(values, rule_name=rule.rule)
    if isinstance(value, bool):
        raise RuleRunError(
            code="DECIMAL_PARSE_FAILED",
            message="A boolean cannot be converted to a decimal.",
            value=value,
        )
    text = str(value)
    if not DECIMAL_PATTERN.fullmatch(text):
        raise RuleRunError(
            code="DECIMAL_PARSE_FAILED",
            message=f"Value {value!r} cannot be converted to a decimal.",
            value=value,
        )
    try:
        result = Decimal(text)
    except InvalidOperation as error:
        raise RuleRunError(
            code="DECIMAL_PARSE_FAILED",
            message=f"Value {value!r} cannot be converted to a decimal.",
            value=value,
        ) from error
    if not result.is_finite():
        raise RuleRunError(
            code="DECIMAL_PARSE_FAILED",
            message="Decimal values must be finite.",
            value=value,
        )
    return result


def run_parse_date(rule: ParseDateRule, values: list[Any]) -> str:
    value = require_one_value(values, rule_name=rule.rule)
    if not isinstance(value, str):
        raise RuleRunError(
            code="DATE_PARSE_FAILED",
            message="The date rule requires a text value.",
            value=value,
        )
    try:
        parsed = datetime.strptime(value, rule.input_format)
    except ValueError as error:
        raise RuleRunError(
            code="DATE_PARSE_FAILED",
            message=(
                f"Value {value!r} does not match format "
                f"{rule.input_format!r}."
            ),
            value=value,
        ) from error
    return parsed.strftime(rule.output_format)


def run_parse_boolean(rule: ParseBooleanRule, values: list[Any]) -> bool:
    value = require_one_value(values, rule_name=rule.rule)
    if isinstance(value, bool):
        return value
    text = scalar_to_text(value)
    if rule.case_sensitive:
        true_values = set(rule.true_values)
        false_values = set(rule.false_values)
    else:
        text = text.casefold()
        true_values = {item.casefold() for item in rule.true_values}
        false_values = {item.casefold() for item in rule.false_values}
    if text in true_values:
        return True
    if text in false_values:
        return False
    raise RuleRunError(
        code="BOOLEAN_PARSE_FAILED",
        message=f"Value {value!r} is not a supported boolean value.",
        value=value,
    )


def run_lookup(rule: LookupRule, values: list[Any]) -> Any:
    value = require_one_value(values, rule_name=rule.rule)
    key = scalar_to_text(value)
    if key in rule.values:
        return rule.values[key]
    if rule.missing_value == "keep_original":
        return value
    raise RuleRunError(
        code="LOOKUP_VALUE_NOT_FOUND",
        message=f"Lookup value {key!r} was not found.",
        value=value,
    )


def run_default_if_missing(
    rule: DefaultIfMissingRule,
    values: list[Any],
) -> Any:
    if not values:
        return rule.value
    value = require_one_value(values, rule_name=rule.rule)
    return rule.value if isinstance(value, MissingValue) else value


def run_concat(rule: ConcatRule, values: list[Any]) -> str:
    if not values:
        raise RuleRunError(
            code="CONCAT_REQUIRES_INPUT",
            message="The concat rule requires at least one input.",
        )
    return rule.separator.join(scalar_to_text(value) for value in values)


def run_get_path(rule: GetPathRule, values: list[Any]) -> Any:
    value = require_one_value(values, rule_name=rule.rule)
    if isinstance(value, MissingValue):
        raise RuleRunError(
            code="SOURCE_VALUE_MISSING",
            message="The source value is missing.",
        )
    current = value
    for part in rule.path:
        if not isinstance(current, dict):
            raise RuleRunError(
                code="PATH_REQUIRES_OBJECT",
                message=f"Cannot read path part {part!r} from a non-object value.",
                value=current,
            )
        if part not in current:
            raise RuleRunError(
                code="PATH_NOT_FOUND",
                message=f"Nested path part {part!r} was not found.",
                value=current,
            )
        current = current[part]
    return current


def run_lowercase(rule: LowercaseRule, values: list[Any]) -> str:
    value = require_one_value(values, rule_name=rule.rule)
    if not isinstance(value, str):
        raise RuleRunError(
            code="LOWERCASE_REQUIRES_TEXT",
            message="The lowercase rule requires a text value.",
            value=value,
        )
    return value.lower()


def run_uppercase(rule: UppercaseRule, values: list[Any]) -> str:
    value = require_one_value(values, rule_name=rule.rule)
    if not isinstance(value, str):
        raise RuleRunError(
            code="UPPERCASE_REQUIRES_TEXT",
            message="The uppercase rule requires a text value.",
            value=value,
        )
    return value.upper()


def run_remove_characters(
    rule: RemoveCharactersRule,
    values: list[Any],
) -> str:
    value = require_one_value(values, rule_name=rule.rule)
    if not isinstance(value, str):
        raise RuleRunError(
            code="REMOVE_CHARACTERS_REQUIRES_TEXT",
            message="The remove_characters rule requires a text value.",
            value=value,
        )
    return value.translate(str.maketrans("", "", rule.characters))


def run_to_string(rule: ToStringRule, values: list[Any]) -> str:
    value = require_one_value(values, rule_name=rule.rule)
    if isinstance(value, MissingValue):
        raise RuleRunError(
            code="SOURCE_VALUE_MISSING",
            message="The source value is missing.",
        )
    if value is None or isinstance(value, (dict, list)):
        raise RuleRunError(
            code="TO_STRING_REQUIRES_SCALAR",
            message="The to_string rule requires a non-null scalar value.",
            value=value,
        )
    return scalar_to_text(value)


def run_split(rule: SplitRule, values: list[Any]) -> list[str]:
    value = require_one_value(values, rule_name=rule.rule)
    if not isinstance(value, str):
        raise RuleRunError(
            code="SPLIT_REQUIRES_TEXT",
            message="The split rule requires a text value.",
            value=value,
        )
    items = value.split(rule.delimiter)
    if rule.trim_items:
        items = [item.strip() for item in items]
    if rule.drop_empty:
        items = [item for item in items if item]
    return items


def run_empty_to_null(rule: EmptyToNullRule, values: list[Any]) -> Any:
    value = require_one_value(values, rule_name=rule.rule)
    if isinstance(value, MissingValue):
        raise RuleRunError(
            code="SOURCE_VALUE_MISSING",
            message="The source value is missing.",
        )
    if isinstance(value, str) and not value.strip():
        return None
    return value


def run_rule(*, rule: RuleStep, values: list[Any]) -> Any:
    try:
        if isinstance(rule, CopyRule):
            return run_copy(rule, values)
        if isinstance(rule, TrimRule):
            return run_trim(rule, values)
        if isinstance(rule, ParseIntegerRule):
            return run_parse_integer(rule, values)
        if isinstance(rule, ParseDecimalRule):
            return run_parse_decimal(rule, values)
        if isinstance(rule, ParseDateRule):
            return run_parse_date(rule, values)
        if isinstance(rule, ParseBooleanRule):
            return run_parse_boolean(rule, values)
        if isinstance(rule, LookupRule):
            return run_lookup(rule, values)
        if isinstance(rule, DefaultIfMissingRule):
            return run_default_if_missing(rule, values)
        if isinstance(rule, ConcatRule):
            return run_concat(rule, values)
        if isinstance(rule, GetPathRule):
            return run_get_path(rule, values)
        if isinstance(rule, LowercaseRule):
            return run_lowercase(rule, values)
        if isinstance(rule, UppercaseRule):
            return run_uppercase(rule, values)
        if isinstance(rule, RemoveCharactersRule):
            return run_remove_characters(rule, values)
        if isinstance(rule, ToStringRule):
            return run_to_string(rule, values)
        if isinstance(rule, SplitRule):
            return run_split(rule, values)
        if isinstance(rule, EmptyToNullRule):
            return run_empty_to_null(rule, values)
    except RuleRunError as error:
        if error.rule is None:
            error.rule = rule.rule
        raise

    raise RuleRunError(
        code="RULE_NOT_SUPPORTED",
        message="The requested rule is not supported.",
        rule=getattr(rule, "rule", None),
    )


def run_mapping(*, mapping: FieldMapping, source_record: dict) -> Any:
    values: list[Any] = [
        source_record.get(field_name, MISSING)
        for field_name in mapping.source_fields
    ]
    for rule in mapping.rules:
        values = [run_rule(rule=rule, values=values)]
    return require_one_value(values, rule_name="mapping")


def transform_record(*, plan: PlanCreate, source_record: dict) -> RecordResult:
    transformed_record: dict = {}
    problems: list[FieldProblem] = []

    for mapping in plan.mappings:
        try:
            transformed_record[mapping.target_field] = run_mapping(
                mapping=mapping,
                source_record=source_record,
            )
        except RuleRunError as error:
            problems.append(
                FieldProblem(
                    stage="transformation",
                    code=error.code,
                    message=error.message,
                    target_field=mapping.target_field,
                    source_fields=mapping.source_fields,
                    rule=error.rule,
                    value=error.value,
                )
            )

    return RecordResult(
        valid=not problems,
        transformed_record=transformed_record,
        problems=problems,
    )
