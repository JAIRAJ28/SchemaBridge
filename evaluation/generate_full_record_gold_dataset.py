"""Generate 1,000 full-record JSON migration evaluation cases."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.generate_gold_dataset import executable_case, field, mapping
from services.rule_list import RULE_LIST_VERSION


ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "gold_full_record_cases.jsonl"
MANIFEST_PATH = ROOT / "gold_full_record_manifest.json"
DATASET_VERSION = "2.0.0"
GENERATION_SEED = 20261005


def source_fields() -> list[dict[str, Any]]:
    return [
        field("customer_id", "string"),
        field("first_name", "string"),
        field("last_name", "string"),
        field("email", "string"),
        field("date_of_birth", "string"),
        field("is_active", "string"),
        field("annual_income", "string"),
        field("address", "object"),
        field("interests", "string"),
        field("phone", "string", required=False, nullable=True),
        field("country_code", "string", required=False, nullable=True),
    ]


def target_fields() -> list[dict[str, Any]]:
    return [
        field("id", "integer", unique=True),
        field("full_name", "string"),
        field("email_address", "string"),
        field("birth_date", "date", format="%Y-%m-%d"),
        field("active", "boolean"),
        field("annual_income", "decimal", precision=14, scale=2),
        field("city", "string"),
        field("postal_code", "string"),
        field("interests", "array", items_type="string"),
        field("phone_number", "string", required=False, nullable=True),
        field("country", "string"),
    ]


def full_mappings(
    *,
    date_format: str = "%d/%m/%Y",
    boolean_rule: dict[str, Any] | None = None,
    interests_delimiter: str = ",",
) -> list[dict[str, Any]]:
    return [
        mapping(["customer_id"], "id", {"rule": "parse_integer"}),
        mapping(
            ["first_name", "last_name"],
            "full_name",
            {"rule": "concat", "separator": " "},
        ),
        mapping(
            ["email"],
            "email_address",
            {"rule": "trim"},
            {"rule": "lowercase"},
        ),
        mapping(
            ["date_of_birth"],
            "birth_date",
            {
                "rule": "parse_date",
                "input_format": date_format,
                "output_format": "%Y-%m-%d",
            },
        ),
        mapping(
            ["is_active"],
            "active",
            boolean_rule or {"rule": "parse_boolean"},
        ),
        mapping(
            ["annual_income"],
            "annual_income",
            {"rule": "remove_characters", "characters": ","},
            {"rule": "parse_decimal"},
        ),
        mapping(
            ["address"],
            "city",
            {"rule": "get_path", "path": ["city"]},
            {"rule": "trim"},
        ),
        mapping(
            ["address"],
            "postal_code",
            {"rule": "get_path", "path": ["postal_code"]},
            {"rule": "to_string"},
        ),
        mapping(
            ["interests"],
            "interests",
            {
                "rule": "split",
                "delimiter": interests_delimiter,
                "trim_items": True,
                "drop_empty": True,
            },
        ),
        mapping(
            ["phone"],
            "phone_number",
            {"rule": "empty_to_null"},
        ),
        mapping(
            ["country_code"],
            "country",
            {"rule": "default_if_missing", "value": "IN"},
            {"rule": "uppercase"},
        ),
    ]


def customer_record(
    index: int,
    row: int,
    *,
    date_value: str | None = None,
    active_value: str | None = None,
    income_value: str | None = None,
    interests_value: Any = None,
    address_value: Any = None,
    phone_value: Any = "",
    country_value: str | None = None,
) -> dict[str, Any]:
    number = 300_000 + index * 10 + row
    record: dict[str, Any] = {
        "customer_id": str(number),
        "first_name": "Jai" if row == 1 else "Asha",
        "last_name": f"Singh{index}" if row == 1 else f"Mehta{index}",
        "email": (
            f"  USER{number}@EXAMPLE.COM  "
            if row == 1
            else f" PERSON{number}@EXAMPLE.ORG "
        ),
        "date_of_birth": date_value or ("15/08/1995" if row == 1 else "02/11/1988"),
        "is_active": active_value or ("YES" if row == 1 else "NO"),
        "annual_income": income_value or (
            f"1,{250 + index:03d},000.50" if row == 1 else f"{500 + index},500.25"
        ),
        "address": address_value
        if address_value is not None
        else {
            "city": "  Pune " if row == 1 else " Bengaluru  ",
            "postal_code": 411001 if row == 1 else 560001,
        },
        "interests": interests_value
        if interests_value is not None
        else "AI, Patents, Data Engineering",
        "phone": phone_value,
    }
    if country_value is not None:
        record["country_code"] = country_value
    return record


SCENARIOS: list[tuple[str, str, str]] = [
    ("easy", "full_customer_clean", "clean"),
    ("easy", "full_customer_email_name", "email_name"),
    ("easy", "full_customer_id_postal", "id_postal"),
    ("easy", "full_customer_date_boolean", "date_boolean"),
    ("easy", "full_customer_income_phone", "income_phone"),
    ("medium", "nested_address_normalization", "nested_address"),
    ("medium", "thousands_income_normalization", "comma_income"),
    ("medium", "csv_interests_array", "csv_interests"),
    ("medium", "optional_phone_to_null", "optional_phone"),
    ("medium", "custom_boolean_values", "custom_boolean"),
    ("medium", "alternate_date_format", "alternate_date"),
    ("medium", "pipe_interests_array", "pipe_interests"),
    ("hard", "invalid_customer_id", "invalid_id"),
    ("hard", "invalid_birth_date", "invalid_date"),
    ("hard", "invalid_active_value", "invalid_boolean"),
    ("hard", "invalid_income_value", "invalid_income"),
    ("hard", "missing_nested_city", "missing_path"),
    ("hard", "invalid_nested_address", "invalid_object"),
    ("hard", "invalid_interests_input", "invalid_interests"),
    ("hard", "full_record_key_conflict", "key_conflict"),
]


def build_case(
    *,
    case_id: str,
    difficulty: str,
    category: str,
    mode: str,
    index: int,
) -> dict[str, Any]:
    date_format = "%d/%m/%Y"
    boolean_rule: dict[str, Any] | None = None
    delimiter = ","
    first = customer_record(index, 1, country_value="in")
    second = customer_record(index, 2)
    existing_keys: list[Any] = []
    risks: list[dict[str, Any]] = []

    if mode == "clean" and index == 1:
        first = {
            "customer_id": "10025",
            "first_name": "Jai",
            "last_name": "Singh",
            "email": "  JAI.SINGH@EXAMPLE.COM  ",
            "date_of_birth": "15/08/1995",
            "is_active": "YES",
            "annual_income": "1,250,000.50",
            "address": {"city": "  Pune ", "postal_code": 411001},
            "interests": "AI, Patents, Data Engineering",
            "phone": "",
        }
    elif mode == "custom_boolean":
        first["is_active"], second["is_active"] = "Y", "N"
        boolean_rule = {
            "rule": "parse_boolean",
            "true_values": ["Y"],
            "false_values": ["N"],
            "case_sensitive": False,
        }
    elif mode == "alternate_date":
        first["date_of_birth"], second["date_of_birth"] = "08-15-1995", "11-02-1988"
        date_format = "%m-%d-%Y"
    elif mode == "pipe_interests":
        first["interests"] = "AI | Patents | Data Engineering"
        second["interests"] = "Security | Cloud | Databases"
        delimiter = "|"
    elif mode == "optional_phone":
        first["phone"], second["phone"] = "   ", "+91-9999999999"
    elif mode == "nested_address":
        first["address"] = {"city": " Mumbai ", "postal_code": 400001, "state": "MH"}
        second["address"] = {"city": " Chennai ", "postal_code": 600001, "state": "TN"}
    elif mode == "comma_income":
        first["annual_income"], second["annual_income"] = "9,999,999.99", "75,000.00"
    elif mode == "csv_interests":
        first["interests"] = "AI, Patents, , Data Engineering"
        second["interests"] = "Cloud,Security,Databases"
    elif mode == "income_phone":
        first["phone"], second["phone"] = "", "+91-8888888888"
    elif mode == "invalid_id":
        second["customer_id"] = "ID-INVALID"
        risks = [{"code": "INVALID_ID", "severity": "high", "source_fields": ["customer_id"]}]
    elif mode == "invalid_date":
        second["date_of_birth"] = "31/02/1995"
        risks = [{"code": "INVALID_DATE", "severity": "high", "source_fields": ["date_of_birth"]}]
    elif mode == "invalid_boolean":
        second["is_active"] = "SOMETIMES"
        risks = [{"code": "INVALID_BOOLEAN", "severity": "high", "source_fields": ["is_active"]}]
    elif mode == "invalid_income":
        second["annual_income"] = "one million"
        risks = [{"code": "INVALID_INCOME", "severity": "high", "source_fields": ["annual_income"]}]
    elif mode == "missing_path":
        second["address"] = {"postal_code": 560001}
        risks = [{"code": "MISSING_NESTED_PATH", "severity": "high", "source_fields": ["address"]}]
    elif mode == "invalid_object":
        second["address"] = "Bengaluru 560001"
        risks = [{"code": "INVALID_NESTED_OBJECT", "severity": "high", "source_fields": ["address"]}]
    elif mode == "invalid_interests":
        second["interests"] = ["AI", "Data"]
        risks = [{"code": "INVALID_LIST_INPUT", "severity": "high", "source_fields": ["interests"]}]
    elif mode == "key_conflict":
        if index % 2:
            second["customer_id"] = first["customer_id"]
            risks = [{"code": "DUPLICATE_BUSINESS_KEY", "severity": "high", "source_fields": ["customer_id"]}]
        else:
            existing_keys = [int(second["customer_id"])]
            risks = [{"code": "TARGET_BUSINESS_KEY_CONFLICT", "severity": "high", "source_fields": ["customer_id"]}]

    result = executable_case(
        case_id=case_id,
        difficulty=difficulty,
        category=category,
        description=(
            "Convert a complete customer JSON record with deterministic rules; "
            f"scenario: {category}."
        ),
        source_fields=source_fields(),
        target_fields=target_fields(),
        records=[first, second],
        mappings=full_mappings(
            date_format=date_format,
            boolean_rule=boolean_rule,
            interests_delimiter=delimiter,
        ),
        existing_target_keys=existing_keys,
        risks=risks,
        business_key="id",
    )
    result["dataset_version"] = DATASET_VERSION
    result["suite"] = "full_record_json"
    return result


def generate_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for difficulty, category, mode in SCENARIOS:
        for index in range(1, 51):
            cases.append(
                build_case(
                    case_id=f"{category}_{index:03d}",
                    difficulty=difficulty,
                    category=category,
                    mode=mode,
                    index=index,
                )
            )
    return cases


def validate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    if len(cases) != 1000:
        raise ValueError(f"Expected 1,000 cases, generated {len(cases)}")
    if len({case["case_id"] for case in cases}) != 1000:
        raise ValueError("Case IDs must be unique")

    categories = Counter(case["category"] for case in cases)
    difficulties = Counter(case["difficulty"] for case in cases)
    rules = Counter(
        rule["rule"]
        for case in cases
        for item in case["expected"]["agent"]["mappings"]
        for rule in item["rules"]
    )
    errors = Counter(
        code
        for case in cases
        for record in case["expected"]["dry_run"]["records"]
        for code in record["error_codes"]
    )
    accepted = sum(
        case["expected"]["dry_run"]["accepted_count"] for case in cases
    )
    rejected = sum(
        case["expected"]["dry_run"]["rejected_count"] for case in cases
    )
    return {
        "dataset_version": DATASET_VERSION,
        "suite": "full_record_json",
        "usage": "evaluation_only",
        "review_status": "pending_human_review",
        "generation_seed": GENERATION_SEED,
        "case_count": len(cases),
        "scenario_count": len(SCENARIOS),
        "cases_per_scenario": 50,
        "difficulty_counts": dict(sorted(difficulties.items())),
        "category_counts": dict(sorted(categories.items())),
        "expected_record_counts": {
            "accepted": accepted,
            "rejected": rejected,
            "total": accepted + rejected,
        },
        "expected_rule_counts": dict(sorted(rules.items())),
        "expected_error_code_counts": dict(sorted(errors.items())),
        "rule_list_version": RULE_LIST_VERSION,
        "schema_format_version": "1.0",
    }


def main() -> None:
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
