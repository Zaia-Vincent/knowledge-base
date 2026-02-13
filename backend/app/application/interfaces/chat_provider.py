"""Abstract chat provider interface — port for AI provider adapters.

This interface enables multi-provider support. Each AI provider
(OpenRouter, Groq, OpenAI, etc.) implements this interface.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.entities import ChatMessage, ChatCompletionResult


class ChatProvider(ABC):
    """Port — defines what the application layer needs from any chat provider."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique name identifying this provider (e.g. 'openrouter', 'groq')."""
        ...

    @abstractmethod
    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletionResult:
        """Send a non-streaming chat completion request.

        Args:
            messages: The conversation history.
            model: The model identifier (e.g. 'openai/gpt-4o-mini').
            temperature: Sampling temperature (0.0–2.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            A ChatCompletionResult with content, usage, and cost.

        Raises:
            ChatProviderError: If the provider returns an error.
        """
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Send a streaming chat completion request.

        Yields SSE-formatted data chunks. The final chunk may contain
        usage statistics.

        Args:
            messages: The conversation history.
            model: The model identifier.
            temperature: Sampling temperature (0.0–2.0).
            max_tokens: Maximum tokens in the response.

        Yields:
            SSE data strings (each line is 'data: {...}').

        Raises:
            ChatProviderError: If the provider returns an error.
        """
        ...
