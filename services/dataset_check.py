from dataclasses import dataclass
from uuid import UUID

from contracts.schema import SchemaDefinition
from contracts.transform_result import FieldProblem, RecordResult
from services.hash_tools import calculate_canonical_hash


@dataclass(frozen=True)
class RecordToCheck:
    source_record_id: UUID
    row_ordinal: int
    result: RecordResult


def business_key_hash(value: object) -> str:
    return calculate_canonical_hash(value)


def check_dataset_keys(
    *,
    records: list[RecordToCheck],
    target_schema: SchemaDefinition,
    existing_target_key_hashes: set[str],
) -> list[RecordToCheck]:
    business_key = target_schema.business_key
    if business_key is None:
        return records

    key_groups: dict[str, list[int]] = {}
    key_values: dict[int, object] = {}

    for index, item in enumerate(records):
        if business_key not in item.result.transformed_record:
            continue
        value = item.result.transformed_record[business_key]
        if value is None:
            continue
        key_hash = business_key_hash(value)
        key_groups.setdefault(key_hash, []).append(index)
        key_values[index] = value

    duplicate_indexes = {
        index
        for indexes in key_groups.values()
        if len(indexes) > 1
        for index in indexes
    }

    checked: list[RecordToCheck] = []
    for index, item in enumerate(records):
        problems = list(item.result.problems)
        value = key_values.get(index)

        if index in duplicate_indexes:
            problems.append(
                FieldProblem(
                    stage="dataset_check",
                    code="DUPLICATE_BUSINESS_KEY",
                    message=(
                        f"Business key '{business_key}' is duplicated "
                        "in the source dataset."
                    ),
                    target_field=business_key,
                    value=value,
                )
            )

        if (
            index in key_values
            and business_key_hash(value) in existing_target_key_hashes
        ):
            problems.append(
                FieldProblem(
                    stage="dataset_check",
                    code="TARGET_BUSINESS_KEY_CONFLICT",
                    message=(
                        f"Business key '{business_key}' already exists "
                        "in the mock target."
                    ),
                    target_field=business_key,
                    value=value,
                )
            )

        checked.append(
            RecordToCheck(
                source_record_id=item.source_record_id,
                row_ordinal=item.row_ordinal,
                result=RecordResult(
                    valid=not problems,
                    transformed_record=item.result.transformed_record,
                    problems=problems,
                ),
            )
        )

    return checked
