from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class SourceRecord(CreatedAtMixin, Base):
    __tablename__ = "source_records"

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
    source_record_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    row_ordinal: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    original_record: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    canonical_record: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    record_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    schema_valid: Mapped[bool] = mapped_column(
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "row_ordinal >= 0",
            name="nonnegative_row_ordinal",
        ),
        UniqueConstraint(
            "dataset_id",
            "source_record_id",
            name="uq_source_record_identity",
        ),
        UniqueConstraint(
            "dataset_id",
            "row_ordinal",
            name="uq_source_record_ordinal",
        ),
    )