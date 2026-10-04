from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from config.constants import ErrorCode
from config.settings import get_settings
from middleware.error_handler import ApplicationError
from repositories.history_db import create_audit_event
from repositories.dataset_db import (
    count_source_records,
    get_dataset_snapshot_by_id,
    list_source_records,
)
from repositories.data_summary_db import (
    create_dataset_profile,
    update_dataset_profile,
)
from repositories.project_db import get_project_by_id
from services.hash_tools import calculate_canonical_hash


def observed_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "decimal"
    if isinstance(value, str):
        return "string"
    return "unsupported"


async def profile_dataset(
    session: AsyncSession,
    *,
    project_id: UUID,
    dataset_id: UUID,
    actor_id: str,
    request_id: str,
):
    project = await get_project_by_id(
        session,
        project_id=project_id,
        owner_id=actor_id,
    )
    dataset = await get_dataset_snapshot_by_id(
        session,
        project_id=project_id,
        dataset_id=dataset_id,
    )
    if project is None or dataset is None:
        raise ApplicationError(
            error_code=ErrorCode.NOT_FOUND,
            message="Dataset was not found.",
            status_code=404,
        )

    profile = await create_dataset_profile(session, dataset_id=dataset_id)
    await update_dataset_profile(
        session,
        profile=profile,
        status="running",
        started_at=datetime.now(timezone.utc),
    )

    records = await list_source_records(
        session,
        dataset_id=dataset_id,
        limit=get_settings().max_record_count,
    )
    total_records = await count_source_records(session, dataset_id=dataset_id)
    field_names = sorted(
        {
            field_name
            for source_record in records
            for field_name in source_record.canonical_record
        }
    )
    field_statistics: dict[str, dict] = {}

    for field_name in field_names:
        present_values = [
            record.canonical_record[field_name]
            for record in records
            if field_name in record.canonical_record
        ]
        non_null_values = [value for value in present_values if value is not None]
        text_lengths = [
            len(value) for value in non_null_values if isinstance(value, str)
        ]
        field_statistics[field_name] = {
            "missing_count": total_records - len(present_values),
            "null_count": sum(value is None for value in present_values),
            "observed_types": dict(
                Counter(observed_type(value) for value in present_values)
            ),
            "distinct_count": len({repr(value) for value in non_null_values}),
            "minimum_length": min(text_lengths) if text_lengths else None,
            "maximum_length": max(text_lengths) if text_lengths else None,
        }

    record_hash_counts = Counter(record.record_hash for record in records)
    duplicate_groups = {
        record_hash: count
        for record_hash, count in record_hash_counts.items()
        if count > 1
    }
    summary = {
        "record_count": total_records,
        "field_count": len(field_names),
        "schema_valid_count": sum(record.schema_valid for record in records),
        "schema_invalid_count": sum(not record.schema_valid for record in records),
    }
    duplicate_summary = {
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_record_count": sum(
            count - 1 for count in duplicate_groups.values()
        ),
    }
    profile_hash = calculate_canonical_hash(
        {
            "summary": summary,
            "field_statistics": field_statistics,
            "duplicate_summary": duplicate_summary,
        }
    )
    await update_dataset_profile(
        session,
        profile=profile,
        status="completed",
        summary=summary,
        field_statistics=field_statistics,
        duplicate_summary=duplicate_summary,
        profile_hash=profile_hash,
        completed_at=datetime.now(timezone.utc),
    )
    await create_audit_event(
        session,
        project_id=project_id,
        actor_id=actor_id,
        event_type="dataset.profiled",
        resource_type="dataset_profile",
        resource_id=profile.id,
        request_id=request_id,
        event_metadata={
            "dataset_id": str(dataset_id),
            "profile_version": profile.profile_version,
            "profile_hash": profile_hash,
        },
    )
    await session.commit()
    await session.refresh(profile)
    return profile
