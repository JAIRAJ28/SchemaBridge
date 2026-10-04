from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class MigrationRun(CreatedAtMixin, Base):
    __tablename__ = "migration_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    approval_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("approvals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dry_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("dry_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_plan_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    target_revision_before: Mapped[int] = mapped_column(Integer, nullable=False)
    target_revision_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reconciliation: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'reconciliation_failed', "
            "'rolled_back', 'rollback_conflict', 'failed')",
            name="valid_status",
        ),
        CheckConstraint(
            "source_count >= 0 AND accepted_count >= 0 AND "
            "rejected_count >= 0 AND inserted_count >= 0",
            name="nonnegative_counts",
        ),
        CheckConstraint(
            "source_count = accepted_count + rejected_count",
            name="balanced_counts",
        ),
        CheckConstraint(
            "target_revision_before >= 0 AND target_revision_after >= 0",
            name="nonnegative_target_revisions",
        ),
        UniqueConstraint("approval_id", name="uq_migration_run_approval"),
        Index("ix_migration_run_project_status", "project_id", "status"),
    )


class WriteLedger(CreatedAtMixin, Base):
    __tablename__ = "write_ledger"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    migration_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_record_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("source_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_record_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("target_records.id", ondelete="SET NULL"),
    )
    business_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint(
            "migration_run_id",
            "source_record_id",
            name="uq_write_ledger_source",
        ),
        UniqueConstraint(
            "migration_run_id",
            "business_key_hash",
            name="uq_write_ledger_business_key",
        ),
        Index("ix_write_ledger_run", "migration_run_id"),
    )


class MigrationAttempt(CreatedAtMixin, Base):
    __tablename__ = "migration_attempts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    migration_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('execute', 'retry', 'reconcile', 'rollback')",
            name="valid_action",
        ),
        CheckConstraint(
            "status IN ('succeeded', 'failed')",
            name="valid_status",
        ),
        Index("ix_migration_attempt_run", "migration_run_id", "created_at"),
    )
