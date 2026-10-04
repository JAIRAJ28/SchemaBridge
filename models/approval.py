from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class Approval(CreatedAtMixin, Base):
    __tablename__ = "approvals"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("migration_projects.id", ondelete="CASCADE"),
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
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_schema_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("schema_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_schema_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("schema_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    bundle_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    bundle_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    target_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_list_version: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    decided_by: Mapped[str] = mapped_column(String(128), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1000))
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name="valid_decision",
        ),
        CheckConstraint(
            "target_revision >= 0",
            name="nonnegative_target_revision",
        ),
        UniqueConstraint("dry_run_id", name="uq_approval_dry_run"),
        UniqueConstraint(
            "project_id",
            "bundle_fingerprint",
            name="uq_approval_bundle_fingerprint",
        ),
    )
