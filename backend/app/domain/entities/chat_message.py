"""Domain entities for chat messages — framework-independent, multimodal."""

from dataclasses import dataclass, field


@dataclass
class ContentPart:
    """A single content part within a multimodal message.

    Supports text and image_url types, following the OpenAI-compatible
    multimodal format used by OpenRouter and other providers.
    """

    type: str  # "text" | "image_url"
    text: str | None = None
    image_url: dict[str, str] | None = None  # {"url": "..."}


@dataclass
class ChatMessage:
    """A single message in a chat conversation.

    Content can be a plain string (text-only) or a list of ContentPart
    objects for multimodal input (text + images).
    """

    role: str  # "system" | "user" | "assistant"
    content: str | list[ContentPart] = ""


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
    finish_reason: str  # "stop" | "length" | "error"
    usage: TokenUsage = field(default_factory=TokenUsage)
    images: list[dict[str, str]] = field(default_factory=list)  # Output images
    provider: str = ""
