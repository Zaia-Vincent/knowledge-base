"""OpenRouter-based embedding provider — calls the /embeddings endpoint.

Uses the same httpx client pattern as the existing OpenRouterClient.
Default model: google/gemini-embedding-001 (3072 dimensions).
"""

import logging
from typing import Any

import httpx

from app.application.interfaces.embedding_provider import EmbeddingProvider

logger = logging.getLogger(__name__)

# nomic-embed-text models require a task prefix; Gemini models do not.
_NOMIC_DOCUMENT_PREFIX = "search_document: "
_NOMIC_QUERY_PREFIX = "search_query: "


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    """Infrastructure adapter — generates embeddings via OpenRouter /embeddings API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        app_name: str = "Knowledge Base",
        model: str = "google/gemini-embedding-001",
        model_dimensions: int = 768,
        http_client: httpx.AsyncClient | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._app_name = app_name
        self._model = model
        self._dimensions = model_dimensions
        self._http_client = http_client

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Title": self._app_name,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=120.0)

    @property
    def _is_nomic(self) -> bool:
        """Whether the configured model is a nomic model requiring task prefixes."""
        return "nomic" in self._model.lower()

    async def generate_embeddings(
        self,
        texts: list[str],
        *,
        _query_mode: bool = False,
    ) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        For nomic models, applies the appropriate task prefix automatically.
        """
        if not texts:
            return []

        # Apply nomic task prefix if needed
        if self._is_nomic:
            prefix = _NOMIC_QUERY_PREFIX if _query_mode else _NOMIC_DOCUMENT_PREFIX
            input_texts = [f"{prefix}{t}" for t in texts]
        else:
            input_texts = texts

        url = f"{self._base_url}/embeddings"
        payload: dict[str, Any] = {
            "model": self._model,
            "input": input_texts,
            "dimensions": self._dimensions,
        }

        client = await self._get_client()
        should_close = self._http_client is None

        try:
            response = await client.post(
                url, headers=self._get_headers(), json=payload
            )

            if response.status_code != 200:
                error_text = response.text[:500]
                logger.error(
                    "Embedding API error %d: %s", response.status_code, error_text
                )
                raise RuntimeError(
                    f"Embedding API returned {response.status_code}: {error_text}"
                )

            data = response.json()
            embeddings_data = data.get("data", [])

            # Sort by index to ensure correct ordering
            embeddings_data.sort(key=lambda x: x.get("index", 0))
            result = [item["embedding"] for item in embeddings_data]

            logger.info(
                "Generated %d embeddings (model=%s, dims=%d)",
                len(result),
                self._model,
                len(result[0]) if result else 0,
            )
            return result

        finally:
            if should_close:
                await client.aclose()

    async def generate_query_embedding(self, query: str) -> list[float]:
        """Generate a single embedding for a search query."""
        results = await self.generate_embeddings(
            [query], _query_mode=True
        )
        return results[0]
