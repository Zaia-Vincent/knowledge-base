"""Files API controller — upload and query processed files."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.application.schemas.files import (
    ClassificationResultSchema,
    ClassificationSignalSchema,
    ExtraFieldSchema,
    MetadataFieldSchema,
    ProcessedFileDetailSchema,
    ProcessedFileSummarySchema,
    UploadResultSchema,
)
from app.application.services.file_processing_service import FileProcessingService
from app.domain.entities import ProcessedFile
from app.infrastructure.dependencies import get_file_processing_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


# ── Helpers ──────────────────────────────────────────────────────────

def _to_summary(pf: ProcessedFile) -> ProcessedFileSummarySchema:
    return ProcessedFileSummarySchema(
        id=pf.id,
        filename=pf.filename,
        original_path=pf.original_path,
        file_size=pf.file_size,
        mime_type=pf.mime_type,
        status=pf.status.value,
        classification_concept_id=pf.classification.primary_concept_id if pf.classification else None,
        classification_confidence=pf.classification.confidence if pf.classification else None,
        concept_label=None,  # Will be populated when concept labels are available
        uploaded_at=pf.uploaded_at.isoformat(),
        processed_at=pf.processed_at.isoformat() if pf.processed_at else None,
        error_message=pf.error_message,
    )


def _to_detail(pf: ProcessedFile) -> ProcessedFileDetailSchema:
    classification = None
    if pf.classification:
        classification = ClassificationResultSchema(
            primary_concept_id=pf.classification.primary_concept_id,
            confidence=pf.classification.confidence,
            signals=[
                ClassificationSignalSchema(
                    method=s.method,
                    concept_id=s.concept_id,
                    score=s.score,
                    details=s.details,
                )
                for s in pf.classification.signals
            ],
        )

    # Preview: first 2000 chars of extracted text
    text_preview = None
    if pf.extracted_text:
        text_preview = pf.extracted_text[:2000] + ("..." if len(pf.extracted_text) > 2000 else "")

    # Map metadata dict to MetadataFieldSchema
    metadata_schemas: dict[str, MetadataFieldSchema] = {}
    for key, entry in (pf.metadata or {}).items():
        if isinstance(entry, dict):
            metadata_schemas[key] = MetadataFieldSchema(**entry)
        else:
            metadata_schemas[key] = MetadataFieldSchema(value=entry)

    # Map extra_fields list to ExtraFieldSchema
    extra_field_schemas = [
        ExtraFieldSchema(**ef) for ef in (pf.extra_fields or []) if isinstance(ef, dict)
    ]

    return ProcessedFileDetailSchema(
        id=pf.id,
        filename=pf.filename,
        original_path=pf.original_path,
        file_size=pf.file_size,
        mime_type=pf.mime_type,
        status=pf.status.value,
        extracted_text_preview=text_preview,
        classification=classification,
        metadata=metadata_schemas,
        extra_fields=extra_field_schemas,
        summary=pf.summary,
        language=pf.language,
        processing_time_ms=pf.processing_time_ms,
        uploaded_at=pf.uploaded_at.isoformat(),
        processed_at=pf.processed_at.isoformat() if pf.processed_at else None,
        error_message=pf.error_message,
    )


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResultSchema)
async def upload_files(
    files: list[UploadFile],
    service: FileProcessingService = Depends(get_file_processing_service),
):
    """Upload one or more files for processing."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    all_processed: list[ProcessedFile] = []

    for upload_file in files:
        content = await upload_file.read()
        if not content:
            continue

        # Check if it's a ZIP file
        if upload_file.content_type == "application/zip" or (
            upload_file.filename and upload_file.filename.lower().endswith(".zip")
        ):
            processed = await service.upload_zip(content, upload_file.filename or "archive.zip")
            all_processed.extend(processed)
        else:
            processed = await service.upload_file(content, upload_file.filename or "untitled")
            all_processed.append(processed)

    return UploadResultSchema(
        files=[_to_summary(pf) for pf in all_processed],
        total_count=len(all_processed),
        message=f"Successfully uploaded {len(all_processed)} file(s)",
    )


@router.post("/upload-zip", response_model=UploadResultSchema)
async def upload_zip(
    file: UploadFile,
    service: FileProcessingService = Depends(get_file_processing_service),
):
    """Upload a ZIP archive — extracts and processes all contained files."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected a .zip file",
        )

    content = await file.read()
    processed = await service.upload_zip(content, file.filename)

    return UploadResultSchema(
        files=[_to_summary(pf) for pf in processed],
        total_count=len(processed),
        message=f"Extracted and uploaded {len(processed)} file(s) from {file.filename}",
    )


@router.get("", response_model=list[ProcessedFileSummarySchema])
async def list_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: FileProcessingService = Depends(get_file_processing_service),
):
    """List all processed files with pagination."""
    files = await service.list_files(skip=skip, limit=limit)
    return [_to_summary(pf) for pf in files]


@router.get("/count")
async def get_file_count(
    service: FileProcessingService = Depends(get_file_processing_service),
):
    """Get the total number of processed files."""
    count = await service.get_file_count()
    return {"count": count}


@router.get("/{file_id}", response_model=ProcessedFileDetailSchema)
async def get_file(
    file_id: str,
    service: FileProcessingService = Depends(get_file_processing_service),
):
    """Get detailed information about a single processed file."""
    pf = await service.get_file(file_id)
    if pf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return _to_detail(pf)


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    service: FileProcessingService = Depends(get_file_processing_service),
):
    """Download the original uploaded file."""
    pf = await service.get_file(file_id)
    if pf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    from pathlib import Path

    file_path = Path(pf.stored_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File no longer exists on disk")

    return FileResponse(
        path=str(file_path),
        filename=pf.filename,
        media_type=pf.mime_type,
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    service: FileProcessingService = Depends(get_file_processing_service),
):
    """Delete a processed file — removes both the stored file and database record."""
    deleted = await service.delete_file(file_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
