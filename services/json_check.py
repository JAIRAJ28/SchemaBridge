import json
from typing import Any

from config.settings import get_settings
from services.json_format import canonical_json_bytes


class DuplicateJSONKeyError(ValueError):
    pass


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_nonstandard_number(value: str) -> None:
    raise ValueError(f"Unsupported JSON number: {value}")


def parse_json_records(content: bytes) -> list[dict]:
    settings = get_settings()
    if len(content) > settings.max_upload_bytes:
        raise ValueError("Upload exceeds the maximum allowed size.")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Upload must use UTF-8 encoding.") from error

    try:
        value = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonstandard_number,
        )
    except json.JSONDecodeError as error:
        raise ValueError("Upload is not valid JSON.") from error

    if not isinstance(value, list):
        raise ValueError("The JSON root must be an array.")
    if not value:
        raise ValueError("Dataset must contain at least one record.")
    if len(value) > settings.max_record_count:
        raise ValueError("Dataset exceeds the maximum record count.")

    records: list[dict] = []
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise ValueError(f"Record {index} must be a JSON object.")
        if len(record) > settings.max_record_fields:
            raise ValueError(f"Record {index} contains too many fields.")
        if len(canonical_json_bytes(record)) > settings.max_record_bytes:
            raise ValueError(f"Record {index} exceeds the maximum record size.")

        for field_name, field_value in record.items():
            if isinstance(field_value, (dict, list)):
                raise ValueError(
                    f"Nested value found at record {index}, field '{field_name}'."
                )
            if (
                isinstance(field_value, str)
                and len(field_value) > settings.max_string_length
            ):
                raise ValueError(
                    f"String value is too long at record {index}, "
                    f"field '{field_name}'."
                )
        records.append(record)

    return records
