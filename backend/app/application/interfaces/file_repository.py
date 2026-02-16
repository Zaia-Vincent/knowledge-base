"""Abstract repository interface (port) for processed files."""

from abc import ABC, abstractmethod

from app.domain.entities import ProcessedFile


class FileRepository(ABC):
    """Port for processed file persistence — implemented in the infrastructure layer."""

    @abstractmethod
    async def get_by_id(self, file_id: str) -> ProcessedFile | None:
        """Retrieve a single processed file by its ID."""
        ...

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ProcessedFile]:
        """Retrieve a paginated list of processed files."""
        ...

    @abstractmethod
    async def create(self, processed_file: ProcessedFile) -> ProcessedFile:
        """Persist a new processed file and return it with the generated ID."""
        ...

    @abstractmethod
    async def update(self, processed_file: ProcessedFile) -> ProcessedFile:
        """Update an existing processed file."""
        ...

    @abstractmethod
    async def delete(self, file_id: str) -> bool:
        """Delete a processed file record by ID. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Return the total number of processed files."""
        ...
