"""Domain entity for processing jobs — database-backed job queue."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class JobStatus(str, Enum):
    """Lifecycle states of a processing job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessingJob:
    """A single unit of work in the background processing queue.

    Each job represents one resource (file or URL) that needs to be processed.
    Jobs are linked to a DataSource and, upon completion, to a ProcessedFile.
    """

    data_source_id: str
    resource_identifier: str  # filename or URL
    resource_type: str        # "file" | "url"
    id: str | None = None
    status: JobStatus = JobStatus.QUEUED
    progress_message: str | None = None
    result_file_id: str | None = None  # links to ProcessedFile.id on completion
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def mark_processing(self, message: str = "Processing started") -> None:
        """Transition to processing state."""
        self.status = JobStatus.PROCESSING
        self.started_at = datetime.now(timezone.utc)
        self.progress_message = message

    def mark_completed(self, result_file_id: str) -> None:
        """Transition to completed state with a reference to the processed file."""
        self.status = JobStatus.COMPLETED
        self.result_file_id = result_file_id
        self.completed_at = datetime.now(timezone.utc)
        self.progress_message = "Processing completed"

    def mark_failed(self, error: str) -> None:
        """Transition to failed state."""
        self.status = JobStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.now(timezone.utc)
        self.progress_message = f"Failed: {error[:100]}"

    def mark_requeued(self) -> None:
        """Reset the job to queued state for reprocessing."""
        self.status = JobStatus.QUEUED
        self.progress_message = "Re-queued for processing"
        self.error_message = None
        self.result_file_id = None
        self.started_at = None
        self.completed_at = None
