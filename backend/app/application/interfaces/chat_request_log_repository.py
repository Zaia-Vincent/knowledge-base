"""Abstract repository interface for chat request logs."""

from abc import ABC, abstractmethod

from app.domain.entities import ChatRequestLog


class ChatRequestLogRepository(ABC):
    """Port — defines persistence operations for chat request logs."""

    @abstractmethod
    async def create(self, log: ChatRequestLog) -> ChatRequestLog:
        """Persist a new chat request log entry.

        Returns:
            The created log with its assigned ID.
        """
        ...

    @abstractmethod
    async def get_all(
        self, *, skip: int = 0, limit: int = 100
    ) -> list[ChatRequestLog]:
        """Retrieve chat request logs, ordered by most recent first."""
        ...
