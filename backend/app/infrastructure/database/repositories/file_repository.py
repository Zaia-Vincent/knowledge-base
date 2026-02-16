"""SQLAlchemy implementation of the FileRepository for processed files."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces import FileRepository
from app.domain.entities import (
    ClassificationResult,
    ClassificationSignal,
    ProcessedFile,
    ProcessingStatus,
)
from app.infrastructure.database.models.file_models import ProcessedFileModel


class SQLAlchemyFileRepository(FileRepository):
    """Concrete file repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, file_id: str) -> ProcessedFile | None:
        result = await self._session.execute(
            select(ProcessedFileModel).where(ProcessedFileModel.id == file_id)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ProcessedFile]:
        result = await self._session.execute(
            select(ProcessedFileModel)
            .order_by(ProcessedFileModel.uploaded_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def create(self, pf: ProcessedFile) -> ProcessedFile:
        if not pf.id:
            pf.id = str(uuid.uuid4())

        model = ProcessedFileModel(
            id=pf.id,
            filename=pf.filename,
            original_path=pf.original_path,
            file_size=pf.file_size,
            mime_type=pf.mime_type,
            stored_path=pf.stored_path,
            status=pf.status.value,
            extracted_text=pf.extracted_text,
            concept_id=pf.classification.primary_concept_id if pf.classification else None,
            concept_label=None,
            classification_confidence=pf.classification.confidence if pf.classification else None,
            classification_signals=self._signals_to_json(pf.classification) if pf.classification else None,
            metadata_=pf.metadata,
            extra_fields=pf.extra_fields,
            summary=pf.summary,
            language=pf.language,
            processing_time_ms=pf.processing_time_ms,
            origin_file_id=pf.origin_file_id,
            page_range=pf.page_range,
            uploaded_at=pf.uploaded_at,
            processed_at=pf.processed_at,
            error_message=pf.error_message,
        )

        self._session.add(model)
        await self._session.flush()
        return pf

    async def update(self, pf: ProcessedFile) -> ProcessedFile:
        result = await self._session.execute(
            select(ProcessedFileModel).where(ProcessedFileModel.id == pf.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"ProcessedFile with id {pf.id} not found")

        # Core fields
        model.status = pf.status.value
        model.extracted_text = pf.extracted_text
        model.processed_at = pf.processed_at
        model.error_message = pf.error_message

        # Classification (flat columns)
        if pf.classification:
            model.concept_id = pf.classification.primary_concept_id
            model.classification_confidence = pf.classification.confidence
            model.classification_signals = self._signals_to_json(pf.classification)

        # Metadata (JSONB — direct assignment)
        if pf.metadata:
            model.metadata_ = pf.metadata
        if pf.extra_fields:
            model.extra_fields = pf.extra_fields

        # Summary
        if pf.summary is not None:
            model.summary = pf.summary
        if pf.language is not None:
            model.language = pf.language
        if pf.processing_time_ms is not None:
            model.processing_time_ms = pf.processing_time_ms

        await self._session.flush()
        return pf

    async def delete(self, file_id: str) -> bool:
        result = await self._session.execute(
            select(ProcessedFileModel).where(ProcessedFileModel.id == file_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(ProcessedFileModel)
        )
        return result.scalar_one()

    # ── Mapping ──────────────────────────────────────────────────────

    @staticmethod
    def _signals_to_json(classification: ClassificationResult) -> list[dict]:
        """Serialize classification signals to JSONB-compatible list."""
        return [
            {
                "method": s.method,
                "concept_id": s.concept_id,
                "score": s.score,
                "details": s.details,
            }
            for s in classification.signals
        ]

    def _to_domain(self, model: ProcessedFileModel) -> ProcessedFile:
        classification = None
        if model.concept_id:
            signals = [
                ClassificationSignal(
                    method=s.get("method", ""),
                    concept_id=s.get("concept_id", ""),
                    score=s.get("score", 0.0),
                    details=s.get("details", ""),
                )
                for s in (model.classification_signals or [])
            ]
            classification = ClassificationResult(
                primary_concept_id=model.concept_id,
                confidence=model.classification_confidence or 0.0,
                signals=signals,
            )

        return ProcessedFile(
            id=model.id,
            filename=model.filename,
            original_path=model.original_path,
            file_size=model.file_size,
            mime_type=model.mime_type,
            stored_path=model.stored_path,
            status=ProcessingStatus(model.status),
            extracted_text=model.extracted_text,
            classification=classification,
            metadata=model.metadata_ or {},
            extra_fields=model.extra_fields or [],
            summary=model.summary,
            language=model.language,
            processing_time_ms=model.processing_time_ms,
            origin_file_id=model.origin_file_id,
            page_range=model.page_range,
            uploaded_at=model.uploaded_at,
            processed_at=model.processed_at,
            error_message=model.error_message,
        )
