from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    String,
    Integer,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class MigrationProject(CreatedAtMixin, Base):
    __tablename__ = "migration_projects"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    owner_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(1000),
    )
    target_namespace: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    target_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'archived')",
            name="valid_status",
        ),
        CheckConstraint(
            "target_revision >= 0",
            name="nonnegative_target_revision",
        ),
    )
