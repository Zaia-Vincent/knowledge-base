"""Chat completion use case — orchestrates provider calls and request logging."""

import time
import logging
from collections.abc import AsyncIterator

from app.application.interfaces.chat_provider import ChatProvider
from app.application.interfaces.service_request_log_repository import (
    ServiceRequestLogRepository,
)
from app.application.services.llm_usage_logger import LLMUsageLogger
from app.domain.entities import (
    ChatMessage,
    ContentPart,
    ChatCompletionResult,
    ServiceRequestLog,
)
from app.domain.entities.chat_message import TokenUsage
from app.domain.exceptions import ChatProviderError
from app.application.schemas.chat import ChatCompletionRequest, ChatMessageSchema

logger = logging.getLogger(__name__)


class ChatCompletionService:
    """Application service — orchestrates chat completion with logging.

    This service is provider-agnostic: it receives a ChatProvider via
    dependency injection. New providers (Groq, OpenAI, etc.) can be
    swapped in without changing this service.
    """

    def __init__(
        self,
        provider: ChatProvider,
        log_repository: ServiceRequestLogRepository,
        usage_logger: LLMUsageLogger | None = None,
    ):
        self._provider = provider
        self._log_repository = log_repository
        self._usage_logger = usage_logger or LLMUsageLogger(log_repository)

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResult:
        """Execute a non-streaming chat completion.

        1. Converts schemas to domain entities
        2. Calls the provider
        3. Logs the request with usage and cost
        4. Returns the result
        """
        messages = self._to_domain_messages(request.messages)
        start = time.monotonic()

        try:
            result = await self._provider.complete(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            await self._usage_logger.log_request(
                model=result.model,
                provider=result.provider or self._provider.provider_name,
                feature="chat",
                usage=result.usage,
                duration_ms=duration_ms,
            )

            return result

        except ChatProviderError as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._usage_logger.log_error(
                model=request.model,
                provider=self._provider.provider_name,
                feature="chat",
                duration_ms=duration_ms,
                error=e,
            )
            logger.error("Chat completion error: %s", e)
            raise

    async def stream(
        self, request: ChatCompletionRequest
    ) -> AsyncIterator[str]:
        """Execute a streaming chat completion.

        Yields SSE data chunks from the provider and logs the request
        after the stream completes.
        """
        messages = self._to_domain_messages(request.messages)
        start = time.monotonic()

        total_content = ""
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        cost: float | None = None
        model_used = request.model
        error_occurred = False
        error_msg: str | None = None

        try:
            async for chunk in self._provider.stream(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                yield chunk

                # Try to extract usage from the final chunk
                self._try_extract_stream_usage(
                    chunk, locals()
                )

        except ChatProviderError as e:
            error_occurred = True
            error_msg = str(e)
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost=cost,
            )
            if error_occurred:
                await self._usage_logger.log_error(
                    model=model_used,
                    provider=self._provider.provider_name,
                    feature="chat",
                    duration_ms=duration_ms,
                    error=Exception(error_msg or "Unknown streaming error"),
                )
            else:
                await self._usage_logger.log_request(
                    model=model_used,
                    provider=self._provider.provider_name,
                    feature="chat",
                    usage=usage,
                    duration_ms=duration_ms,
                )

    @staticmethod
    def _to_domain_messages(
        schemas: list[ChatMessageSchema],
    ) -> list[ChatMessage]:
        """Convert Pydantic message schemas to domain entities."""
        messages: list[ChatMessage] = []
        for msg in schemas:
            if isinstance(msg.content, str):
                messages.append(ChatMessage(role=msg.role, content=msg.content))
            else:
                parts = [
                    ContentPart(
                        type=p.type,
                        text=p.text,
                        image_url=(
                            {"url": p.image_url.url, "detail": p.image_url.detail or "auto"}
                            if p.image_url
                            else None
                        ),
                    )
                    for p in msg.content
                ]
                messages.append(ChatMessage(role=msg.role, content=parts))
        return messages

    @staticmethod
    def _try_extract_stream_usage(chunk: str, context: dict) -> None:
        """Attempt to extract usage data from a streamed chunk.

        The final SSE chunk from OpenRouter may include usage statistics.
        This is a best-effort extraction — if the chunk doesn't contain
        usage data, we silently skip.
        """
        import json

        if not chunk.startswith("data: "):
            return
        try:
            data = json.loads(chunk[6:])
            if "usage" in data:
                usage = data["usage"]
                context["prompt_tokens"] = usage.get("prompt_tokens", 0)
                context["completion_tokens"] = usage.get("completion_tokens", 0)
                context["total_tokens"] = usage.get("total_tokens", 0)
                context["cost"] = usage.get("cost")
            if "model" in data:
                context["model_used"] = data["model"]
        except (json.JSONDecodeError, KeyError):
            pass

    async def get_logs(
        self, *, skip: int = 0, limit: int = 100
    ) -> list[ServiceRequestLog]:
        """Retrieve service request logs for monitoring."""
        return await self._log_repository.get_all(skip=skip, limit=limit)

