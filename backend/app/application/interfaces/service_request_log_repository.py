"""Abstract repository interface for service request logs."""

from abc import ABC, abstractmethod

from app.domain.entities import ServiceRequestLog


class ServiceRequestLogRepository(ABC):
    """Port — defines persistence operations for service request logs."""

    @abstractmethod
    async def create(self, log: ServiceRequestLog) -> ServiceRequestLog:
        """Persist a new service request log entry.

        Returns:
            The created log with its assigned ID.
        """
        ...

    @abstractmethod
    async def get_all(
        self, *, skip: int = 0, limit: int = 100
    ) -> list[ServiceRequestLog]:
        """Retrieve service request logs, ordered by most recent first."""
        ...
