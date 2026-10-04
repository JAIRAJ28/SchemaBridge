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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class AgentRun(CreatedAtMixin, Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("migration_projects.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    source_schema_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("schema_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    target_schema_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("schema_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    plan_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("migration_plan_versions.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="running", server_default="running"
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_list_version: Mapped[str] = mapped_column(String(32), nullable=False)
    revision_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    proposal: Mapped[dict | None] = mapped_column(JSONB)
    validation: Mapped[dict | None] = mapped_column(JSONB)
    preview: Mapped[dict | None] = mapped_column(JSONB)
    target_conflicts: Mapped[dict | None] = mapped_column(JSONB)
    tool_evidence: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    transcript_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    failure_reason: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'needs_clarification', "
            "'ready_for_review', 'invalid', 'failed')",
            name="valid_status",
        ),
        CheckConstraint("revision_count >= 0", name="nonnegative_revision_count"),
        Index("ix_agent_run_project_status", "project_id", "status"),
    )


class AgentQuestion(CreatedAtMixin, Base):
    __tablename__ = "agent_questions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(String(1000), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    affected_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    blocking: Mapped[bool] = mapped_column(nullable=False, default=True)
    answer: Mapped[str | None] = mapped_column(String(2000))
    answered_by: Mapped[str | None] = mapped_column(String(128))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("revision_number > 0", name="positive_revision_number"),
        CheckConstraint("question_number > 0", name="positive_question_number"),
        UniqueConstraint(
            "agent_run_id",
            "revision_number",
            "question_number",
            name="uq_agent_question_number",
        ),
    )
