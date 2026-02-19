"""Abstract repository interface (port) for data sources."""

from abc import ABC, abstractmethod

from app.domain.entities.data_source import DataSource


class DataSourceRepository(ABC):
    """Port for data source persistence — implemented in the infrastructure layer."""

    @abstractmethod
    async def get_by_id(self, source_id: str) -> DataSource | None:
        """Retrieve a single data source by ID."""
        ...

    @abstractmethod
    async def get_all(self) -> list[DataSource]:
        """Retrieve all registered data sources."""
        ...

    @abstractmethod
    async def create(self, source: DataSource) -> DataSource:
        """Persist a new data source and return it with the generated ID."""
        ...

    @abstractmethod
    async def update(self, source: DataSource) -> DataSource:
        """Update an existing data source."""
        ...

    @abstractmethod
    async def delete(self, source_id: str) -> bool:
        """Delete a data source by ID. Returns True if deleted."""
        ...
