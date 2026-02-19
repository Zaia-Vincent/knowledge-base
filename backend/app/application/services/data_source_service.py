"""Data Source Service — CRUD operations and job submission logic."""

import logging
import uuid
from datetime import datetime, timezone

from app.application.interfaces.data_source_repository import DataSourceRepository
from app.application.interfaces.processing_job_repository import ProcessingJobRepository
from app.domain.entities.data_source import DataSource, DataSourceType
from app.domain.entities.processing_job import JobStatus, ProcessingJob
from app.infrastructure.storage.local_file_storage import LocalFileStorage

logger = logging.getLogger(__name__)


class DataSourceService:
    """Application service for managing data sources and submitting processing jobs."""

    def __init__(
        self,
        source_repo: DataSourceRepository,
        job_repo: ProcessingJobRepository,
        file_storage: LocalFileStorage,
    ) -> None:
        self._source_repo = source_repo
        self._job_repo = job_repo
        self._file_storage = file_storage

    # ── Data Source CRUD ─────────────────────────────────────────────

    async def create_source(
        self,
        name: str,
        source_type: DataSourceType,
        description: str = "",
        config: dict | None = None,
    ) -> DataSource:
        """Create and persist a new data source."""
        now = datetime.now(timezone.utc)
        source = DataSource(
            id=str(uuid.uuid4()),
            name=name,
            source_type=source_type,
            description=description,
            config=config or {},
            created_at=now,
            updated_at=now,
        )
        return await self._source_repo.create(source)

    async def get_source(self, source_id: str) -> DataSource | None:
        return await self._source_repo.get_by_id(source_id)

    async def list_sources(self) -> list[DataSource]:
        return await self._source_repo.get_all()

    async def delete_source(self, source_id: str) -> bool:
        """Delete a data source and all its associated jobs."""
        await self._job_repo.delete_by_data_source(source_id)
        return await self._source_repo.delete(source_id)

    # ── Job Submission ───────────────────────────────────────────────

    async def store_files(
        self,
        source_id: str,
        files: list[tuple[str, bytes]],  # [(filename, content), ...]
    ) -> list[dict]:
        """Upload files and store metadata in config — no processing jobs created.

        Returns list of file entry dicts for the newly stored files.
        """
        source = await self._source_repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Data source {source_id} not found")
        if source.source_type != DataSourceType.FILE_UPLOAD:
            raise ValueError(f"Data source {source_id} is not a file_upload source")

        existing: list[dict] = source.config.get("files", [])
        new_entries: list[dict] = []

        for filename, content in files:
            stored = await self._file_storage.store_file(content, filename)
            entry = {
                "stored_path": stored.stored_path,
                "filename": stored.filename,
                "file_size": stored.file_size,
                "mime_type": stored.mime_type,
            }
            new_entries.append(entry)
            existing.append(entry)

        source.config["files"] = existing
        source.updated_at = datetime.now(timezone.utc)
        await self._source_repo.update(source)

        logger.info("Stored %d file(s) for source %s", len(new_entries), source_id)
        return new_entries

    async def get_source_files(self, source_id: str) -> list[dict]:
        """Return stored file entries for a file_upload data source."""
        source = await self._source_repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Data source {source_id} not found")
        if source.source_type != DataSourceType.FILE_UPLOAD:
            raise ValueError(f"Data source {source_id} is not a file_upload source")
        return source.config.get("files", [])

    async def remove_source_file(self, source_id: str, stored_path: str) -> list[dict]:
        """Remove a file from disk and from config. Returns updated file list."""
        source = await self._source_repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Data source {source_id} not found")
        if source.source_type != DataSourceType.FILE_UPLOAD:
            raise ValueError(f"Data source {source_id} is not a file_upload source")

        existing: list[dict] = source.config.get("files", [])
        source.config["files"] = [f for f in existing if f["stored_path"] != stored_path]
        source.updated_at = datetime.now(timezone.utc)
        await self._source_repo.update(source)

        # Delete from disk
        await self._file_storage.delete_file(stored_path)
        logger.info("Removed file %s from source %s", stored_path, source_id)
        return source.config["files"]

    async def process_files(
        self,
        source_id: str,
        stored_paths: list[str],
    ) -> list[ProcessingJob]:
        """Create processing jobs for selected stored files."""
        source = await self._source_repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Data source {source_id} not found")
        if source.source_type != DataSourceType.FILE_UPLOAD:
            raise ValueError(f"Data source {source_id} is not a file_upload source")

        existing: list[dict] = source.config.get("files", [])
        known_paths = {f["stored_path"] for f in existing}

        jobs: list[ProcessingJob] = []
        for path in stored_paths:
            if path not in known_paths:
                logger.warning("Skipping unknown file path: %s", path)
                continue
            entry = next(f for f in existing if f["stored_path"] == path)
            job = ProcessingJob(
                data_source_id=source_id,
                resource_identifier=path,
                resource_type="file",
            )
            job.progress_message = f"Queued: {entry['filename']} ({entry['file_size']} bytes)"
            created = await self._job_repo.create(job)
            jobs.append(created)

        # Remove processed files from config so they no longer appear in the UI.
        # The actual files on disk are preserved for the background processor.
        if jobs:
            processed_paths = {j.resource_identifier for j in jobs}
            source.config["files"] = [
                f for f in existing if f["stored_path"] not in processed_paths
            ]
            source.updated_at = datetime.now(timezone.utc)
            await self._source_repo.update(source)

        logger.info("Submitted %d file(s) for processing on source %s", len(jobs), source_id)
        return jobs

    async def submit_urls(
        self,
        source_id: str,
        urls: list[str],
    ) -> list[ProcessingJob]:
        """Create a processing job for each URL.

        Actual content fetching happens in the background processor.
        """
        source = await self._source_repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Data source {source_id} not found")
        if source.source_type != DataSourceType.WEBSITE:
            raise ValueError(f"Data source {source_id} is not a website source")

        jobs: list[ProcessingJob] = []
        for url in urls:
            # Normalise URL — ensure a valid scheme is present
            normalised = url.strip()
            if not normalised.startswith(("http://", "https://")):
                normalised = f"https://{normalised}"

            job = ProcessingJob(
                data_source_id=source_id,
                resource_identifier=normalised,
                resource_type="url",
            )
            job.progress_message = f"Queued: {normalised}"
            created = await self._job_repo.create(job)
            jobs.append(created)

        logger.info("Submitted %d URL(s) for processing on source %s", len(jobs), source_id)
        return jobs

    # ── Job Queries ──────────────────────────────────────────────────

    async def list_jobs(
        self,
        source_id: str | None = None,
        limit: int = 200,
    ) -> list[ProcessingJob]:
        """List processing jobs, optionally filtered by source."""
        if source_id:
            return await self._job_repo.get_by_data_source(source_id, limit=limit)
        return await self._job_repo.get_all(limit=limit)

    async def get_job(self, job_id: str) -> ProcessingJob | None:
        return await self._job_repo.get_by_id(job_id)

    # ── URL Management ───────────────────────────────────────────────

    async def get_source_urls(self, source_id: str) -> list[str]:
        """Return the stored URLs for a website data source."""
        source = await self._source_repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Data source {source_id} not found")
        if source.source_type != DataSourceType.WEBSITE:
            raise ValueError(f"Data source {source_id} is not a website source")
        return source.config.get("urls", [])

    async def update_source_urls(
        self, source_id: str, urls: list[str]
    ) -> list[str]:
        """Replace the stored URL list for a website data source."""
        source = await self._source_repo.get_by_id(source_id)
        if not source:
            raise ValueError(f"Data source {source_id} not found")
        if source.source_type != DataSourceType.WEBSITE:
            raise ValueError(f"Data source {source_id} is not a website source")

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for u in urls:
            stripped = u.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                unique.append(stripped)

        source.config["urls"] = unique
        source.updated_at = datetime.now(timezone.utc)
        await self._source_repo.update(source)
        logger.info("Updated URLs for source %s — %d URL(s)", source_id, len(unique))
        return unique

    async def restart_job(self, job_id: str) -> ProcessingJob:
        """Reset a completed or failed job back to queued for reprocessing.

        If the job previously produced Resource records, they are
        deleted so that the new processing run replaces the old results.
        """
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Processing job {job_id} not found")

        if job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
            raise ValueError(
                f"Only completed or failed jobs can be restarted (current: {job.status.value})"
            )

        # Delete old Resource results if any
        if job.result_file_id:
            from app.infrastructure.database.repositories import SQLAlchemyResourceRepository
            from app.infrastructure.database.session import async_session_factory

            # Use the same session from job_repo for consistency
            resource_repo = SQLAlchemyResourceRepository(self._job_repo._session)
            await resource_repo.delete(job.result_file_id)
            logger.info("Deleted old result resource %s for restarted job %s", job.result_file_id, job_id)

        job.mark_requeued()
        await self._job_repo.update(job)
        logger.info("Job %s re-queued for processing", job_id)
        return job
