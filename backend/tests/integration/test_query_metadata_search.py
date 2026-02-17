"""Integration tests for metadata-based query filtering on processed files."""

import uuid

import pytest
from sqlalchemy import delete

from app.domain.entities import (
    ClassificationResult,
    ProcessedFile,
    ProcessingStatus,
)
from app.domain.entities.query import MetadataFilter
from app.infrastructure.database import Base, engine
from app.infrastructure.database.models.file_models import ProcessedFileModel
from app.infrastructure.database.repositories.file_repository import SQLAlchemyFileRepository
from app.infrastructure.database.session import async_session_factory


@pytest.mark.asyncio
async def test_search_matches_reference_vendor_for_contains_and_equals():
    """Vendor reference metadata should be queryable via contains and equals."""
    try:
        await _ensure_tables()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL not reachable in this environment: {exc}")

    created_ids: list[str] = []
    async with async_session_factory() as session:
        repo = SQLAlchemyFileRepository(session)
        try:
            deli_id = str(uuid.uuid4())
            other_id = str(uuid.uuid4())
            created_ids.extend([deli_id, other_id])

            await repo.create(
                ProcessedFile(
                    id=deli_id,
                    filename="invoice_deli.pdf",
                    original_path="/tmp/invoice_deli.pdf",
                    file_size=1024,
                    mime_type="application/pdf",
                    stored_path="/tmp/invoice_deli.pdf",
                    status=ProcessingStatus.DONE,
                    classification=ClassificationResult(
                        primary_concept_id="Invoice",
                        confidence=0.99,
                        signals=[],
                    ),
                    metadata={
                        "vendor": {
                            "value": {"label": "Deli Tyres bv"},
                            "confidence": 1.0,
                        },
                        "document_number": {"value": "2408484", "confidence": 1.0},
                    },
                    summary="Invoice from Deli Tyres bv",
                )
            )
            await repo.create(
                ProcessedFile(
                    id=other_id,
                    filename="invoice_other.pdf",
                    original_path="/tmp/invoice_other.pdf",
                    file_size=1024,
                    mime_type="application/pdf",
                    stored_path="/tmp/invoice_other.pdf",
                    status=ProcessingStatus.DONE,
                    classification=ClassificationResult(
                        primary_concept_id="Invoice",
                        confidence=0.95,
                        signals=[],
                    ),
                    metadata={
                        "vendor": {
                            "value": {"label": "Another Vendor"},
                            "confidence": 1.0,
                        },
                        "document_number": {"value": "999", "confidence": 1.0},
                    },
                    summary="Invoice from another vendor",
                )
            )
            await session.commit()

            contains_results = await repo.search(
                concept_ids=["Invoice"],
                metadata_filters=[
                    MetadataFilter(field_name="vendor", value="Deli", operator="contains")
                ],
                limit=20,
            )
            contains_ids = {f.id for f in contains_results}
            assert deli_id in contains_ids
            assert other_id not in contains_ids

            equals_results = await repo.search(
                concept_ids=["Invoice"],
                metadata_filters=[
                    MetadataFilter(
                        field_name="vendor",
                        value="Deli Tyres bv",
                        operator="equals",
                    )
                ],
                limit=20,
            )
            equals_ids = {f.id for f in equals_results}
            assert deli_id in equals_ids
            assert other_id not in equals_ids
        finally:
            await session.execute(
                delete(ProcessedFileModel).where(ProcessedFileModel.id.in_(created_ids))
            )
            await session.commit()


async def _ensure_tables() -> None:
    """Create DB tables for integration tests when needed."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
