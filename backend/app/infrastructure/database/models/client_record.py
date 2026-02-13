"""SQLAlchemy ORM model for the ClientRecord entity."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ClientRecordModel(Base):
    """ORM model — maps to the 'client_records' table."""

    __tablename__ = "client_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_client_records_scope", "module_name", "entity_type"),
        Index("ix_client_records_parent", "parent_id"),
        Index("ix_client_records_user", "user_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<ClientRecordModel(id={self.id}, "
            f"module='{self.module_name}', type='{self.entity_type}')>"
        )
