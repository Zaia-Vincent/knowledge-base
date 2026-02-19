"""SSE Manager — in-process event broadcaster for real-time processing updates."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages SSE client connections and broadcasts processing job updates.

    Each connected client gets its own asyncio.Queue. Broadcasting pushes
    the event to all queues. Clients consume events via an async generator.
    """

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[str | None]] = []

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribe to SSE events. Yields formatted SSE strings.

        The generator automatically unsubscribes when the client disconnects.
        """
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._queues.append(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            self._queues.remove(queue)

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an SSE event to all connected clients."""
        sse_message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        dead_queues: list[asyncio.Queue[str | None]] = []

        for queue in self._queues:
            try:
                queue.put_nowait(sse_message)
            except asyncio.QueueFull:
                dead_queues.append(queue)
                logger.warning("SSE client queue full — disconnecting")

        for q in dead_queues:
            q.put_nowait(None)
            self._queues.remove(q)

    async def shutdown(self) -> None:
        """Disconnect all connected clients."""
        for queue in self._queues:
            queue.put_nowait(None)
        self._queues.clear()

    @property
    def client_count(self) -> int:
        return len(self._queues)
