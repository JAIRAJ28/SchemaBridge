from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, CreatedAtMixin


class IdempotencyRecord(CreatedAtMixin, Base):
    __tablename__ = "idempotency_records"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )
    actor_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(64),
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(128),
    )
    response_status: Mapped[int | None] = mapped_column()
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "response_status IS NULL OR "
            "(response_status >= 100 AND response_status <= 599)",
            name="valid_response_status",
        ),
        UniqueConstraint(
            "actor_id",
            "scope",
            "idempotency_key",
            name="uq_idempotency_actor_scope_key",
        ),
    )