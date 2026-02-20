"""SQLAlchemy implementation of ChunkRepository — pgvector-powered vector search."""

import logging

from sqlalchemy import select, text, literal_column, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.chunk_repository import ChunkRepository, VectorSearchResult
from app.domain.entities.resource_chunk import ResourceChunk
from app.infrastructure.database.models.resource_chunk_models import ResourceChunkModel
from app.infrastructure.database.models.resource_models import ResourceModel

logger = logging.getLogger(__name__)


class PgChunkRepository(ChunkRepository):
    """Concrete chunk repository backed by PostgreSQL + pgvector."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def store_chunks(self, chunks: list[ResourceChunk]) -> None:
        """Persist a batch of resource chunks with their embeddings."""
        if not chunks:
            return

        models = [
            ResourceChunkModel(
                resource_id=chunk.resource_id,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                embedding=chunk.embedding if chunk.embedding else None,
            )
            for chunk in chunks
        ]

        self._session.add_all(models)
        await self._session.flush()
        logger.info("Stored %d chunks for resource %s", len(models), chunks[0].resource_id)

    async def delete_by_resource(self, resource_id: str) -> int:
        """Delete all chunks belonging to a resource."""
        result = await self._session.execute(
            delete(ResourceChunkModel).where(
                ResourceChunkModel.resource_id == resource_id
            )
        )
        count = result.rowcount
        if count > 0:
            logger.info("Deleted %d chunks for resource %s", count, resource_id)
        return count

    async def search_similar(
        self,
        query_embedding: list[float],
        *,
        concept_ids: list[str] | None = None,
        limit: int = 20,
    ) -> list[VectorSearchResult]:
        """Find chunks most similar to the query embedding using cosine similarity.

        Joins with the resources table to apply concept filters and return
        resource-level metadata alongside chunk-level similarity scores.
        """
        # Build raw SQL for pgvector cosine distance operator
        # 1 - (embedding <=> query_vector) gives cosine similarity (0-1)
        vector_str = f"[{','.join(str(v) for v in query_embedding)}]"

        # Use literal_column() so the alias is accessible in result rows.
        similarity_expr = literal_column(
            f"1 - (resource_chunks.embedding <=> '{vector_str}'::vector)"
        ).label("similarity")

        query = (
            select(
                ResourceChunkModel.id,
                ResourceChunkModel.resource_id,
                ResourceChunkModel.chunk_index,
                ResourceChunkModel.chunk_type,
                ResourceChunkModel.content,
                ResourceChunkModel.embedding,
                ResourceChunkModel.created_at,
                ResourceModel.filename,
                ResourceModel.concept_id,
                ResourceModel.concept_label,
                ResourceModel.summary.label("resource_summary"),
                ResourceModel.metadata_.label("resource_metadata"),
                similarity_expr,
            )
            .select_from(ResourceChunkModel)
            .join(ResourceModel, ResourceModel.id == ResourceChunkModel.resource_id)
            .where(ResourceModel.status == "done")
            .where(ResourceChunkModel.embedding.is_not(None))
        )

        if concept_ids:
            query = query.where(ResourceModel.concept_id.in_(concept_ids))

        query = query.order_by(text("similarity DESC")).limit(limit)

        result = await self._session.execute(query)
        rows = result.all()

        return [
            VectorSearchResult(
                chunk=ResourceChunk(
                    id=row.id,
                    resource_id=row.resource_id,
                    chunk_index=row.chunk_index,
                    chunk_type=row.chunk_type,
                    content=row.content,
                    embedding=[],  # Don't return full embedding in search results
                ),
                similarity=float(row.similarity),
                resource_id=row.resource_id,
                filename=row.filename,
                concept_id=row.concept_id,
                concept_label=row.concept_label,
                summary=row.resource_summary,
                metadata=row.resource_metadata or {},
            )
            for row in rows
        ]
