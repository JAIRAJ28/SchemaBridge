"""Generate 1,000 deterministic, synthetic SchemaBridge evaluation cases."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable
from uuid import NAMESPACE_URL, uuid5

from contracts.plan import PlanCreate
from contracts.schema import SchemaDefinition
from services.dataset_check import (
    RecordToCheck,
    business_key_hash,
    check_dataset_keys,
)
from services.plan_check import check_plan
from services.target_check import transform_and_check_record
from services.rule_list import RULE_LIST_VERSION


ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "gold_cases.jsonl"
MANIFEST_PATH = ROOT / "gold_manifest.json"
DATASET_VERSION = "1.0.0"
GENERATION_SEED = 20261005


def field(
    name: str,
    data_type: str,
    *,
    required: bool = True,
    nullable: bool = False,
    unique: bool = False,
    **constraints: Any,
) -> dict[str, Any]:
    return {
        "name": name,
        "type": data_type,
        "required": required,
        "nullable": nullable,
        "unique": unique,
        **constraints,
    }


def mapping(
    source_fields: list[str], target_field: str, *rules: dict[str, Any]
) -> dict[str, Any]:
    return {
        "source_fields": source_fields,
        "target_field": target_field,
        "rules": list(rules),
    }


def copy_rule() -> dict[str, str]:
    return {"rule": "copy"}


def source_schema(case_id: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_name": f"source_{case_id}",
        "schema_role": "source",
        "schema_format_version": "1.0",
        "additional_fields_policy": "profile",
        "business_key": None,
        "fields": fields,
    }


def target_schema(
    case_id: str,
    fields: list[dict[str, Any]],
    business_key: str = "customer_id",
) -> dict[str, Any]:
    return {
        "schema_name": f"target_{case_id}",
        "schema_role": "target",
        "schema_format_version": "1.0",
        "additional_fields_policy": "reject",
        "business_key": business_key,
        "fields": fields,
    }


def executable_case(
    *,
    case_id: str,
    difficulty: str,
    category: str,
    description: str,
    source_fields: list[dict[str, Any]],
    target_fields: list[dict[str, Any]],
    records: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    existing_target_keys: list[Any] | None = None,
    risks: list[dict[str, Any]] | None = None,
    business_key: str = "customer_id",
) -> dict[str, Any]:
    source = source_schema(case_id, source_fields)
    target = target_schema(case_id, target_fields, business_key=business_key)
    source_id = uuid5(NAMESPACE_URL, f"{case_id}:source")
    target_id = uuid5(NAMESPACE_URL, f"{case_id}:target")
    dataset_id = uuid5(NAMESPACE_URL, f"{case_id}:dataset")
    plan_data = {
        "source_schema_version_id": str(source_id),
        "target_schema_version_id": str(target_id),
        "dataset_version_id": str(dataset_id),
        "name": f"Expected plan for {case_id}",
        "description": description,
        "mappings": mappings,
    }
    plan = PlanCreate.model_validate(plan_data)
    source_contract = SchemaDefinition.model_validate(source)
    target_contract = SchemaDefinition.model_validate(target)
    plan_check = check_plan(
        plan=plan,
        source_schema=source_contract,
        target_schema=target_contract,
    )
    if not plan_check.valid:
        raise ValueError(f"Generated plan is invalid for {case_id}: {plan_check.problems}")

    transformed: list[RecordToCheck] = []
    for ordinal, record in enumerate(records):
        result = transform_and_check_record(
            plan=plan,
            source_record=record,
            target_schema=target_contract,
        )
        transformed.append(
            RecordToCheck(
                source_record_id=uuid5(NAMESPACE_URL, f"{case_id}:row:{ordinal}"),
                row_ordinal=ordinal,
                result=result,
            )
        )

    existing_target_keys = existing_target_keys or []
    checked = check_dataset_keys(
        records=transformed,
        target_schema=target_contract,
        existing_target_key_hashes={
            business_key_hash(value) for value in existing_target_keys
        },
    )
    expected_records: list[dict[str, Any]] = []
    transformed_count = 0
    accepted_count = 0
    for item in checked:
        problems = [problem.model_dump(mode="json") for problem in item.result.problems]
        if not any(problem["stage"] == "transformation" for problem in problems):
            transformed_count += 1
        status = "accepted" if item.result.valid else "rejected"
        accepted_count += int(item.result.valid)
        expected_records.append(
            {
                "row_ordinal": item.row_ordinal,
                "status": status,
                "transformed_record": item.result.model_dump(mode="json")[
                    "transformed_record"
                ],
                "error_codes": [problem["code"] for problem in problems],
                "field_errors": problems,
            }
        )

    return {
        "case_id": case_id,
        "dataset_version": DATASET_VERSION,
        "usage": "evaluation_only",
        "difficulty": difficulty,
        "category": category,
        "description": description,
        "review": {
            "status": "pending_human_review",
            "reviewer": None,
            "reviewed_at": None,
        },
        "input": {
            "source_schema": source,
            "target_schema": target,
            "source_records": records,
            "existing_target_business_keys": existing_target_keys,
        },
        "expected": {
            "agent": {
                "proposal_status": "ready_for_validation",
                "mappings": mappings,
                "questions": [],
                "risks": risks or [],
                "missing_source_fields": [],
                "incompatible_fields": [],
            },
            "plan": {"valid": True, "problems": []},
            "dry_run": {
                "source_count": len(records),
                "transformed_count": transformed_count,
                "accepted_count": accepted_count,
                "rejected_count": len(records) - accepted_count,
                "records": expected_records,
            },
            "approval_eligible": True,
        },
    }


def clarification_case(
    *,
    case_id: str,
    description: str,
    source_fields: list[dict[str, Any]],
    target_fields: list[dict[str, Any]],
    records: list[dict[str, Any]],
    question: str,
    reason: str,
    affected_fields: list[str],
    missing_source_fields: list[str] | None = None,
    incompatible_fields: list[str] | None = None,
) -> dict[str, Any]:
    source = source_schema(case_id, source_fields)
    target = target_schema(case_id, target_fields)
    SchemaDefinition.model_validate(source)
    SchemaDefinition.model_validate(target)
    return {
        "case_id": case_id,
        "dataset_version": DATASET_VERSION,
        "usage": "evaluation_only",
        "difficulty": "hard",
        "category": "semantic_blocker",
        "description": description,
        "review": {
            "status": "pending_human_review",
            "reviewer": None,
            "reviewed_at": None,
        },
        "input": {
            "source_schema": source,
            "target_schema": target,
            "source_records": records,
            "existing_target_business_keys": [],
        },
        "expected": {
            "agent": {
                "proposal_status": "needs_clarification",
                "mappings": [],
                "questions": [
                    {
                        "question": question,
                        "reason": reason,
                        "affected_fields": affected_fields,
                        "blocking": True,
                    }
                ],
                "risks": [
                    {
                        "code": "AMBIGUOUS_OR_MISSING_MEANING",
                        "severity": "high",
                        "source_fields": affected_fields,
                    }
                ],
                "missing_source_fields": missing_source_fields or [],
                "incompatible_fields": incompatible_fields or [],
            },
            "plan": None,
            "dry_run": None,
            "approval_eligible": False,
        },
    }


def base_id_fields() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        [field("customer_id", "string", unique=True)],
        [field("customer_id", "string", unique=True)],
    )


def scenario_exact_copy(case_id: str, index: int) -> dict[str, Any]:
    source, target = base_id_fields()
    source.append(field("name", "string"))
    target.append(field("name", "string"))
    records = [
        {"customer_id": f"C{index:04d}A", "name": f"Customer {index} A"},
        {"customer_id": f"C{index:04d}B", "name": f"Customer {index} B"},
    ]
    return executable_case(
        case_id=case_id,
        difficulty="easy",
        category="exact_copy",
        description="Identical source and target fields require direct copy rules.",
        source_fields=source,
        target_fields=target,
        records=records,
        mappings=[
            mapping(["customer_id"], "customer_id", copy_rule()),
            mapping(["name"], "name", copy_rule()),
        ],
    )


def scenario_renamed_copy(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="easy",
        category="renamed_copy",
        description="Clear renamed fields require copy rules.",
        source_fields=[
            field("external_id", "string", unique=True),
            field("full_name", "string"),
        ],
        target_fields=[
            field("customer_id", "string", unique=True),
            field("name", "string"),
        ],
        records=[
            {"external_id": f"E{index:04d}A", "full_name": f"Person {index} A"},
            {"external_id": f"E{index:04d}B", "full_name": f"Person {index} B"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["full_name"], "name", copy_rule()),
        ],
    )


def scenario_trim_text(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="easy",
        category="trim_text",
        description="Whitespace is removed from identifiers and names.",
        source_fields=[field("external_id", "string"), field("full_name", "string")],
        target_fields=[field("customer_id", "string", unique=True), field("name", "string")],
        records=[
            {"external_id": f" T{index:04d}A ", "full_name": f"  Trim Person {index} A  "},
            {"external_id": f" T{index:04d}B ", "full_name": f" Trim Person {index} B "},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", {"rule": "trim"}),
            mapping(["full_name"], "name", {"rule": "trim"}),
        ],
    )


def scenario_integer_valid(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="easy",
        category="parse_integer_valid",
        description="Valid integer text is trimmed and parsed.",
        source_fields=[field("external_id", "string"), field("age_text", "string")],
        target_fields=[field("customer_id", "string", unique=True), field("age", "integer")],
        records=[
            {"external_id": f"I{index:04d}A", "age_text": f" {20 + index % 60} "},
            {"external_id": f"I{index:04d}B", "age_text": str(30 + index % 50)},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["age_text"], "age", {"rule": "trim"}, {"rule": "parse_integer"}),
        ],
    )


def scenario_decimal_valid(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="easy",
        category="parse_decimal_valid",
        description="Valid decimal text is converted to a bounded decimal.",
        source_fields=[field("external_id", "string"), field("balance_text", "string")],
        target_fields=[
            field("customer_id", "string", unique=True),
            field("balance", "decimal", precision=10, scale=2),
        ],
        records=[
            {"external_id": f"D{index:04d}A", "balance_text": f"{100 + index}.25"},
            {"external_id": f"D{index:04d}B", "balance_text": f"{200 + index}.50"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["balance_text"], "balance", {"rule": "parse_decimal"}),
        ],
    )


def scenario_boolean_valid(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="easy",
        category="parse_boolean_valid",
        description="Supported boolean text is converted to true or false.",
        source_fields=[field("external_id", "string"), field("active_text", "string")],
        target_fields=[field("customer_id", "string", unique=True), field("active", "boolean")],
        records=[
            {"external_id": f"B{index:04d}A", "active_text": "yes"},
            {"external_id": f"B{index:04d}B", "active_text": "no"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["active_text"], "active", {"rule": "parse_boolean"}),
        ],
    )


def scenario_date_valid(case_id: str, index: int) -> dict[str, Any]:
    day = 1 + index % 27
    return executable_case(
        case_id=case_id,
        difficulty="medium",
        category="parse_date_valid",
        description="A documented day-first date is normalized to ISO date.",
        source_fields=[field("external_id", "string"), field("joined_text", "string")],
        target_fields=[
            field("customer_id", "string", unique=True),
            field("joined_on", "date", format="%Y-%m-%d"),
        ],
        records=[
            {"external_id": f"DT{index:04d}A", "joined_text": f"{day:02d}/01/2025"},
            {"external_id": f"DT{index:04d}B", "joined_text": f"{day:02d}/02/2025"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(
                ["joined_text"],
                "joined_on",
                {"rule": "parse_date", "input_format": "%d/%m/%Y", "output_format": "%Y-%m-%d"},
            ),
        ],
    )


def scenario_concat_names(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="medium",
        category="concat_names",
        description="First and last names are joined in a documented order.",
        source_fields=[
            field("external_id", "string"),
            field("first_name", "string"),
            field("last_name", "string"),
        ],
        target_fields=[field("customer_id", "string", unique=True), field("full_name", "string")],
        records=[
            {"external_id": f"N{index:04d}A", "first_name": "Asha", "last_name": f"Singh{index}"},
            {"external_id": f"N{index:04d}B", "first_name": "Rohan", "last_name": f"Mehta{index}"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["first_name", "last_name"], "full_name", {"rule": "concat", "separator": " "}),
        ],
    )


def scenario_lookup_status(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="medium",
        category="lookup_status",
        description="Documented status codes are converted with a fixed lookup.",
        source_fields=[field("external_id", "string"), field("status_code", "string")],
        target_fields=[
            field("customer_id", "string", unique=True),
            field("status", "string", allowed_values=["active", "inactive"]),
        ],
        records=[
            {"external_id": f"L{index:04d}A", "status_code": "A"},
            {"external_id": f"L{index:04d}B", "status_code": "I"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["status_code"], "status", {"rule": "lookup", "values": {"A": "active", "I": "inactive"}, "missing_value": "error"}),
        ],
    )


def scenario_default_missing(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="medium",
        category="default_if_missing",
        description="A documented default is used only when an optional source value is missing.",
        source_fields=[
            field("external_id", "string"),
            field("country_code", "string", required=False, nullable=True),
        ],
        target_fields=[field("customer_id", "string", unique=True), field("country", "string")],
        records=[
            {"external_id": f"M{index:04d}A"},
            {"external_id": f"M{index:04d}B", "country_code": "US"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["country_code"], "country", {"rule": "default_if_missing", "value": "IN"}),
        ],
    )


def scenario_mixed(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="medium",
        category="mixed_transformations",
        description="Several supported transformations are applied in one plan.",
        source_fields=[
            field("external_id", "string"),
            field("full_name", "string"),
            field("age_text", "string"),
            field("active_text", "string"),
            field("last_seen", "datetime"),
        ],
        target_fields=[
            field("customer_id", "string", unique=True),
            field("name", "string"),
            field("age", "integer"),
            field("active", "boolean"),
            field("last_seen", "datetime"),
        ],
        records=[
            {"external_id": f" X{index:04d}A ", "full_name": " Asha Singh ", "age_text": "31", "active_text": "yes", "last_seen": "2025-01-10T09:30:00Z"},
            {"external_id": f" X{index:04d}B ", "full_name": " Rohan Mehta ", "age_text": "42", "active_text": "no", "last_seen": "2025-01-11T14:15:00+05:30"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", {"rule": "trim"}),
            mapping(["full_name"], "name", {"rule": "trim"}),
            mapping(["age_text"], "age", {"rule": "parse_integer"}),
            mapping(["active_text"], "active", {"rule": "parse_boolean"}),
            mapping(["last_seen"], "last_seen", copy_rule()),
        ],
    )


def scenario_nullable(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="medium",
        category="nullable_values",
        description="A nullable target accepts a copied null while preserving non-null values.",
        source_fields=[field("external_id", "string"), field("note", "string", required=False, nullable=True)],
        target_fields=[field("customer_id", "string", unique=True), field("note", "string", required=False, nullable=True)],
        records=[
            {"external_id": f"NU{index:04d}A", "note": None},
            {"external_id": f"NU{index:04d}B", "note": f"Note {index}"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["note"], "note", copy_rule()),
        ],
    )


def scenario_extra_source(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="medium",
        category="extra_source_fields",
        description="Unmapped source-only fields are profiled and do not enter the target.",
        source_fields=[
            field("external_id", "string"),
            field("full_name", "string"),
            field("debug_value", "string", required=False, nullable=True),
        ],
        target_fields=[field("customer_id", "string", unique=True), field("name", "string")],
        records=[
            {"external_id": f"EX{index:04d}A", "full_name": "Asha", "debug_value": "ignore-me"},
            {"external_id": f"EX{index:04d}B", "full_name": "Rohan", "undeclared_extra": "profile-me"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["full_name"], "name", copy_rule()),
        ],
    )


def scenario_invalid_numeric(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="hard",
        category="invalid_numeric_quarantine",
        description="Invalid integer and decimal values preserve field-level quarantine evidence.",
        source_fields=[field("external_id", "string"), field("age_text", "string"), field("balance_text", "string")],
        target_fields=[
            field("customer_id", "string", unique=True),
            field("age", "integer"),
            field("balance", "decimal", precision=8, scale=2),
        ],
        records=[
            {"external_id": f"IN{index:04d}A", "age_text": "31", "balance_text": "125.50"},
            {"external_id": f"IN{index:04d}B", "age_text": "not-an-integer", "balance_text": "85.00"},
            {"external_id": f"IN{index:04d}C", "age_text": "44", "balance_text": "not-a-decimal"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["age_text"], "age", {"rule": "parse_integer"}),
            mapping(["balance_text"], "balance", {"rule": "parse_decimal"}),
        ],
        risks=[{"code": "INVALID_NUMERIC_VALUES", "severity": "high", "source_fields": ["age_text", "balance_text"]}],
    )


def scenario_invalid_boolean(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="hard",
        category="invalid_boolean_quarantine",
        description="Unsupported boolean text is rejected with transformation evidence.",
        source_fields=[field("external_id", "string"), field("active_text", "string")],
        target_fields=[field("customer_id", "string", unique=True), field("active", "boolean")],
        records=[
            {"external_id": f"IB{index:04d}A", "active_text": "yes"},
            {"external_id": f"IB{index:04d}B", "active_text": "sometimes"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["active_text"], "active", {"rule": "parse_boolean"}),
        ],
        risks=[{"code": "INVALID_BOOLEAN_VALUE", "severity": "high", "source_fields": ["active_text"]}],
    )


def scenario_invalid_date(case_id: str, index: int) -> dict[str, Any]:
    return executable_case(
        case_id=case_id,
        difficulty="hard",
        category="invalid_date_quarantine",
        description="Invalid dates are rejected without guessing another date format.",
        source_fields=[field("external_id", "string"), field("joined_text", "string")],
        target_fields=[field("customer_id", "string", unique=True), field("joined_on", "date")],
        records=[
            {"external_id": f"ID{index:04d}A", "joined_text": "15/01/2025"},
            {"external_id": f"ID{index:04d}B", "joined_text": "31/02/2025"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["joined_text"], "joined_on", {"rule": "parse_date", "input_format": "%d/%m/%Y", "output_format": "%Y-%m-%d"}),
        ],
        risks=[{"code": "INVALID_DATE_VALUE", "severity": "high", "source_fields": ["joined_text"]}],
    )


def scenario_target_constraint(case_id: str, index: int) -> dict[str, Any]:
    mode = (index - 1) % 6
    common_source = [field("external_id", "string")]
    common_target = [field("customer_id", "string", unique=True)]
    common_mapping = [mapping(["external_id"], "customer_id", copy_rule())]
    source_field_name = ""
    target_field_name = ""
    selected_rule = copy_rule()

    if mode == 0:
        value_field = field("status", "string")
        checked_field = field(
            "status", "string", allowed_values=["active", "inactive"]
        )
        good_value, bad_value = "active", "paused"
        expected_code = "TARGET_VALUE_NOT_ALLOWED"
    elif mode == 1:
        value_field = field("display_name", "string")
        checked_field = field("display_name", "string", max_length=12)
        good_value, bad_value = "Asha Singh", "Name exceeds twelve characters"
        expected_code = "TARGET_TEXT_TOO_LONG"
    elif mode == 2:
        value_field = field("points_code", "string")
        checked_field = field("points", "integer")
        source_field_name, target_field_name = "points_code", "points"
        selected_rule = {
            "rule": "lookup",
            "values": {"VALID": 25, "INVALID": "twenty-five"},
            "missing_value": "error",
        }
        good_value, bad_value = "VALID", "INVALID"
        expected_code = "TARGET_TYPE_MISMATCH"
    elif mode == 3:
        value_field = field("joined_code", "string")
        checked_field = field("joined_on", "date")
        source_field_name, target_field_name = "joined_code", "joined_on"
        selected_rule = {
            "rule": "lookup",
            "values": {"VALID": "2025-01-15", "INVALID": "2025-02-31"},
            "missing_value": "error",
        }
        good_value, bad_value = "VALID", "INVALID"
        expected_code = "TARGET_DATE_INVALID"
    elif mode == 4:
        value_field = field("balance", "decimal")
        checked_field = field("balance", "decimal", precision=6, scale=2)
        good_value, bad_value = 125.5, 1234567.891
        expected_code = "TARGET_DECIMAL_PRECISION_EXCEEDED"
    else:
        value_field = field("region", "string", required=False, nullable=True)
        checked_field = field("region", "string")
        good_value, bad_value = "north", None
        expected_code = "TARGET_FIELD_CANNOT_BE_NULL"

    source_field_name = source_field_name or value_field["name"]
    target_field_name = target_field_name or checked_field["name"]
    return executable_case(
        case_id=case_id,
        difficulty="hard",
        category="target_constraint_violation",
        description="A target constraint violation is rejected with field-level evidence.",
        source_fields=[*common_source, value_field],
        target_fields=[*common_target, checked_field],
        records=[
            {"external_id": f"TV{index:04d}A", source_field_name: good_value},
            {"external_id": f"TV{index:04d}B", source_field_name: bad_value},
        ],
        mappings=[
            *common_mapping,
            mapping([source_field_name], target_field_name, selected_rule),
        ],
        risks=[
            {
                "code": expected_code,
                "severity": "high",
                "source_fields": [source_field_name],
            }
        ],
    )


def scenario_duplicate_key(case_id: str, index: int) -> dict[str, Any]:
    duplicate = f"DUP{index:04d}"
    return executable_case(
        case_id=case_id,
        difficulty="hard",
        category="duplicate_business_key",
        description="Every source row sharing a duplicate business key is quarantined.",
        source_fields=[field("external_id", "string"), field("name", "string")],
        target_fields=[field("customer_id", "string", unique=True), field("name", "string")],
        records=[
            {"external_id": duplicate, "name": "First duplicate"},
            {"external_id": duplicate, "name": "Second duplicate"},
            {"external_id": f"UNQ{index:04d}", "name": "Unique record"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["name"], "name", copy_rule()),
        ],
        risks=[{"code": "DUPLICATE_BUSINESS_KEY", "severity": "high", "source_fields": ["external_id"]}],
    )


def scenario_target_conflict(case_id: str, index: int) -> dict[str, Any]:
    existing = f"EXIST{index:04d}"
    return executable_case(
        case_id=case_id,
        difficulty="hard",
        category="target_business_key_conflict",
        description="A record whose key already exists in the mock target is quarantined.",
        source_fields=[field("external_id", "string"), field("name", "string")],
        target_fields=[field("customer_id", "string", unique=True), field("name", "string")],
        records=[
            {"external_id": existing, "name": "Conflicting record"},
            {"external_id": f"NEW{index:04d}", "name": "New record"},
        ],
        mappings=[
            mapping(["external_id"], "customer_id", copy_rule()),
            mapping(["name"], "name", copy_rule()),
        ],
        existing_target_keys=[existing],
        risks=[{"code": "TARGET_BUSINESS_KEY_CONFLICT", "severity": "high", "source_fields": ["external_id"]}],
    )


def scenario_semantic_blocker(case_id: str, index: int) -> dict[str, Any]:
    mode = (index - 1) % 4
    if mode == 0:
        return clarification_case(
            case_id=case_id,
            description="Two plausible source identifiers make the target business key ambiguous.",
            source_fields=[
                field("customer_code", "string", unique=True),
                field("legacy_code", "string", unique=True),
                field("name", "string"),
            ],
            target_fields=[field("customer_id", "string", unique=True), field("name", "string")],
            records=[{"customer_code": f"NEW{index}", "legacy_code": f"OLD{index}", "name": "Ambiguous Person"}],
            question="Should customer_id use customer_code or legacy_code?",
            reason="Both source fields are unique identifiers and the schemas do not define which identity the target requires.",
            affected_fields=["customer_code", "legacy_code", "customer_id"],
            incompatible_fields=["customer_id"],
        )
    if mode == 1:
        return clarification_case(
        case_id=case_id,
        description="A required target tier has no source field or documented default.",
        source_fields=[field("customer_id", "string", unique=True), field("name", "string")],
        target_fields=[
            field("customer_id", "string", unique=True),
            field("name", "string"),
            field("account_tier", "string", allowed_values=["gold", "silver", "bronze"]),
        ],
        records=[{"customer_id": f"MIS{index}", "name": "Missing Tier"}],
        question="What source value or approved default should populate account_tier?",
        reason="The target requires account_tier, but the source has no matching field and no default was provided.",
        affected_fields=["account_tier"],
        missing_source_fields=["account_tier"],
        )
    if mode == 2:
        return clarification_case(
            case_id=case_id,
            description="The only plausible source field has an incompatible meaning and type.",
            source_fields=[
                field("customer_id", "string", unique=True),
                field("loyalty_label", "string"),
            ],
            target_fields=[
                field("customer_id", "string", unique=True),
                field("loyalty_points", "integer"),
            ],
            records=[
                {"customer_id": f"INC{index}", "loyalty_label": "preferred"}
            ],
            question="How should loyalty_label be converted into numeric loyalty_points?",
            reason="The schemas do not provide an approved conversion from a descriptive label to a numeric score.",
            affected_fields=["loyalty_label", "loyalty_points"],
            incompatible_fields=["loyalty_points"],
        )
    return clarification_case(
        case_id=case_id,
        description="A required derived target value needs an undocumented business formula.",
        source_fields=[
            field("customer_id", "string", unique=True),
            field("annual_spend", "decimal"),
            field("late_payments", "integer"),
        ],
        target_fields=[
            field("customer_id", "string", unique=True),
            field("risk_score", "integer"),
        ],
        records=[
            {
                "customer_id": f"DER{index}",
                "annual_spend": 85000.0,
                "late_payments": 2,
            }
        ],
        question="What approved formula should calculate risk_score?",
        reason="The target requires a derived score, but no supported business formula was provided.",
        affected_fields=["annual_spend", "late_payments", "risk_score"],
        missing_source_fields=["risk_score"],
    )


SCENARIOS: list[tuple[str, str, Callable[[str, int], dict[str, Any]]]] = [
    ("easy", "exact_copy", scenario_exact_copy),
    ("easy", "renamed_copy", scenario_renamed_copy),
    ("easy", "trim_text", scenario_trim_text),
    ("easy", "parse_integer_valid", scenario_integer_valid),
    ("easy", "parse_decimal_valid", scenario_decimal_valid),
    ("easy", "parse_boolean_valid", scenario_boolean_valid),
    ("medium", "parse_date_valid", scenario_date_valid),
    ("medium", "concat_names", scenario_concat_names),
    ("medium", "lookup_status", scenario_lookup_status),
    ("medium", "default_if_missing", scenario_default_missing),
    ("medium", "mixed_transformations", scenario_mixed),
    ("medium", "nullable_values", scenario_nullable),
    ("medium", "extra_source_fields", scenario_extra_source),
    ("hard", "invalid_numeric_quarantine", scenario_invalid_numeric),
    ("hard", "invalid_boolean_quarantine", scenario_invalid_boolean),
    ("hard", "invalid_date_quarantine", scenario_invalid_date),
    ("hard", "target_constraint_violation", scenario_target_constraint),
    ("hard", "duplicate_business_key", scenario_duplicate_key),
    ("hard", "target_business_key_conflict", scenario_target_conflict),
    ("hard", "semantic_blocker", scenario_semantic_blocker),
]


def generate_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for _, category, builder in SCENARIOS:
        for index in range(50):
            case_id = f"{category}_{index + 1:03d}"
            case = builder(case_id, index + 1)
            if case["category"] != category:
                raise ValueError(f"Category mismatch for {case_id}")
            cases.append(case)
    return cases


def validate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    case_ids = [case["case_id"] for case in cases]
    if len(cases) != 1000:
        raise ValueError(f"Expected 1,000 cases, generated {len(cases)}")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Case IDs are not unique")

    difficulty_counts = Counter(case["difficulty"] for case in cases)
    category_counts = Counter(case["category"] for case in cases)
    status_counts = Counter(
        case["expected"]["agent"]["proposal_status"] for case in cases
    )
    executable = [case for case in cases if case["expected"]["dry_run"]]
    accepted_records = sum(
        case["expected"]["dry_run"]["accepted_count"] for case in executable
    )
    rejected_records = sum(
        case["expected"]["dry_run"]["rejected_count"] for case in executable
    )
    observed_error_codes = Counter(
        code
        for case in executable
        for record in case["expected"]["dry_run"]["records"]
        for code in record["error_codes"]
    )
    rule_counts = Counter(
        rule["rule"]
        for case in cases
        for item in case["expected"]["agent"]["mappings"]
        for rule in item["rules"]
    )
    target_type_counts = Counter(
        field["type"]
        for case in cases
        for field in case["input"]["target_schema"]["fields"]
    )
    return {
        "dataset_version": DATASET_VERSION,
        "usage": "evaluation_only",
        "generation_seed": GENERATION_SEED,
        "review_status": "pending_human_review",
        "case_count": len(cases),
        "scenario_count": len(SCENARIOS),
        "cases_per_scenario": 50,
        "difficulty_counts": dict(sorted(difficulty_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "proposal_status_counts": dict(sorted(status_counts.items())),
        "executable_case_count": len(executable),
        "clarification_case_count": len(cases) - len(executable),
        "expected_record_counts": {
            "accepted": accepted_records,
            "rejected": rejected_records,
            "total": accepted_records + rejected_records,
        },
        "expected_error_code_counts": dict(sorted(observed_error_codes.items())),
        "expected_rule_counts": dict(sorted(rule_counts.items())),
        "target_data_type_counts": dict(sorted(target_type_counts.items())),
        "rule_list_version": RULE_LIST_VERSION,
        "schema_format_version": "1.0",
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    cases = generate_cases()
    manifest = validate_cases(cases)
    with DATASET_PATH.open("w", encoding="utf-8") as output:
        for case in cases:
            output.write(json.dumps(case, ensure_ascii=False, sort_keys=True))
            output.write("\n")
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
