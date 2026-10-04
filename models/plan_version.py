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


class MigrationPlanVersion(CreatedAtMixin, Base):
    __tablename__ = "migration_plan_versions"

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

    previous_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "migration_plan_versions.id",
            ondelete="SET NULL",
        ),
    )

    source_schema_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "schema_snapshots.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    target_schema_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "schema_snapshots.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    dataset_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "dataset_snapshots.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(1000),
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    plan_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    plan_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    rule_list_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    created_by: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "version > 0",
            name="positive_version",
        ),
        CheckConstraint(
            "status IN ('draft', 'valid', 'invalid')",
            name="valid_status",
        ),
        UniqueConstraint(
            "project_id",
            "version",
            name="uq_migration_plan_version",
        ),
        UniqueConstraint(
            "project_id",
            "plan_hash",
            name="uq_migration_plan_hash",
        ),
        Index(
            "ix_migration_plan_project_status",
            "project_id",
            "status",
        ),
    )