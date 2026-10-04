from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict

from config.constants import SchemaRole
from contracts.page import StrictContract


class SchemaSnapshotResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    project_id: UUID
    previous_schema_id: UUID | None
    schema_role: SchemaRole
    version: int
    schema_hash: str
    normalized_schema: dict
    created_by: str
    created_at: datetime
