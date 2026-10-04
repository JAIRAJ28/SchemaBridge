from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class SchemaSnapshot(CreatedAtMixin, Base):
    __tablename__ = "schema_snapshots"

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
    previous_schema_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "schema_snapshots.id",
            ondelete="SET NULL",
        ),
    )
    schema_role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    original_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    normalized_schema: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    schema_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "schema_role IN ('source', 'target')",
            name="valid_schema_role",
        ),
        CheckConstraint(
            "version > 0",
            name="positive_version",
        ),
        UniqueConstraint(
            "project_id",
            "schema_role",
            "version",
            name="uq_schema_snapshot_version",
        ),
        UniqueConstraint(
            "project_id",
            "schema_role",
            "schema_hash",
            name="uq_schema_snapshot_hash",
        ),
        Index(
            "ix_schema_snapshot_project_role",
            "project_id",
            "schema_role",
        ),
    )