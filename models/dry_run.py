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


class TargetRecord(CreatedAtMixin, Base):
    __tablename__ = "target_records"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    business_key: Mapped[object] = mapped_column(JSONB, nullable=False)
    business_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "business_key_hash",
            name="uq_target_record_business_key",
        ),
    )


class DryRun(CreatedAtMixin, Base):
    __tablename__ = "dry_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_plan_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed", server_default="completed"
    )
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    transformed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        CheckConstraint("status = 'completed'", name="valid_status"),
        CheckConstraint(
            "source_count >= 0 AND transformed_count >= 0 "
            "AND accepted_count >= 0 AND rejected_count >= 0",
            name="nonnegative_counts",
        ),
        CheckConstraint(
            "source_count = accepted_count + rejected_count",
            name="balanced_counts",
        ),
        Index("ix_dry_run_project_plan", "project_id", "plan_id"),
    )


class DryRunRecord(CreatedAtMixin, Base):
    __tablename__ = "dry_run_records"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dry_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("dry_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_record_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("source_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    row_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    transformed_record: Mapped[dict] = mapped_column(JSONB, nullable=False)
    field_errors: Mapped[list] = mapped_column(JSONB, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint("row_ordinal >= 0", name="nonnegative_row_ordinal"),
        CheckConstraint(
            "status IN ('accepted', 'rejected')",
            name="valid_status",
        ),
        UniqueConstraint(
            "dry_run_id",
            "source_record_id",
            name="uq_dry_run_source_record",
        ),
        Index("ix_dry_run_record_status", "dry_run_id", "status"),
    )
