from uuid import UUID, uuid4

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class AuditEvent(CreatedAtMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "migration_projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    resource_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    resource_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    event_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    request_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_audit_event_project_created",
            "project_id",
            "created_at",
        ),
    )