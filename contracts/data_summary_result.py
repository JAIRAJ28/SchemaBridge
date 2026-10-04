from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from contracts.page import StrictContract


class DatasetProfileResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    dataset_id: UUID
    profile_version: int
    status: str
    summary: dict
    field_statistics: dict
    duplicate_summary: dict
    profile_hash: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
