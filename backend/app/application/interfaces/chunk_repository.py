"""Abstract repository interface (port) for resource chunks and vector search."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.domain.entities.resource_chunk import ResourceChunk


@dataclass
class VectorSearchResult:
    """A single result from a vector similarity search."""

    chunk: ResourceChunk
    similarity: float  # 0.0 – 1.0 (cosine similarity)
    resource_id: str
    filename: str
    concept_id: str | None = None
    concept_label: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkRepository(ABC):
    """Port for resource chunk persistence and vector search."""

    @abstractmethod
    async def store_chunks(self, chunks: list[ResourceChunk]) -> None:
        """Persist a batch of resource chunks with their embeddings."""
        ...

    @abstractmethod
    async def delete_by_resource(self, resource_id: str) -> int:
        """Delete all chunks for a resource. Returns count of deleted rows."""
        ...

    @abstractmethod
    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        concept_ids: list[str] | None = None,
        limit: int = 20,
    ) -> list[VectorSearchResult]:
        """Find chunks most similar to the query embedding.

        Args:
            query_embedding: The query vector.
            concept_ids: Optional filter — only search within these concepts.
            limit: Maximum number of results.

        Returns:
            List of VectorSearchResult ordered by descending similarity.
        """
        ...
