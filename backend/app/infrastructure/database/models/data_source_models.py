"""SQLAlchemy ORM models for data sources and processing jobs."""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.infrastructure.database.base import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class DataSourceModel(Base):
    """A registered data source from which documents are ingested."""

    __tablename__ = "data_sources"

    id = Column(String(36), primary_key=True, default=_generate_uuid)
    name = Column(String(255), nullable=False)
    source_type = Column(String(30), nullable=False, index=True)
    description = Column(Text, nullable=False, server_default="")
    config = Column(JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProcessingJobModel(Base):
    """A single unit of work in the background processing queue."""

    __tablename__ = "processing_jobs"

    id = Column(String(36), primary_key=True, default=_generate_uuid)
    data_source_id = Column(
        String(36),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_identifier = Column(String(1000), nullable=False)
    resource_type = Column(String(20), nullable=False)  # "file" | "url"
    status = Column(String(20), nullable=False, default="queued", index=True)
    progress_message = Column(Text, nullable=True)
    result_file_id = Column(String(36), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_jobs_status_created", "status", "created_at"),
    )
