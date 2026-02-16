"""OpenRouter API client — implements the ChatProvider interface.

Communicates with the OpenRouter API (https://openrouter.ai/api/v1)
using httpx for both non-streaming and SSE streaming chat completions.
Supports tool calling for agentic workflows.
"""

import json
import logging
from collections.abc import AsyncIterator, Callable, Awaitable
from typing import Any

import httpx

from app.application.interfaces.chat_provider import ChatProvider
from app.domain.entities import (
    ChatMessage,
    ChatCompletionResult,
    ContentPart,
    TokenUsage,
    ToolCall,
    ToolCallFunction,
)
from app.domain.exceptions import ChatProviderError

logger = logging.getLogger(__name__)

# Type alias for tool handler callbacks
ToolHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class OpenRouterClient(ChatProvider):
    """Infrastructure adapter — connects to the OpenRouter API.

    Uses httpx with connection pooling for high-performance async requests.
    Supports both standard JSON responses and SSE streaming.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        app_name: str = "Knowledge Base",
        http_client: httpx.AsyncClient | None = None,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._app_name = app_name
        self._http_client = http_client

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def _get_headers(self) -> dict[str, str]:
        """Standard headers for OpenRouter requests."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Title": self._app_name,
        }

    def _build_payload(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict | None = None,
    ) -> dict:
        """Build the request payload for the OpenRouter API."""
        payload: dict = {
            "model": model,
            "messages": [self._serialize_message(m) for m in messages],
        }
        if stream:
            payload["stream"] = True
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        return payload

    @staticmethod
    def _serialize_message(msg: ChatMessage) -> dict:
        """Convert a domain ChatMessage to an API-compatible dict."""
        # Tool response message
        if msg.role == "tool":
            result: dict = {
                "role": "tool",
                "content": msg.content if isinstance(msg.content, str) else "",
                "tool_call_id": msg.tool_call_id or "",
            }
            if msg.name:
                result["name"] = msg.name
            return result

        # Assistant message with tool calls
        if msg.role == "assistant" and msg.tool_calls:
            result = {
                "role": "assistant",
                "content": msg.content if isinstance(msg.content, str) else None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
            return result

        # Standard text or multimodal message
        if isinstance(msg.content, str):
            return {"role": msg.role, "content": msg.content}

        # Multimodal content
        parts = []
        for part in msg.content:
            if part.type == "text":
                parts.append({"type": "text", "text": part.text or ""})
            elif part.type == "image_url" and part.image_url:
                parts.append({
                    "type": "image_url",
                    "image_url": part.image_url,
                })
            elif part.type == "file" and part.file_data:
                parts.append({
                    "type": "file",
                    "file": part.file_data,
                })
        return {"role": msg.role, "content": parts}

    async def _get_client(self) -> httpx.AsyncClient:
        """Return the injected client or create a new one."""
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=120.0)

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatCompletionResult:
        """Send a non-streaming chat completion to OpenRouter."""
        payload = self._build_payload(
            messages, model, temperature=temperature, max_tokens=max_tokens
        )
        url = f"{self._base_url}/chat/completions"

        client = await self._get_client()
        should_close = self._http_client is None

        try:
            response = await client.post(
                url, headers=self._get_headers(), json=payload
            )

            if response.status_code != 200:
                self._raise_provider_error(response)

            data = response.json()
            return self._parse_completion_response(data)

        finally:
            if should_close:
                await client.aclose()

    async def complete_with_tools(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        tools: list[dict],
        tool_handler: ToolHandler,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_iterations: int = 10,
    ) -> ChatCompletionResult:
        """Run a tool-calling loop until the LLM produces a final response.

        The LLM may request tool calls in its response. For each tool call,
        the tool_handler callback is invoked with (tool_name, parsed_args),
        and its result is sent back as a tool response message. The loop
        continues until the LLM returns a non-tool-call response or the
        max_iterations limit is reached.

        Args:
            messages: Initial conversation messages.
            tools: Tool definitions in OpenAI function-calling format.
            tool_handler: Async callback (name, args) -> result_dict.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens per response.
            max_iterations: Safety limit on tool-calling rounds.

        Returns:
            The final ChatCompletionResult after all tool calls are resolved.
        """
        conversation = list(messages)  # Don't mutate the original
        total_usage = TokenUsage()
        url = f"{self._base_url}/chat/completions"

        client = await self._get_client()
        should_close = self._http_client is None

        try:
            for iteration in range(max_iterations):
                payload = self._build_payload(
                    conversation,
                    model,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                response = await client.post(
                    url, headers=self._get_headers(), json=payload
                )

                if response.status_code != 200:
                    self._raise_provider_error(response)

                data = response.json()
                result = self._parse_completion_response(data)

                # Accumulate token usage
                total_usage.prompt_tokens += result.usage.prompt_tokens
                total_usage.completion_tokens += result.usage.completion_tokens
                total_usage.total_tokens += result.usage.total_tokens

                # If no tool calls, we're done
                if not result.tool_calls:
                    result.usage = total_usage
                    return result

                logger.info(
                    "Tool-calling iteration %d: %d tool call(s)",
                    iteration + 1,
                    len(result.tool_calls),
                )

                # Add the assistant's tool-call message to conversation
                assistant_msg = ChatMessage(
                    role="assistant",
                    content=result.content or "",
                    tool_calls=result.tool_calls,
                )
                conversation.append(assistant_msg)

                # Execute each tool call and add results
                for tc in result.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    logger.info(
                        "Executing tool '%s' (call_id=%s)",
                        tc.function.name,
                        tc.id,
                    )

                    try:
                        tool_result = await tool_handler(tc.function.name, args)
                    except Exception as e:
                        logger.exception("Tool '%s' failed", tc.function.name)
                        tool_result = {"error": str(e)}

                    tool_msg = ChatMessage(
                        role="tool",
                        content=json.dumps(tool_result),
                        tool_call_id=tc.id,
                        name=tc.function.name,
                    )
                    conversation.append(tool_msg)

            # Max iterations reached — return what we have
            logger.warning(
                "Tool-calling loop reached max iterations (%d)", max_iterations
            )
            result.usage = total_usage
            return result

        finally:
            if should_close:
                await client.aclose()

    async def stream(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Send a streaming chat completion to OpenRouter.

        Yields SSE-formatted 'data: {...}' lines. Filters out
        OpenRouter keepalive comments (': OPENROUTER PROCESSING').
        """
        payload = self._build_payload(
            messages, model, stream=True, temperature=temperature, max_tokens=max_tokens
        )
        url = f"{self._base_url}/chat/completions"

        client = await self._get_client()
        should_close = self._http_client is None

        try:
            async with client.stream(
                "POST", url, headers=self._get_headers(), json=payload
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    self._raise_provider_error_from_bytes(
                        response.status_code, body
                    )

                async for line in response.aiter_lines():
                    # Skip empty lines and OpenRouter keepalive comments
                    if not line or line.startswith(":"):
                        continue

                    # End of stream marker
                    if line.strip() == "data: [DONE]":
                        yield line
                        break

                    # Yield valid SSE data lines
                    if line.startswith("data: "):
                        yield line

        finally:
            if should_close:
                await client.aclose()

    def _parse_completion_response(self, data: dict) -> ChatCompletionResult:
        """Parse the OpenRouter JSON response into a domain entity."""
        # Check for error in response body
        if "error" in data:
            error = data["error"]
            raise ChatProviderError(
                provider=self.provider_name,
                status_code=error.get("code", 500),
                message=error.get("message", "Unknown error"),
            )

        choices = data.get("choices", [])
        if not choices:
            raise ChatProviderError(
                provider=self.provider_name,
                status_code=500,
                message="No choices in response",
            )

        choice = choices[0]
        message = choice.get("message", {})
        usage_data = data.get("usage", {})

        # Extract output images if present
        images = []
        if "images" in message:
            images = message["images"]

        # Parse tool calls if present
        tool_calls = []
        if "tool_calls" in message and message["tool_calls"]:
            for tc in message["tool_calls"]:
                func_data = tc.get("function", {})
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        type=tc.get("type", "function"),
                        function=ToolCallFunction(
                            name=func_data.get("name", ""),
                            arguments=func_data.get("arguments", "{}"),
                        ),
                    )
                )

        return ChatCompletionResult(
            model=data.get("model", ""),
            content=message.get("content", "") or "",
            finish_reason=choice.get("finish_reason", "stop") or "stop",
            usage=TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
            images=images,
            provider=self.provider_name,
            tool_calls=tool_calls,
        )

    def _raise_provider_error(self, response: httpx.Response) -> None:
        """Raise ChatProviderError from a non-200 httpx Response."""
        try:
            data = response.json()
            error = data.get("error", {})
            message = error.get("message", response.text)
        except Exception:
            message = response.text

        raise ChatProviderError(
            provider=self.provider_name,
            status_code=response.status_code,
            message=message,
        )

    def _raise_provider_error_from_bytes(
        self, status_code: int, body: bytes
    ) -> None:
        """Raise ChatProviderError from raw response bytes."""
        try:
            data = json.loads(body)
            error = data.get("error", {})
            message = error.get("message", body.decode())
        except Exception:
            message = body.decode(errors="replace")

        raise ChatProviderError(
            provider=self.provider_name,
            status_code=status_code,
            message=message,
        )

