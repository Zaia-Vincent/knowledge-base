"""SQLAlchemy implementation of the ProcessingJobRepository."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.processing_job_repository import ProcessingJobRepository
from app.domain.entities.processing_job import JobStatus, ProcessingJob
from app.infrastructure.database.models.data_source_models import ProcessingJobModel


class SQLAlchemyProcessingJobRepository(ProcessingJobRepository):
    """Concrete processing job repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, job_id: str) -> ProcessingJob | None:
        result = await self._session.execute(
            select(ProcessingJobModel).where(ProcessingJobModel.id == job_id)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_data_source(
        self, source_id: str, limit: int = 100
    ) -> list[ProcessingJob]:
        result = await self._session.execute(
            select(ProcessingJobModel)
            .where(ProcessingJobModel.data_source_id == source_id)
            .order_by(ProcessingJobModel.created_at.desc())
            .limit(limit)
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_all(self, limit: int = 200) -> list[ProcessingJob]:
        result = await self._session.execute(
            select(ProcessingJobModel)
            .order_by(ProcessingJobModel.created_at.desc())
            .limit(limit)
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_queued(self, limit: int = 10) -> list[ProcessingJob]:
        result = await self._session.execute(
            select(ProcessingJobModel)
            .where(ProcessingJobModel.status == JobStatus.QUEUED.value)
            .order_by(ProcessingJobModel.created_at.asc())
            .limit(limit)
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def create(self, job: ProcessingJob) -> ProcessingJob:
        if not job.id:
            job.id = str(uuid.uuid4())

        model = ProcessingJobModel(
            id=job.id,
            data_source_id=job.data_source_id,
            resource_identifier=job.resource_identifier,
            resource_type=job.resource_type,
            status=job.status.value,
            progress_message=job.progress_message,
            result_file_id=job.result_file_id,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
        self._session.add(model)
        await self._session.flush()
        return job

    async def update(self, job: ProcessingJob) -> ProcessingJob:
        result = await self._session.execute(
            select(ProcessingJobModel).where(ProcessingJobModel.id == job.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"ProcessingJob with id {job.id} not found")

        model.status = job.status.value
        model.progress_message = job.progress_message
        model.result_file_id = job.result_file_id
        model.error_message = job.error_message
        model.started_at = job.started_at
        model.completed_at = job.completed_at
        await self._session.flush()
        return job

    async def delete_by_data_source(self, source_id: str) -> int:
        result = await self._session.execute(
            delete(ProcessingJobModel)
            .where(ProcessingJobModel.data_source_id == source_id)
        )
        await self._session.flush()
        return result.rowcount

    # ── Mapping ──────────────────────────────────────────────────────

    @staticmethod
    def _to_domain(model: ProcessingJobModel) -> ProcessingJob:
        return ProcessingJob(
            id=model.id,
            data_source_id=model.data_source_id,
            resource_identifier=model.resource_identifier,
            resource_type=model.resource_type,
            status=JobStatus(model.status),
            progress_message=model.progress_message,
            result_file_id=model.result_file_id,
            error_message=model.error_message,
            created_at=model.created_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
        )
