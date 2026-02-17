"""Domain entities for knowledge base queries — NL-to-ontology search."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetadataFilter:
    """A single metadata filter resolved from the user's question."""

    field_name: str
    value: str
    operator: str = "contains"  # "contains" | "equals" | "gte" | "lte"


@dataclass
class QueryIntent:
    """Structured search intent resolved from a natural-language question.

    Produced by the LLM from the user's question + ontology context.
    Contains everything needed to query the knowledge database.
    """

    original_question: str
    resolved_language: str = "en"
    concept_ids: list[str] = field(default_factory=list)
    concept_labels: list[str] = field(default_factory=list)
    metadata_filters: list[MetadataFilter] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    text_query: str | None = None
    reasoning: str = ""


@dataclass
class QueryMatch:
    """A single file matching the resolved query intent."""

    file_id: str
    filename: str
    concept_id: str | None = None
    concept_label: str | None = None
    confidence: float = 0.0
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0


@dataclass
class QueryResult:
    """Complete query result: the resolved intent + matching files."""

    intent: QueryIntent
    matches: list[QueryMatch] = field(default_factory=list)
    total_matches: int = 0
