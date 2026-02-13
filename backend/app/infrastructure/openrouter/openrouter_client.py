"""OpenRouter API client — implements the ChatProvider interface.

Communicates with the OpenRouter API (https://openrouter.ai/api/v1)
using httpx for both non-streaming and SSE streaming chat completions.
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.application.interfaces.chat_provider import ChatProvider
from app.domain.entities import (
    ChatMessage,
    ChatCompletionResult,
    ContentPart,
    TokenUsage,
)
from app.domain.exceptions import ChatProviderError

logger = logging.getLogger(__name__)


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
        return payload

    @staticmethod
    def _serialize_message(msg: ChatMessage) -> dict:
        """Convert a domain ChatMessage to an API-compatible dict."""
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

        return ChatCompletionResult(
            model=data.get("model", ""),
            content=message.get("content", ""),
            finish_reason=choice.get("finish_reason", "stop"),
            usage=TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
            images=images,
            provider=self.provider_name,
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
