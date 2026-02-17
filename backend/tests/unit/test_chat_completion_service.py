"""Unit tests for the ChatCompletionService."""

import pytest

from app.application.schemas.chat import ChatCompletionRequest, ChatMessageSchema
from app.application.services.chat_completion_service import ChatCompletionService
from app.application.interfaces.chat_provider import ChatProvider
from app.application.interfaces.service_request_log_repository import (
    ServiceRequestLogRepository,
)
from app.domain.entities import (
    ChatMessage,
    ChatCompletionResult,
    ServiceRequestLog,
    TokenUsage,
)
from app.domain.exceptions import ChatProviderError
from collections.abc import AsyncIterator


# ── Fakes ──


class FakeChatProvider(ChatProvider):
    """In-memory fake provider for unit testing."""

    def __init__(
        self,
        *,
        result: ChatCompletionResult | None = None,
        stream_chunks: list[str] | None = None,
        error: ChatProviderError | None = None,
    ):
        self._result = result
        self._stream_chunks = stream_chunks or []
        self._error = error

    @property
    def provider_name(self) -> str:
        return "fake"

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletionResult:
        if self._error:
            raise self._error
        return self._result  # type: ignore

    async def stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        if self._error:
            raise self._error
        for chunk in self._stream_chunks:
            yield chunk


class FakeServiceRequestLogRepository(ServiceRequestLogRepository):
    """In-memory fake repository for unit testing."""

    def __init__(self):
        self._logs: list[ServiceRequestLog] = []
        self._next_id = 1

    async def create(self, log: ServiceRequestLog) -> ServiceRequestLog:
        log.id = self._next_id
        self._next_id += 1
        self._logs.append(log)
        return log

    async def get_all(
        self, *, skip: int = 0, limit: int = 100
    ) -> list[ServiceRequestLog]:
        return list(reversed(self._logs))[skip : skip + limit]


# ── Fixtures ──


def _make_request(model: str = "test/model") -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=model,
        messages=[ChatMessageSchema(role="user", content="Hello")],
    )


def _make_result(**overrides) -> ChatCompletionResult:
    defaults = {
        "model": "test/model",
        "content": "Test response",
        "finish_reason": "stop",
        "usage": TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30, cost=0.001),
        "provider": "fake",
    }
    defaults.update(overrides)
    return ChatCompletionResult(**defaults)


# ── Tests ──


@pytest.mark.asyncio
async def test_complete_returns_result():
    """Non-streaming call returns correct result."""
    expected = _make_result()
    provider = FakeChatProvider(result=expected)
    log_repo = FakeServiceRequestLogRepository()
    service = ChatCompletionService(provider=provider, log_repository=log_repo)

    result = await service.complete(_make_request())

    assert result.content == "Test response"
    assert result.model == "test/model"
    assert result.usage.total_tokens == 30


@pytest.mark.asyncio
async def test_complete_logs_request():
    """Non-streaming call logs the request with usage and cost."""
    expected = _make_result()
    provider = FakeChatProvider(result=expected)
    log_repo = FakeServiceRequestLogRepository()
    service = ChatCompletionService(provider=provider, log_repository=log_repo)

    await service.complete(_make_request())

    assert len(log_repo._logs) == 1
    log = log_repo._logs[0]
    assert log.model == "test/model"
    assert log.provider == "fake"
    assert log.prompt_tokens == 10
    assert log.completion_tokens == 20
    assert log.total_tokens == 30
    assert log.cost == 0.001
    assert log.status == "success"
    assert log.duration_ms is not None


@pytest.mark.asyncio
async def test_complete_provider_error_logged():
    """Provider errors are logged with error status."""
    error = ChatProviderError(provider="fake", status_code=429, message="Rate limited")
    provider = FakeChatProvider(error=error)
    log_repo = FakeServiceRequestLogRepository()
    service = ChatCompletionService(provider=provider, log_repository=log_repo)

    with pytest.raises(ChatProviderError):
        await service.complete(_make_request())

    assert len(log_repo._logs) == 1
    log = log_repo._logs[0]
    assert log.status == "error"
    assert "Rate limited" in (log.error_message or "")


@pytest.mark.asyncio
async def test_stream_yields_chunks():
    """Streaming call yields all chunks from the provider."""
    chunks = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" world"}}]}',
        "data: [DONE]",
    ]
    provider = FakeChatProvider(stream_chunks=chunks)
    log_repo = FakeServiceRequestLogRepository()
    service = ChatCompletionService(provider=provider, log_repository=log_repo)

    received = []
    async for chunk in service.stream(_make_request()):
        received.append(chunk)

    assert len(received) == 3
    assert received[0] == chunks[0]
    assert received[2] == "data: [DONE]"


@pytest.mark.asyncio
async def test_stream_logs_after_completion():
    """Streaming call logs the request after the stream ends."""
    chunks = ['data: {"choices":[{"delta":{"content":"Hi"}}]}']
    provider = FakeChatProvider(stream_chunks=chunks)
    log_repo = FakeServiceRequestLogRepository()
    service = ChatCompletionService(provider=provider, log_repository=log_repo)

    async for _ in service.stream(_make_request()):
        pass

    assert len(log_repo._logs) == 1
    assert log_repo._logs[0].status == "success"


@pytest.mark.asyncio
async def test_get_logs_returns_entries():
    """Log retrieval returns stored entries."""
    expected = _make_result()
    provider = FakeChatProvider(result=expected)
    log_repo = FakeServiceRequestLogRepository()
    service = ChatCompletionService(provider=provider, log_repository=log_repo)

    await service.complete(_make_request("model-1"))
    await service.complete(_make_request("model-2"))

    logs = await service.get_logs()
    assert len(logs) == 2


@pytest.mark.asyncio
async def test_multimodal_message_conversion():
    """Multimodal messages with text + image are correctly converted."""
    from app.application.schemas.chat import ContentPartSchema, ImageUrlDetail

    expected = _make_result()
    provider = FakeChatProvider(result=expected)
    log_repo = FakeServiceRequestLogRepository()
    service = ChatCompletionService(provider=provider, log_repository=log_repo)

    request = ChatCompletionRequest(
        model="test/model",
        messages=[
            ChatMessageSchema(
                role="user",
                content=[
                    ContentPartSchema(type="text", text="What is in this image?"),
                    ContentPartSchema(
                        type="image_url",
                        image_url=ImageUrlDetail(url="https://example.com/img.jpg"),
                    ),
                ],
            )
        ],
    )

    result = await service.complete(request)
    assert result.content == "Test response"
