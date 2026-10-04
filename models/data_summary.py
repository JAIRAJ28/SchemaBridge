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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class DatasetProfile(CreatedAtMixin, Base):
    __tablename__ = "dataset_profiles"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    dataset_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "dataset_snapshots.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    profile_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    summary: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    field_statistics: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    duplicate_summary: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    profile_hash: Mapped[str | None] = mapped_column(
        String(64),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    __table_args__ = (
        CheckConstraint(
            "profile_version > 0",
            name="positive_profile_version",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="valid_status",
        ),
        UniqueConstraint(
            "dataset_id",
            "profile_version",
            name="uq_dataset_profile_version",
        ),
    )