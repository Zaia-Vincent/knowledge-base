"""Domain entity for resource chunks — text fragments with vector embeddings."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ResourceChunk:
    """A text chunk from a processed resource, suitable for vector search.

    Each resource can produce multiple chunks from its extracted text
    and summary. Each chunk stores both the original text and its
    embedding vector for semantic similarity search.
    """

    resource_id: str
    chunk_index: int
    chunk_type: str  # "text", "summary"
    content: str
    embedding: list[float] = field(default_factory=list)
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
