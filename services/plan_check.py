from config.constants import SchemaRole, SupportedDataType
from contracts.plan import FieldMapping, PlanCreate
from contracts.plan_check import PlanCheckResult, PlanProblem
from contracts.schema import SchemaDefinition
from services.rule_list import get_rule


RULE_OUTPUT_TYPES = {
    "trim": SupportedDataType.STRING,
    "parse_integer": SupportedDataType.INTEGER,
    "parse_decimal": SupportedDataType.DECIMAL,
    "parse_date": SupportedDataType.DATE,
    "parse_boolean": SupportedDataType.BOOLEAN,
    "concat": SupportedDataType.STRING,
}


def check_mapping_inputs(
    *,
    mapping: FieldMapping,
    mapping_number: int,
) -> list[PlanProblem]:
    problems: list[PlanProblem] = []
    current_input_count = len(mapping.source_fields)

    for rule_step in mapping.rules:
        rule_info = get_rule(rule_step.rule)

        if rule_info is None:
            problems.append(
                PlanProblem(
                    code="RULE_NOT_SUPPORTED",
                    message=f"Rule '{rule_step.rule}' is not supported.",
                    mapping_number=mapping_number,
                    target_field=mapping.target_field,
                    rule=rule_step.rule,
                )
            )
            continue

        if not (
            rule_info.minimum_inputs
            <= current_input_count
            <= rule_info.maximum_inputs
        ):
            problems.append(
                PlanProblem(
                    code="INVALID_RULE_INPUT_COUNT",
                    message=(
                        f"Rule '{rule_step.rule}' received "
                        f"{current_input_count} input fields but supports "
                        f"between {rule_info.minimum_inputs} and "
                        f"{rule_info.maximum_inputs}."
                    ),
                    mapping_number=mapping_number,
                    target_field=mapping.target_field,
                    rule=rule_step.rule,
                )
            )

        current_input_count = 1

    return problems


def check_plan(
    *,
    plan: PlanCreate,
    source_schema: SchemaDefinition,
    target_schema: SchemaDefinition,
) -> PlanCheckResult:
    problems: list[PlanProblem] = []

    if source_schema.schema_role != SchemaRole.SOURCE:
        problems.append(
            PlanProblem(
                code="INVALID_SOURCE_SCHEMA_ROLE",
                message="The selected source schema does not have the source role.",
            )
        )

    if target_schema.schema_role != SchemaRole.TARGET:
        problems.append(
            PlanProblem(
                code="INVALID_TARGET_SCHEMA_ROLE",
                message="The selected target schema does not have the target role.",
            )
        )

    source_field_names = {field.name for field in source_schema.fields}
    target_fields = {field.name: field for field in target_schema.fields}
    mapped_target_fields: set[str] = set()

    for mapping_number, mapping in enumerate(plan.mappings):
        mapped_target_fields.add(mapping.target_field)

        for source_field in mapping.source_fields:
            if source_field not in source_field_names:
                problems.append(
                    PlanProblem(
                        code="SOURCE_FIELD_NOT_FOUND",
                        message=f"Source field '{source_field}' does not exist.",
                        mapping_number=mapping_number,
                        source_field=source_field,
                        target_field=mapping.target_field,
                    )
                )

        if mapping.target_field not in target_fields:
            problems.append(
                PlanProblem(
                    code="TARGET_FIELD_NOT_FOUND",
                    message=f"Target field '{mapping.target_field}' does not exist.",
                    mapping_number=mapping_number,
                    target_field=mapping.target_field,
                )
            )
        elif mapping.rules:
            final_rule = mapping.rules[-1].rule
            output_type = RULE_OUTPUT_TYPES.get(final_rule)

            if final_rule == "copy" and len(mapping.source_fields) == 1:
                source_field = next(
                    (
                        field
                        for field in source_schema.fields
                        if field.name == mapping.source_fields[0]
                    ),
                    None,
                )
                if source_field is not None:
                    output_type = source_field.type

            target_type = target_fields[mapping.target_field].type
            if output_type is not None and output_type != target_type:
                problems.append(
                    PlanProblem(
                        code="RULE_OUTPUT_TYPE_MISMATCH",
                        message=(
                            f"Rule '{final_rule}' produces {output_type.value} "
                            f"but target field '{mapping.target_field}' requires "
                            f"{target_type.value}."
                        ),
                        mapping_number=mapping_number,
                        target_field=mapping.target_field,
                        rule=final_rule,
                    )
                )

        problems.extend(
            check_mapping_inputs(
                mapping=mapping,
                mapping_number=mapping_number,
            )
        )

    for target_field in target_schema.fields:
        if target_field.required and target_field.name not in mapped_target_fields:
            problems.append(
                PlanProblem(
                    code="REQUIRED_TARGET_FIELD_NOT_MAPPED",
                    message=(
                        f"Required target field '{target_field.name}' "
                        "does not have a mapping."
                    ),
                    target_field=target_field.name,
                )
            )

    if (
        target_schema.business_key
        and target_schema.business_key not in mapped_target_fields
    ):
        problems.append(
            PlanProblem(
                code="BUSINESS_KEY_NOT_MAPPED",
                message=(
                    f"Target business key '{target_schema.business_key}' "
                    "does not have a mapping."
                ),
                target_field=target_schema.business_key,
            )
        )

    return PlanCheckResult(
        valid=not problems,
        problems=problems,
    )
