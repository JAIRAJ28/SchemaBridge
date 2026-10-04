from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from contracts.page import StrictContract


class ProjectCreate(StrictContract):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    target_namespace: str = Field(min_length=1, max_length=128)


class ProjectResponse(StrictContract):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    owner_id: str
    name: str
    description: str | None
    target_namespace: str
    status: str
    target_revision: int
    created_at: datetime
    updated_at: datetime
