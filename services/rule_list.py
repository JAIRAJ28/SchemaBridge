from dataclasses import dataclass


@dataclass(frozen=True)
class RuleInfo:
    name: str
    purpose: str
    minimum_inputs: int
    maximum_inputs: int


RULES: dict[str, RuleInfo] = {
    "copy": RuleInfo(
        name="copy",
        purpose="Copy a source value without changing it.",
        minimum_inputs=1,
        maximum_inputs=1,
    ),
    "trim": RuleInfo(
        name="trim",
        purpose="Remove spaces from the beginning and end of text.",
        minimum_inputs=1,
        maximum_inputs=1,
    ),
    "parse_integer": RuleInfo(
        name="parse_integer",
        purpose="Convert a value to an integer.",
        minimum_inputs=1,
        maximum_inputs=1,
    ),
    "parse_decimal": RuleInfo(
        name="parse_decimal",
        purpose="Convert a value to a decimal number.",
        minimum_inputs=1,
        maximum_inputs=1,
    ),
    "parse_date": RuleInfo(
        name="parse_date",
        purpose="Convert a date from one supported format to another.",
        minimum_inputs=1,
        maximum_inputs=1,
    ),
    "parse_boolean": RuleInfo(
        name="parse_boolean",
        purpose="Convert supported text or numbers to true or false.",
        minimum_inputs=1,
        maximum_inputs=1,
    ),
    "lookup": RuleInfo(
        name="lookup",
        purpose="Replace a value using a fixed lookup table.",
        minimum_inputs=1,
        maximum_inputs=1,
    ),
    "default_if_missing": RuleInfo(
        name="default_if_missing",
        purpose="Use a fixed value when the source value is missing.",
        minimum_inputs=0,
        maximum_inputs=1,
    ),
    "concat": RuleInfo(
        name="concat",
        purpose="Join multiple source values into one text value.",
        minimum_inputs=1,
        maximum_inputs=20,
    ),
}


def get_rule(
    rule_name: str,
) -> RuleInfo | None:
    return RULES.get(rule_name)


def list_rules() -> list[RuleInfo]:
    return list(RULES.values())


def is_supported_rule(
    rule_name: str,
) -> bool:
    return rule_name in RULES