"""Domain entity for chat request logging — tracks usage and cost."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ChatRequestLog:
    """Represents a logged chat completion request with cost tracking.

    Each request to any AI provider is logged with token usage,
    cost, timing, and status information for observability.
    """

    model: str
    provider: str  # e.g. "openrouter", "groq", "openai"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float | None = None  # Cost in USD
    duration_ms: int | None = None
    status: str = "success"  # "success" | "error"
    error_message: str | None = None
    feature: str = "chat"  # "chat" | "classification" | "extraction" | "pdf_processing"
    tools_called: list[str] | None = None  # Tool names invoked during request
    tool_call_count: int = 0  # Total number of tool invocations
    request_context: str | None = None  # Extra context (e.g. filename)
    id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
