"""Embedding service — orchestrates text chunking, embedding generation, and storage.

This is an application service that coordinates:
1. Splitting resource text into chunks
2. Generating embeddings via the EmbeddingProvider
3. Storing chunks + embeddings via the ChunkRepository
"""

import logging
import time

from app.application.interfaces.embedding_provider import EmbeddingProvider
from app.application.interfaces.chunk_repository import ChunkRepository
from app.domain.entities.resource import Resource
from app.domain.entities.resource_chunk import ResourceChunk

logger = logging.getLogger(__name__)

# ── Chunking constants ──────────────────────────────────────────────
_DEFAULT_CHUNK_SIZE = 1200  # ~300 tokens (rough 4:1 char-to-token ratio)
_DEFAULT_CHUNK_OVERLAP = 200  # Overlap for context continuity
_MAX_BATCH_SIZE = 50  # Max texts per embedding API call


class EmbeddingService:
    """Application service for generating and storing document embeddings.

    Handles the full flow: chunk text → generate embeddings → store chunks.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        chunk_repository: ChunkRepository,
        *,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = _DEFAULT_CHUNK_OVERLAP,
    ):
        self._embedding_provider = embedding_provider
        self._chunk_repo = chunk_repository
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def embed_resource(self, resource: Resource) -> int:
        """Generate and store embeddings for a processed resource.

        Creates chunks from extracted_text and summary, generates embeddings
        in batches, and persists them.

        Returns:
            Number of chunks created.
        """
        if not resource.id:
            logger.warning("Cannot embed resource without an ID")
            return 0

        start = time.monotonic()

        # Delete existing chunks (idempotent for reprocessing)
        await self._chunk_repo.delete_by_resource(resource.id)

        # Build chunks from available text
        chunks: list[ResourceChunk] = []

        # Chunk the extracted text
        if resource.extracted_text and resource.extracted_text.strip():
            text_parts = self._split_text(resource.extracted_text)
            for i, part in enumerate(text_parts):
                chunks.append(
                    ResourceChunk(
                        resource_id=resource.id,
                        chunk_index=i,
                        chunk_type="text",
                        content=part,
                    )
                )

        # Add summary as a single chunk (if present)
        if resource.summary and resource.summary.strip():
            chunks.append(
                ResourceChunk(
                    resource_id=resource.id,
                    chunk_index=0,
                    chunk_type="summary",
                    content=resource.summary,
                )
            )

        if not chunks:
            logger.info("No embeddable text for resource %s", resource.id)
            return 0

        # Generate embeddings in batches
        all_texts = [c.content for c in chunks]
        all_embeddings: list[list[float]] = []

        for batch_start in range(0, len(all_texts), _MAX_BATCH_SIZE):
            batch = all_texts[batch_start : batch_start + _MAX_BATCH_SIZE]
            batch_embeddings = await self._embedding_provider.generate_embeddings(batch)
            all_embeddings.extend(batch_embeddings)

        # Attach embeddings to chunks
        for chunk, embedding in zip(chunks, all_embeddings, strict=True):
            chunk.embedding = embedding

        # Persist
        await self._chunk_repo.store_chunks(chunks)

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Embedded resource %s: %d chunks in %dms",
            resource.id,
            len(chunks),
            duration_ms,
        )
        return len(chunks)

    def _split_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks using a recursive character strategy.

        Splits on paragraph breaks first, then sentences, then words.
        """
        text = text.strip()
        if not text:
            return []

        if len(text) <= self._chunk_size:
            return [text]

        chunks: list[str] = []
        # Try splitting on double newlines (paragraphs)
        separators = ["\n\n", "\n", ". ", " "]

        self._recursive_split(text, separators, chunks)
        return chunks

    def _recursive_split(
        self, text: str, separators: list[str], chunks: list[str]
    ) -> None:
        """Recursively split text using the separator hierarchy."""
        if len(text) <= self._chunk_size:
            if text.strip():
                chunks.append(text.strip())
            return

        # Find the best separator that produces reasonable splits
        best_sep = separators[-1]  # fallback to space
        for sep in separators:
            if sep in text:
                best_sep = sep
                break

        parts = text.split(best_sep)
        current_chunk = ""

        for part in parts:
            candidate = f"{current_chunk}{best_sep}{part}" if current_chunk else part

            if len(candidate) > self._chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Overlap: keep the tail of the previous chunk
                overlap_text = current_chunk[-self._chunk_overlap :] if self._chunk_overlap else ""
                current_chunk = f"{overlap_text}{best_sep}{part}" if overlap_text else part
            else:
                current_chunk = candidate

        if current_chunk.strip():
            chunks.append(current_chunk.strip())
