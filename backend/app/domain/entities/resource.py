"""Domain entities for processed resources — classification and metadata extraction results."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ProcessingStatus(str, Enum):
    """Lifecycle states of a resource in the processing pipeline."""

    PENDING = "pending"
    EXTRACTING_TEXT = "extracting_text"
    CLASSIFYING = "classifying"
    EXTRACTING_METADATA = "extracting_metadata"
    DONE = "done"
    ERROR = "error"


@dataclass
class ClassificationSignal:
    """A single classification signal from one detection method."""

    method: str          # "file_pattern" | "synonym_match" | "llm_analysis"
    concept_id: str
    score: float         # 0.0 – 1.0
    details: str = ""    # human-readable explanation


@dataclass
class ClassificationResult:
    """Aggregated classification result with signals from multiple methods."""

    primary_concept_id: str
    confidence: float
    signals: list[ClassificationSignal] = field(default_factory=list)


@dataclass
class Resource:
    """Core domain entity: a resource that has been uploaded and processed.

    Tracks the full lifecycle from upload through text extraction,
    classification, and metadata extraction.

    A *Resource* represents the source file. Each resource produces one or more
    *Resource Objects* — the database records holding classification results
    and extracted metadata.

    Metadata is stored as a flat JSONB dict:
        {"document_date": {"value": "2024-08-14", "confidence": 1.0}, ...}
    """

    filename: str
    original_path: str
    file_size: int
    mime_type: str
    stored_path: str = ""
    id: str | None = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    # Link to the data source that produced this resource
    data_source_id: str | None = None
    # Classification results
    classification: ClassificationResult | None = None
    # Extracted metadata (JSONB)
    metadata: dict[str, Any] = field(default_factory=dict)
    extra_fields: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None
    extracted_text: str | None = None
    language: str | None = None
    processing_time_ms: int | None = None
    # Multi-document support
    origin_file_id: str | None = None  # Links sub-documents to the parent upload
    page_range: str | None = None  # e.g. "1-2", "3-3"
    # Timestamps
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None
    error_message: str | None = None

    def mark_error(self, message: str) -> None:
        """Transition to error state."""
        self.status = ProcessingStatus.ERROR
        self.error_message = message

    def mark_done(self) -> None:
        """Transition to completed state."""
        self.status = ProcessingStatus.DONE
        self.processed_at = datetime.now(timezone.utc)
