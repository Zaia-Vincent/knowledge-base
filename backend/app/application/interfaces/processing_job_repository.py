"""Abstract repository interface (port) for processing jobs."""

from abc import ABC, abstractmethod

from app.domain.entities.processing_job import ProcessingJob


class ProcessingJobRepository(ABC):
    """Port for processing job persistence — implemented in the infrastructure layer."""

    @abstractmethod
    async def get_by_id(self, job_id: str) -> ProcessingJob | None:
        """Retrieve a single job by ID."""
        ...

    @abstractmethod
    async def get_by_data_source(
        self, source_id: str, limit: int = 100
    ) -> list[ProcessingJob]:
        """Retrieve jobs for a specific data source, most recent first."""
        ...

    @abstractmethod
    async def get_all(self, limit: int = 200) -> list[ProcessingJob]:
        """Retrieve all jobs, most recent first."""
        ...

    @abstractmethod
    async def get_queued(self, limit: int = 10) -> list[ProcessingJob]:
        """Retrieve queued jobs ordered by creation time (FIFO)."""
        ...

    @abstractmethod
    async def create(self, job: ProcessingJob) -> ProcessingJob:
        """Persist a new job and return it with the generated ID."""
        ...

    @abstractmethod
    async def update(self, job: ProcessingJob) -> ProcessingJob:
        """Update an existing job."""
        ...

    @abstractmethod
    async def delete_by_data_source(self, source_id: str) -> int:
        """Delete all jobs for a data source. Returns number of deleted rows."""
        ...
