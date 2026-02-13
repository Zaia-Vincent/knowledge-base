"""Pydantic v2 schemas (DTOs) for chat completion requests and responses."""

from pydantic import BaseModel, Field


# ── Multimodal content parts ──


class ImageUrlDetail(BaseModel):
    """Image URL with optional detail level."""

    url: str
    detail: str | None = None  # "auto" | "low" | "high"


class ContentPartSchema(BaseModel):
    """A single part of a multimodal message content.

    Follows the OpenAI-compatible format used by OpenRouter and other providers.
    - type="text": contains a text field
    - type="image_url": contains an image_url field with a URL
    """

    type: str  # "text" | "image_url"
    text: str | None = None
    image_url: ImageUrlDetail | None = None


# ── Message schema ──


class ChatMessageSchema(BaseModel):
    """A chat message with multimodal support.

    Content can be either:
    - A plain string for text-only messages
    - A list of ContentPartSchema for multimodal messages (text + images)
    """

    role: str = Field(..., pattern=r"^(system|user|assistant)$")
    content: str | list[ContentPartSchema]


# ── Request / Response ──


class ChatCompletionRequest(BaseModel):
    """Request schema for chat completion endpoints."""

    model: str = Field(..., description="Model identifier, e.g. 'openai/gpt-4o-mini'")
    messages: list[ChatMessageSchema] = Field(
        ..., min_length=1, description="Conversation messages"
    )
    temperature: float | None = Field(
        default=None, ge=0.0, le=2.0, description="Sampling temperature"
    )
    max_tokens: int | None = Field(
        default=None, gt=0, description="Maximum tokens in the response"
    )
    stream: bool = Field(default=False, description="Enable SSE streaming")


class TokenUsageResponse(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float | None = None


class ChatCompletionResponse(BaseModel):
    """Response schema for non-streaming chat completion."""

    model: str
    content: str
    finish_reason: str
    usage: TokenUsageResponse
    provider: str = ""
    images: list[dict[str, str]] = Field(default_factory=list)


class ChatRequestLogResponse(BaseModel):
    """Response schema for chat request log entries."""

    id: int
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float | None
    duration_ms: int | None
    status: str
    error_message: str | None
    created_at: str  # ISO 8601

    model_config = {"from_attributes": True}
