"""Abstract repository interface (port) for ClientRecord persistence."""

from abc import ABC, abstractmethod

from app.domain.entities import ClientRecord


class ClientRecordRepository(ABC):
    """Port for client record persistence — implemented in the infrastructure layer."""

    @abstractmethod
    async def get_by_id(self, record_id: str) -> ClientRecord | None:
        """Retrieve a single record by its UUID."""
        ...

    @abstractmethod
    async def get_all(
        self,
        *,
        module_name: str | None = None,
        entity_type: str | None = None,
        parent_id: str | None = None,
        user_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ClientRecord]:
        """Retrieve a filtered, paginated list of records."""
        ...

    @abstractmethod
    async def create(self, record: ClientRecord) -> ClientRecord:
        """Persist a new record and return it."""
        ...

    @abstractmethod
    async def update(self, record: ClientRecord) -> ClientRecord:
        """Update an existing record."""
        ...

    @abstractmethod
    async def delete(self, record_id: str) -> bool:
        """Delete a record. Returns True if deleted, False if not found."""
        ...
