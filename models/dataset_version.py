from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class DatasetSnapshot(CreatedAtMixin, Base):
    __tablename__ = "dataset_snapshots"

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
    source_schema_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "schema_snapshots.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    original_object_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    original_checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    canonical_hash: Mapped[str | None] = mapped_column(
        String(64),
    )
    parser_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    record_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    upload_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploading",
        server_default="uploading",
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
            "record_count >= 0",
            name="nonnegative_record_count",
        ),
        CheckConstraint(
            "upload_size_bytes >= 0",
            name="nonnegative_upload_size",
        ),
        CheckConstraint(
            "status IN ('uploading', 'processing', 'ready', 'failed')",
            name="valid_status",
        ),
        UniqueConstraint(
            "project_id",
            "version",
            name="uq_dataset_snapshot_version",
        ),
    )