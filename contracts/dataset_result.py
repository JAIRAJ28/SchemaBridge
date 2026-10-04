from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from contracts.page import StrictContract


class DatasetResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    source_schema_snapshot_id: UUID
    version: int
    original_checksum: str
    canonical_hash: str | None
    parser_version: str
    record_count: int
    upload_size_bytes: int
    status: str
    created_by: str
    created_at: datetime
