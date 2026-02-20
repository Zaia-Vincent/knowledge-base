"""Pydantic schemas for processed resources API responses."""

from typing import Any

from pydantic import BaseModel


class ClassificationSignalSchema(BaseModel):
    method: str
    concept_id: str
    score: float
    details: str


class ClassificationResultSchema(BaseModel):
    primary_concept_id: str
    confidence: float
    signals: list[ClassificationSignalSchema]


class MetadataFieldSchema(BaseModel):
    """A single extracted metadata field stored in the JSONB metadata column."""
    value: Any = None
    confidence: float = 0.0
    raw_text: str | None = None
    source_quote: str | None = None


class ExtraFieldSchema(BaseModel):
    """A field discovered by the LLM that is not in the extraction template."""
    field_name: str
    value: Any = None
    confidence: float = 0.0
    source_quote: str | None = None


class ResourceSummarySchema(BaseModel):
    """Lightweight resource representation for list views."""
    id: str
    filename: str
    display_name: str | None = None
    original_path: str
    file_size: int
    mime_type: str
    status: str
    data_source_id: str | None = None
    data_source_name: str | None = None
    classification_concept_id: str | None = None
    classification_confidence: float | None = None
    concept_label: str | None = None
    origin_file_id: str | None = None
    page_range: str | None = None
    stored_path: str | None = None
    uploaded_at: str
    processed_at: str | None = None
    error_message: str | None = None


class ResourceDetailSchema(BaseModel):
    """Full resource representation for detail view."""
    id: str
    filename: str
    original_path: str
    file_size: int
    mime_type: str
    status: str
    data_source_id: str | None = None
    data_source_name: str | None = None
    extracted_text_preview: str | None = None
    classification: ClassificationResultSchema | None = None
    metadata: dict[str, MetadataFieldSchema] = {}
    extra_fields: list[ExtraFieldSchema] = []
    summary: str | None = None
    language: str | None = None
    processing_time_ms: int | None = None
    stored_path: str | None = None
    uploaded_at: str
    processed_at: str | None = None
    error_message: str | None = None


class ResourceUploadResultSchema(BaseModel):
    """Response after uploading resource(s)."""
    resources: list[ResourceSummarySchema]
    total_count: int
    message: str
