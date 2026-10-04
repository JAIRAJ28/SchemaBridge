"""add dry run tables

Revision ID: 8f31c2d70a44
Revises: 264912339a6c
Create Date: 2026-10-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8f31c2d70a44"
down_revision: Union[str, Sequence[str], None] = "264912339a6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "target_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("business_key", postgresql.JSONB(), nullable=False),
        sa.Column("business_key_hash", sa.String(length=64), nullable=False),
        sa.Column("record_data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["migration_projects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "business_key_hash",
            name="uq_target_record_business_key",
        ),
    )
    op.create_table(
        "dry_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="completed",
            nullable=False,
        ),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("transformed_count", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("result_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_count = accepted_count + rejected_count",
            name="ck_dry_runs_balanced_counts",
        ),
        sa.CheckConstraint(
            "source_count >= 0 AND transformed_count >= 0 "
            "AND accepted_count >= 0 AND rejected_count >= 0",
            name="ck_dry_runs_nonnegative_counts",
        ),
        sa.CheckConstraint(
            "status = 'completed'",
            name="ck_dry_runs_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["dataset_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["migration_plan_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["migration_projects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dry_run_project_plan",
        "dry_runs",
        ["project_id", "plan_id"],
    )
    op.create_table(
        "dry_run_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dry_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_record_id", sa.Uuid(), nullable=False),
        sa.Column("row_ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("transformed_record", postgresql.JSONB(), nullable=False),
        sa.Column("field_errors", postgresql.JSONB(), nullable=False),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "row_ordinal >= 0",
            name="ck_dry_run_records_nonnegative_row_ordinal",
        ),
        sa.CheckConstraint(
            "status IN ('accepted', 'rejected')",
            name="ck_dry_run_records_valid_status",
        ),
        sa.ForeignKeyConstraint(
            ["dry_run_id"],
            ["dry_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"],
            ["source_records.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dry_run_id",
            "source_record_id",
            name="uq_dry_run_source_record",
        ),
    )
    op.create_index(
        "ix_dry_run_record_status",
        "dry_run_records",
        ["dry_run_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dry_run_record_status",
        table_name="dry_run_records",
    )
    op.drop_table("dry_run_records")
    op.drop_index("ix_dry_run_project_plan", table_name="dry_runs")
    op.drop_table("dry_runs")
    op.drop_table("target_records")
