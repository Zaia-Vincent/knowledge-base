"""Domain entities for chat messages — framework-independent, multimodal."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContentPart:
    """A single content part within a multimodal message.

    Supports text, image_url, and file types, following the OpenAI-compatible
    multimodal format used by OpenRouter and other providers.
    """

    type: str  # "text" | "image_url" | "file"
    text: str | None = None
    image_url: dict[str, str] | None = None  # {"url": "..."}
    file_data: dict[str, str] | None = None  # {"file_data": "data:...;base64,...", "filename": "..."}


@dataclass
class ToolCallFunction:
    """The function invocation details within a tool call."""

    name: str
    arguments: str  # JSON-encoded arguments string


@dataclass
class ToolCall:
    """A tool call requested by the LLM in its response."""

    id: str
    type: str  # "function"
    function: ToolCallFunction


@dataclass
class ChatMessage:
    """A single message in a chat conversation.

    Content can be a plain string (text-only) or a list of ContentPart
    objects for multimodal input (text + images).

    For tool responses, set role="tool", provide tool_call_id, and
    set content to the JSON result string.
    """

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | list[ContentPart] = ""
    tool_call_id: str | None = None  # Required when role == "tool"
    name: str | None = None  # Tool function name (for role == "tool")
    tool_calls: list[ToolCall] | None = None  # For assistant messages requesting tool calls


@dataclass
class TokenUsage:
    """Token usage statistics from a completion."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float | None = None  # Cost in USD, if available from provider


@dataclass
class ChatCompletionResult:
    """Result from a chat completion call."""

    model: str
    content: str
    finish_reason: str  # "stop" | "length" | "error" | "tool_calls"
    usage: TokenUsage = field(default_factory=TokenUsage)
    images: list[dict[str, str]] = field(default_factory=list)  # Output images
    provider: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
