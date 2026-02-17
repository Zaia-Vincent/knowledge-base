"""Chat completion endpoints — non-streaming, streaming, and logs."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.application.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ServiceRequestLogResponse,
    TokenUsageResponse,
)
from app.application.services import ChatCompletionService
from app.domain.exceptions import ChatProviderError
from app.infrastructure.dependencies import get_chat_completion_service

router = APIRouter(prefix="/chat", tags=["Chat Completions"])


@router.post("/completions", response_model=ChatCompletionResponse)
async def chat_completion(
    request: ChatCompletionRequest,
    service: ChatCompletionService = Depends(get_chat_completion_service),
) -> ChatCompletionResponse:
    """Execute a non-streaming chat completion.

    Supports multimodal input: messages can contain text and/or image URLs.
    The request is logged with token usage and cost.
    """
    try:
        result = await service.complete(request)
    except ChatProviderError as e:
        raise HTTPException(
            status_code=e.status_code if 400 <= e.status_code < 600 else 502,
            detail=f"[{e.provider}] {e.message}",
        )

    return ChatCompletionResponse(
        model=result.model,
        content=result.content,
        finish_reason=result.finish_reason,
        usage=TokenUsageResponse(
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
            cost=result.usage.cost,
        ),
        provider=result.provider,
        images=result.images,
    )


@router.post("/completions/stream")
async def chat_completion_stream(
    request: ChatCompletionRequest,
    service: ChatCompletionService = Depends(get_chat_completion_service),
) -> StreamingResponse:
    """Execute a streaming chat completion via Server-Sent Events (SSE).

    Returns a stream of SSE chunks. Each chunk is a 'data: {...}' line
    following the OpenAI-compatible SSE format.
    """

    async def event_generator():
        try:
            async for chunk in service.stream(request):
                yield f"{chunk}\n\n"
        except ChatProviderError as e:
            # Send error as SSE event
            import json

            error_data = json.dumps(
                {"error": {"code": e.status_code, "message": e.message}}
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/logs", response_model=list[ServiceRequestLogResponse])
async def get_chat_logs(
    skip: int = 0,
    limit: int = 100,
    service: ChatCompletionService = Depends(get_chat_completion_service),
) -> list[ServiceRequestLogResponse]:
    """Retrieve service request logs for monitoring.

    Returns a paginated list of all chat completion requests,
    ordered by most recent first, including token usage and cost.
    """
    logs = await service.get_logs(skip=skip, limit=limit)
    return [
        ServiceRequestLogResponse(
            id=log.id,
            model=log.model,
            provider=log.provider,
            prompt_tokens=log.prompt_tokens,
            completion_tokens=log.completion_tokens,
            total_tokens=log.total_tokens,
            cost=log.cost,
            duration_ms=log.duration_ms,
            status=log.status,
            error_message=log.error_message,
            feature=log.feature,
            tools_called=log.tools_called,
            tool_call_count=log.tool_call_count,
            request_context=log.request_context,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]
