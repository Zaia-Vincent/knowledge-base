"""Abstract interface (port) for embedding generation."""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Port for generating text embeddings — implemented in the infrastructure layer."""

    @abstractmethod
    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, one per input text.
            Each vector has the same dimensionality (determined by the model).
        """
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the dimensionality of the embedding vectors produced by this provider."""
        ...
