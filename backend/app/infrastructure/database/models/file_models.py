"""SQLAlchemy ORM model for processed files — single flat table with JSONB columns."""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.infrastructure.database.base import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class ProcessedFileModel(Base):
    """A file that has been uploaded and processed through the pipeline.

    All classification results, extracted metadata, and summary are stored
    inline using PostgreSQL JSONB columns — one row per file.
    """

    __tablename__ = "processed_files"

    # ── Identity ──────────────────────────────────────────────────────
    id = Column(String(36), primary_key=True, default=_generate_uuid)
    filename = Column(String(255), nullable=False, index=True)
    original_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    stored_path = Column(String(500), nullable=False)
    status = Column(String(30), nullable=False, default="pending", index=True)
    extracted_text = Column(Text, nullable=True)

    # ── Classification (flattened) ────────────────────────────────────
    concept_id = Column(String(100), nullable=True, index=True)
    concept_label = Column(String(200), nullable=True)
    classification_confidence = Column(Float, nullable=True)
    classification_signals = Column(JSONB, nullable=True)

    # ── Extracted metadata (JSONB) ────────────────────────────────────
    metadata_ = Column("metadata", JSONB, nullable=False, server_default="{}")
    extra_fields = Column(JSONB, nullable=False, server_default="[]")
    summary = Column(Text, nullable=True)
    language = Column(String(10), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)

    # ── Multi-document support ────────────────────────────────────────
    origin_file_id = Column(String(36), nullable=True, index=True)
    page_range = Column(String(20), nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────
    uploaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # ── Indexes ───────────────────────────────────────────────────────
    __table_args__ = (
        Index("idx_metadata_gin", metadata_, postgresql_using="gin"),
    )
