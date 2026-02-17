"""Unit tests for the OpenRouterClient."""

import json

import httpx
import pytest

from app.infrastructure.openrouter.openrouter_client import OpenRouterClient
from app.domain.entities import ChatMessage, ContentPart
from app.domain.exceptions import ChatProviderError


# ── Helpers ──


def _mock_openrouter_response(
    content: str = "Hello!",
    model: str = "openai/gpt-4o-mini",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
    cost: float | None = 0.00014,
) -> dict:
    """Build a mock OpenRouter JSON response."""
    return {
        "id": "chatcmpl-test123",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "model": model,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            **({
                "cost": cost,
            } if cost is not None else {}),
        },
    }


def _make_mock_transport(
    response_data: dict | None = None,
    status_code: int = 200,
    error_data: dict | None = None,
) -> httpx.MockTransport:
    """Create a mock transport that returns a fixed response."""

    def handler(request: httpx.Request) -> httpx.Response:
        if error_data:
            return httpx.Response(status_code, json=error_data)
        return httpx.Response(status_code, json=response_data or {})

    return httpx.MockTransport(handler)


def _make_sse_mock_transport(lines: list[str]) -> httpx.MockTransport:
    """Create a mock transport that returns SSE content."""

    def handler(request: httpx.Request) -> httpx.Response:
        content = "\n".join(lines) + "\n"
        return httpx.Response(
            200,
            content=content.encode(),
            headers={"content-type": "text/event-stream"},
        )

    return httpx.MockTransport(handler)


# ── Tests ──


@pytest.mark.asyncio
async def test_complete_parses_response():
    """Non-streaming call correctly parses OpenRouter JSON response."""
    response_data = _mock_openrouter_response(content="The answer is 42.")
    transport = _make_mock_transport(response_data)
    client = OpenRouterClient(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=transport),
    )

    result = await client.complete(
        messages=[ChatMessage(role="user", content="What is 42?")],
        model="openai/gpt-4o-mini",
    )

    assert result.content == "The answer is 42."
    assert result.model == "openai/gpt-4o-mini"
    assert result.usage.prompt_tokens == 10
    assert result.usage.completion_tokens == 5
    assert result.usage.total_tokens == 15
    assert result.usage.cost == 0.00014
    assert result.provider == "openrouter"


@pytest.mark.asyncio
async def test_complete_error_handling():
    """Non-streaming call raises ChatProviderError on 4xx/5xx."""
    error_data = {"error": {"code": 429, "message": "Rate limit exceeded"}}
    transport = _make_mock_transport(error_data=error_data, status_code=429)
    client = OpenRouterClient(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=transport),
    )

    with pytest.raises(ChatProviderError) as exc_info:
        await client.complete(
            messages=[ChatMessage(role="user", content="Hi")],
            model="openai/gpt-4o-mini",
        )

    assert exc_info.value.status_code == 429
    assert "Rate limit" in exc_info.value.message


@pytest.mark.asyncio
async def test_complete_multimodal_message():
    """Multimodal messages are correctly serialized."""
    response_data = _mock_openrouter_response(content="I see an image.")
    transport = _make_mock_transport(response_data)
    client = OpenRouterClient(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=transport),
    )

    result = await client.complete(
        messages=[
            ChatMessage(
                role="user",
                content=[
                    ContentPart(type="text", text="What is this?"),
                    ContentPart(
                        type="image_url",
                        image_url={"url": "https://example.com/img.jpg"},
                    ),
                ],
            )
        ],
        model="openai/gpt-4o-mini",
    )

    assert result.content == "I see an image."


@pytest.mark.asyncio
async def test_stream_parses_sse_chunks():
    """Streaming call yields correctly parsed SSE data chunks."""
    sse_lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        "data: [DONE]",
    ]
    transport = _make_sse_mock_transport(sse_lines)
    client = OpenRouterClient(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=transport),
    )

    received = []
    async for chunk in client.stream(
        messages=[ChatMessage(role="user", content="Hi")],
        model="openai/gpt-4o-mini",
    ):
        received.append(chunk)

    assert len(received) == 3
    assert "Hello" in received[0]
    assert "world" in received[1]
    assert received[2] == "data: [DONE]"


@pytest.mark.asyncio
async def test_stream_ignores_keepalive_comments():
    """Streaming call filters out OpenRouter keepalive comments."""
    sse_lines = [
        ": OPENROUTER PROCESSING",
        'data: {"choices":[{"delta":{"content":"Hi"}}]}',
        ": OPENROUTER PROCESSING",
        "data: [DONE]",
    ]
    transport = _make_sse_mock_transport(sse_lines)
    client = OpenRouterClient(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=transport),
    )

    received = []
    async for chunk in client.stream(
        messages=[ChatMessage(role="user", content="Hi")],
        model="openai/gpt-4o-mini",
    ):
        received.append(chunk)

    # Only data lines should be yielded, not comments
    assert len(received) == 2
    assert all(c.startswith("data: ") for c in received)


@pytest.mark.asyncio
async def test_provider_name():
    """Provider name is correctly reported."""
    client = OpenRouterClient(api_key="test-key")
    assert client.provider_name == "openrouter"
