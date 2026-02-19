"""SQLAlchemy implementation of the ResourceRepository for processed resources."""

import re
import uuid

from sqlalchemy import Float, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces import ResourceRepository
from app.domain.entities import (
    ClassificationResult,
    ClassificationSignal,
    Resource,
    ProcessingStatus,
)
from app.infrastructure.database.models.resource_models import ResourceModel


class SQLAlchemyResourceRepository(ResourceRepository):
    """Concrete resource repository backed by PostgreSQL via SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, resource_id: str) -> Resource | None:
        result = await self._session.execute(
            select(ResourceModel).where(ResourceModel.id == resource_id)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Resource]:
        result = await self._session.execute(
            select(ResourceModel)
            .order_by(ResourceModel.uploaded_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_by_source(self, source_id: str) -> list[Resource]:
        result = await self._session.execute(
            select(ResourceModel)
            .where(ResourceModel.data_source_id == source_id)
            .order_by(ResourceModel.uploaded_at.desc())
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def create(self, resource: Resource) -> Resource:
        if not resource.id:
            resource.id = str(uuid.uuid4())

        model = ResourceModel(
            id=resource.id,
            filename=resource.filename,
            original_path=resource.original_path,
            file_size=resource.file_size,
            mime_type=resource.mime_type,
            stored_path=resource.stored_path,
            status=resource.status.value,
            data_source_id=resource.data_source_id,
            extracted_text=resource.extracted_text,
            concept_id=resource.classification.primary_concept_id if resource.classification else None,
            concept_label=None,
            classification_confidence=resource.classification.confidence if resource.classification else None,
            classification_signals=self._signals_to_json(resource.classification) if resource.classification else None,
            metadata_=resource.metadata,
            extra_fields=resource.extra_fields,
            summary=resource.summary,
            language=resource.language,
            processing_time_ms=resource.processing_time_ms,
            origin_file_id=resource.origin_file_id,
            page_range=resource.page_range,
            uploaded_at=resource.uploaded_at,
            processed_at=resource.processed_at,
            error_message=resource.error_message,
        )

        self._session.add(model)
        await self._session.flush()
        return resource

    async def update(self, resource: Resource) -> Resource:
        result = await self._session.execute(
            select(ResourceModel).where(ResourceModel.id == resource.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Resource with id {resource.id} not found")

        # Core fields
        model.status = resource.status.value
        model.extracted_text = resource.extracted_text
        model.processed_at = resource.processed_at
        model.error_message = resource.error_message
        model.data_source_id = resource.data_source_id

        # Classification (flat columns)
        if resource.classification:
            model.concept_id = resource.classification.primary_concept_id
            model.classification_confidence = resource.classification.confidence
            model.classification_signals = self._signals_to_json(resource.classification)

        # Metadata (JSONB — direct assignment)
        if resource.metadata:
            model.metadata_ = resource.metadata
        if resource.extra_fields:
            model.extra_fields = resource.extra_fields

        # Summary
        if resource.summary is not None:
            model.summary = resource.summary
        if resource.language is not None:
            model.language = resource.language
        if resource.processing_time_ms is not None:
            model.processing_time_ms = resource.processing_time_ms

        await self._session.flush()
        return resource

    async def delete(self, resource_id: str) -> bool:
        result = await self._session.execute(
            select(ResourceModel).where(ResourceModel.id == resource_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def delete_by_source(self, source_id: str) -> int:
        result = await self._session.execute(
            select(ResourceModel).where(ResourceModel.data_source_id == source_id)
        )
        models = result.scalars().all()
        count = len(models)
        for model in models:
            await self._session.delete(model)
        if count > 0:
            await self._session.flush()
        return count

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(ResourceModel)
        )
        return result.scalar_one()

    async def search(
        self,
        concept_ids: list[str] | None = None,
        metadata_filters: list["MetadataFilter"] | None = None,
        text_query: str | None = None,
        limit: int = 50,
    ) -> list[Resource]:
        stmt = select(ResourceModel).where(
            ResourceModel.status == "done"
        )

        if concept_ids:
            stmt = stmt.where(ResourceModel.concept_id.in_(concept_ids))

        if metadata_filters:
            for mf in metadata_filters:
                field_col = ResourceModel.metadata_[mf.field_name]

                if mf.operator == "equals":
                    # Exact match on scalar values and ref labels.
                    target = str(mf.value).strip().lower()
                    scalar_val = func.lower(field_col["value"].as_string())
                    label_val = func.lower(field_col["value"]["label"].as_string())
                    stmt = stmt.where(
                        (scalar_val == target) | (label_val == target)
                    )

                elif mf.operator in ("gte", "lte"):
                    # Numeric comparison: cast the JSONB value to float
                    raw_target = str(mf.value).strip()
                    numeric_val = func.cast(field_col["value"].as_string(), Float)
                    try:
                        target = float(raw_target)
                    except (ValueError, TypeError):
                        # Fallback for ISO dates (YYYY-MM-DD): lexical compare is valid.
                        if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw_target):
                            continue  # skip unsupported filters
                        date_val = field_col["value"].as_string()
                        if mf.operator == "gte":
                            stmt = stmt.where(date_val >= raw_target)
                        else:
                            stmt = stmt.where(date_val <= raw_target)
                        continue

                    if mf.operator == "gte":
                        stmt = stmt.where(numeric_val >= target)
                    else:
                        stmt = stmt.where(numeric_val <= target)

                else:
                    # Default: "contains" — case-insensitive partial match.
                    pattern = f"%{mf.value}%"
                    scalar_val = field_col["value"].as_string()
                    label_val = field_col["value"]["label"].as_string()
                    full_text = func.cast(field_col, Text)

                    stmt = stmt.where(
                        scalar_val.ilike(pattern)
                        | label_val.ilike(pattern)
                        | full_text.ilike(pattern)
                    )

        if text_query:
            pattern = f"%{text_query}%"
            stmt = stmt.where(
                ResourceModel.extracted_text.ilike(pattern)
                | ResourceModel.summary.ilike(pattern)
                | ResourceModel.filename.ilike(pattern)
            )

        stmt = stmt.order_by(
            ResourceModel.classification_confidence.desc().nulls_last()
        ).limit(limit)

        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

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

    def _to_domain(self, model: ResourceModel) -> Resource:
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

        return Resource(
            id=model.id,
            filename=model.filename,
            original_path=model.original_path,
            file_size=model.file_size,
            mime_type=model.mime_type,
            stored_path=model.stored_path,
            status=ProcessingStatus(model.status),
            data_source_id=model.data_source_id,
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
