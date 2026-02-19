"""Abstract repository interface (port) for processed resources."""

from abc import ABC, abstractmethod

from app.domain.entities import Resource
from app.domain.entities.query import MetadataFilter


class ResourceRepository(ABC):
    """Port for resource persistence — implemented in the infrastructure layer."""

    @abstractmethod
    async def get_by_id(self, resource_id: str) -> Resource | None:
        """Retrieve a single resource by its ID."""
        ...

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Resource]:
        """Retrieve a paginated list of resources."""
        ...

    @abstractmethod
    async def get_by_source(self, source_id: str) -> list[Resource]:
        """Retrieve all resources belonging to a specific data source."""
        ...

    @abstractmethod
    async def create(self, resource: Resource) -> Resource:
        """Persist a new resource and return it with the generated ID."""
        ...

    @abstractmethod
    async def update(self, resource: Resource) -> Resource:
        """Update an existing resource."""
        ...

    @abstractmethod
    async def delete(self, resource_id: str) -> bool:
        """Delete a resource record by ID. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    async def delete_by_source(self, source_id: str) -> int:
        """Delete all resources belonging to a data source. Returns count of deleted records."""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Return the total number of resources."""
        ...

    @abstractmethod
    async def search(
        self,
        concept_ids: list[str] | None = None,
        metadata_filters: list[MetadataFilter] | None = None,
        text_query: str | None = None,
        limit: int = 50,
    ) -> list[Resource]:
        """Search resources by concept, metadata, or text content."""
        ...
