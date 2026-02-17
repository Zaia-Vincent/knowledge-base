"""Centralized LLM usage logger — single entry point for tracking all LLM requests.

Persists every LLM request (chat, classification, extraction, PDF processing)
with token usage, cost, tool calls, and contextual metadata.
"""

import logging
import time
from typing import Any

from app.application.interfaces import ServiceRequestLogRepository
from app.domain.entities import ServiceRequestLog
from app.domain.entities.chat_message import TokenUsage

logger = logging.getLogger(__name__)


class LLMUsageLogger:
    """Tracks and persists LLM usage across all features.

    Usage:
        logger = LLMUsageLogger(log_repository)
        await logger.log_request(
            model="anthropic/claude-sonnet-4.5",
            provider="openrouter",
            feature="classification",
            usage=result.usage,
            duration_ms=42,
        )
    """

    def __init__(self, log_repository: ServiceRequestLogRepository):
        self._repo = log_repository

    async def log_request(
        self,
        *,
        model: str,
        provider: str,
        feature: str,
        usage: TokenUsage,
        duration_ms: int,
        status: str = "success",
        error_message: str | None = None,
        tools_called: list[str] | None = None,
        tool_call_count: int = 0,
        request_context: str | None = None,
    ) -> ServiceRequestLog:
        """Persist and log an LLM request.

        Args:
            model: Model identifier (e.g. "anthropic/claude-sonnet-4.5").
            provider: Provider name (e.g. "openrouter").
            feature: Which subsystem triggered the call
                     ("chat", "classification", "extraction", "pdf_processing").
            usage: Token usage from the completion result.
            duration_ms: Wall-clock time of the request in milliseconds.
            status: "success" or "error".
            error_message: Error details if status == "error".
            tools_called: List of unique tool names invoked.
            tool_call_count: Total number of tool invocations.
            request_context: Additional context (e.g. filename, concept_id).

        Returns:
            The persisted ServiceRequestLog entity.
        """
        entry = ServiceRequestLog(
            model=model,
            provider=provider,
            feature=feature,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cost=usage.cost,
            duration_ms=duration_ms,
            status=status,
            error_message=error_message,
            tools_called=tools_called,
            tool_call_count=tool_call_count,
            request_context=request_context,
        )

        saved = await self._repo.create(entry)

        # Console summary
        cost_str = f"${usage.cost:.6f}" if usage.cost else "n/a"
        tools_str = f" tools={tools_called}" if tools_called else ""
        ctx_str = f" ctx={request_context}" if request_context else ""

        logger.info(
            "LLM [%s] model=%s tokens=%d cost=%s %dms%s%s",
            feature,
            model,
            usage.total_tokens,
            cost_str,
            duration_ms,
            tools_str,
            ctx_str,
        )

        return saved

    async def log_error(
        self,
        *,
        model: str,
        provider: str,
        feature: str,
        duration_ms: int,
        error: Exception,
        request_context: str | None = None,
    ) -> ServiceRequestLog:
        """Convenience method for logging failed LLM requests."""
        return await self.log_request(
            model=model,
            provider=provider,
            feature=feature,
            usage=TokenUsage(),
            duration_ms=duration_ms,
            status="error",
            error_message=str(error),
            request_context=request_context,
        )
