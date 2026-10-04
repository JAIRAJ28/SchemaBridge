from hashlib import sha256
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import DatasetStatus, ErrorCode, SchemaRole
from config.settings import get_settings
from contracts.schema import SchemaDefinition
from middleware.error_handler import ApplicationError
from repositories.history_db import create_audit_event
from repositories.dataset_db import (
    SourceRecordData,
    create_dataset_snapshot,
    create_source_records,
    get_dataset_snapshot_by_checksum,
    update_dataset_status,
)
from repositories.project_db import get_project_by_id
from repositories.schema_db import get_schema_snapshot_by_id
from services.json_format import canonical_json_bytes
from services.hash_tools import (
    calculate_bytes_hash,
    calculate_canonical_hash,
)
from services.json_check import parse_json_records
from storage.local_storage import LocalStorage


PARSER_VERSION = "1.0"


def value_matches_type(value: object, data_type: str) -> bool:
    if value is None:
        return True
    if data_type == "string":
        return isinstance(value, str)
    if data_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if data_type == "decimal":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if data_type == "boolean":
        return isinstance(value, bool)
    if data_type in {"date", "datetime"}:
        return isinstance(value, str)
    return False


def record_matches_schema(record: dict, schema: SchemaDefinition) -> bool:
    for field in schema.fields:
        if field.name not in record:
            if field.required:
                return False
            continue

        value = record[field.name]
        if value is None:
            if not field.nullable:
                return False
            continue
        if not value_matches_type(value, field.type.value):
            return False
        if (
            field.max_length is not None
            and isinstance(value, str)
            and len(value) > field.max_length
        ):
            return False
        if field.allowed_values is not None and value not in field.allowed_values:
            return False
    return True


async def ingest_dataset(
    session: AsyncSession,
    *,
    project_id: UUID,
    source_schema_snapshot_id: UUID,
    actor_id: str,
    request_id: str,
    content: bytes,
):
    project = await get_project_by_id(
        session,
        project_id=project_id,
        owner_id=actor_id,
    )
    if project is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Project was not found.",
            status_code=404,
        )

    try:
        records = parse_json_records(content)
    except ValueError as error:
        raise ApplicationError(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=str(error),
            status_code=422,
        ) from error

    original_checksum = calculate_bytes_hash(content)
    existing = await get_dataset_snapshot_by_checksum(
        session,
        project_id=project_id,
        original_checksum=original_checksum,
    )
    if existing is not None:
        return existing

    schema_snapshot = await get_schema_snapshot_by_id(
        session,
        project_id=project_id,
        schema_snapshot_id=source_schema_snapshot_id,
    )
    if (
        schema_snapshot is None
        or schema_snapshot.schema_role != SchemaRole.SOURCE.value
    ):
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Source schema snapshot was not found.",
            status_code=404,
        )

    schema = SchemaDefinition.model_validate(schema_snapshot.normalized_schema)
    object_key = await LocalStorage(get_settings().storage_root).save(
        object_key=f"{original_checksum}.json",
        content=content,
    )
    dataset = await create_dataset_snapshot(
        session,
        project_id=project_id,
        source_schema_snapshot_id=source_schema_snapshot_id,
        original_object_key=object_key,
        original_checksum=original_checksum,
        parser_version=PARSER_VERSION,
        upload_size_bytes=len(content),
        created_by=actor_id,
    )

    source_records: list[SourceRecordData] = []
    for row_ordinal, original_record in enumerate(records):
        canonical_record = original_record
        record_hash = calculate_canonical_hash(canonical_record)
        stable_id = sha256(
            f"{original_checksum}:{row_ordinal}:{record_hash}".encode("utf-8")
        ).hexdigest()
        source_records.append(
            {
                "source_record_id": stable_id,
                "row_ordinal": row_ordinal,
                "original_record": original_record,
                "canonical_record": canonical_record,
                "record_hash": record_hash,
                "schema_valid": record_matches_schema(canonical_record, schema),
            }
        )

    await create_source_records(
        session,
        dataset_id=dataset.id,
        records=source_records,
    )
    await update_dataset_status(
        session,
        dataset=dataset,
        status=DatasetStatus.READY,
        record_count=len(source_records),
        canonical_hash=calculate_bytes_hash(canonical_json_bytes(records)),
    )
    await create_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        event_type="dataset.ingested",
        resource_type="dataset_snapshot",
        resource_id=dataset.id,
        request_id=request_id,
        event_metadata={
            "version": dataset.version,
            "record_count": len(source_records),
            "canonical_hash": dataset.canonical_hash,
        },
    )
    await session.commit()
    await session.refresh(dataset)
    return dataset
