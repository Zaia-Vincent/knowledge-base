"""Pydantic schemas for query API requests and responses."""

from pydantic import BaseModel, Field
from typing import Any


# ── Request Schemas ──────────────────────────────────────────────────


class QueryRequest(BaseModel):
    """Request body for a natural-language query."""

    question: str = Field(..., min_length=1, description="Natural-language question in any language")
    max_results: int = Field(default=20, ge=1, le=100, description="Maximum number of results")


# ── Response Schemas ─────────────────────────────────────────────────


class MetadataFilterSchema(BaseModel):
    """A resolved metadata filter."""

    field_name: str
    value: str
    operator: str = "contains"


class QueryIntentSchema(BaseModel):
    """The LLM-resolved search intent."""

    original_question: str
    resolved_language: str
    concept_ids: list[str] = []
    concept_labels: list[str] = []
    metadata_filters: list[MetadataFilterSchema] = []
    keywords: list[str] = []
    text_query: str | None = None
    reasoning: str = ""


class QueryMatchSchema(BaseModel):
    """A single matching file in query results."""

    file_id: str
    filename: str
    concept_id: str | None = None
    concept_label: str | None = None
    confidence: float = 0.0
    summary: str | None = None
    metadata: dict[str, Any] = {}
    relevance_score: float = 0.0


class QueryResultSchema(BaseModel):
    """Full query result with resolved intent and matching files."""

    intent: QueryIntentSchema
    matches: list[QueryMatchSchema] = []
    total_matches: int = 0
