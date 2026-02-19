"""Resources API controller — upload and query processed resources."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.application.schemas.resources import (
    ClassificationResultSchema,
    ClassificationSignalSchema,
    ExtraFieldSchema,
    MetadataFieldSchema,
    ResourceDetailSchema,
    ResourceSummarySchema,
    ResourceUploadResultSchema,
)
from app.application.services.resource_processing_service import ResourceProcessingService
from app.domain.entities import Resource
from app.infrastructure.dependencies import get_resource_processing_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resources", tags=["resources"])


# ── Helpers ──────────────────────────────────────────────────────────

def _extract_display_name(resource: Resource) -> str | None:
    """Build a UI-friendly row name from extracted metadata when available."""
    if not resource.metadata:
        return None

    label_entry = resource.metadata.get("label")
    if not isinstance(label_entry, dict):
        return None

    value = label_entry.get("value")
    if isinstance(value, str) and value.strip():
        return value.strip()

    if isinstance(value, dict):
        nested_label = value.get("label")
        if isinstance(nested_label, str) and nested_label.strip():
            return nested_label.strip()

    return None


def _to_summary(resource: Resource) -> ResourceSummarySchema:
    return ResourceSummarySchema(
        id=resource.id,
        filename=resource.filename,
        display_name=_extract_display_name(resource),
        original_path=resource.original_path,
        file_size=resource.file_size,
        mime_type=resource.mime_type,
        status=resource.status.value,
        classification_concept_id=resource.classification.primary_concept_id if resource.classification else None,
        classification_confidence=resource.classification.confidence if resource.classification else None,
        concept_label=None,  # Will be populated when concept labels are available
        origin_file_id=resource.origin_file_id,
        page_range=resource.page_range,
        data_source_id=resource.data_source_id,
        data_source_name=None,
        uploaded_at=resource.uploaded_at.isoformat(),
        processed_at=resource.processed_at.isoformat() if resource.processed_at else None,
        error_message=resource.error_message,
    )


def _to_detail(resource: Resource) -> ResourceDetailSchema:
    classification = None
    if resource.classification:
        classification = ClassificationResultSchema(
            primary_concept_id=resource.classification.primary_concept_id,
            confidence=resource.classification.confidence,
            signals=[
                ClassificationSignalSchema(
                    method=s.method,
                    concept_id=s.concept_id,
                    score=s.score,
                    details=s.details,
                )
                for s in resource.classification.signals
            ],
        )

    # Preview: first 2000 chars of extracted text
    text_preview = None
    if resource.extracted_text:
        text_preview = resource.extracted_text[:2000] + ("..." if len(resource.extracted_text) > 2000 else "")

    # Map metadata dict to MetadataFieldSchema
    metadata_schemas: dict[str, MetadataFieldSchema] = {}
    for key, entry in (resource.metadata or {}).items():
        if isinstance(entry, dict):
            metadata_schemas[key] = MetadataFieldSchema(**entry)
        else:
            metadata_schemas[key] = MetadataFieldSchema(value=entry)

    # Map extra_fields list to ExtraFieldSchema
    extra_field_schemas = [
        ExtraFieldSchema(**ef) for ef in (resource.extra_fields or []) if isinstance(ef, dict)
    ]

    return ResourceDetailSchema(
        id=resource.id,
        filename=resource.filename,
        original_path=resource.original_path,
        file_size=resource.file_size,
        mime_type=resource.mime_type,
        status=resource.status.value,
        extracted_text_preview=text_preview,
        classification=classification,
        metadata=metadata_schemas,
        extra_fields=extra_field_schemas,
        summary=resource.summary,
        language=resource.language,
        processing_time_ms=resource.processing_time_ms,
        data_source_id=resource.data_source_id,
        data_source_name=None,
        uploaded_at=resource.uploaded_at.isoformat(),
        processed_at=resource.processed_at.isoformat() if resource.processed_at else None,
        error_message=resource.error_message,
    )


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/upload", response_model=ResourceUploadResultSchema)
async def upload_resources(
    files: list[UploadFile],
    service: ResourceProcessingService = Depends(get_resource_processing_service),
):
    """Upload one or more files for processing."""
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    all_processed: list[Resource] = []

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

    return ResourceUploadResultSchema(
        resources=[_to_summary(r) for r in all_processed],
        total_count=len(all_processed),
        message=f"Successfully uploaded {len(all_processed)} resource(s)",
    )


@router.post("/upload-zip", response_model=ResourceUploadResultSchema)
async def upload_zip(
    file: UploadFile,
    service: ResourceProcessingService = Depends(get_resource_processing_service),
):
    """Upload a ZIP archive — extracts and processes all contained files."""
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected a .zip file",
        )

    content = await file.read()
    processed = await service.upload_zip(content, file.filename)

    return ResourceUploadResultSchema(
        resources=[_to_summary(r) for r in processed],
        total_count=len(processed),
        message=f"Extracted and uploaded {len(processed)} resource(s) from {file.filename}",
    )


@router.get("", response_model=list[ResourceSummarySchema])
async def list_resources(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    service: ResourceProcessingService = Depends(get_resource_processing_service),
):
    """List all processed resources with pagination."""
    resources = await service.list_resources(skip=skip, limit=limit)
    return [_to_summary(r) for r in resources]


@router.get("/count")
async def get_resource_count(
    service: ResourceProcessingService = Depends(get_resource_processing_service),
):
    """Get the total number of processed resources."""
    count = await service.get_resource_count()
    return {"count": count}


@router.get("/{resource_id}", response_model=ResourceDetailSchema)
async def get_resource(
    resource_id: str,
    service: ResourceProcessingService = Depends(get_resource_processing_service),
):
    """Get detailed information about a single processed resource."""
    resource = await service.get_resource(resource_id)
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return _to_detail(resource)


@router.get("/{resource_id}/download")
async def download_resource(
    resource_id: str,
    service: ResourceProcessingService = Depends(get_resource_processing_service),
):
    """Download the original uploaded file."""
    resource = await service.get_resource(resource_id)
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    from pathlib import Path

    file_path = Path(resource.stored_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File no longer exists on disk")

    return FileResponse(
        path=str(file_path),
        filename=resource.filename,
        media_type=resource.mime_type,
    )


@router.post("/{resource_id}/reprocess")
async def reprocess_resource(
    resource_id: str,
    service: ResourceProcessingService = Depends(get_resource_processing_service),
):
    """Re-run the processing pipeline for an existing resource."""
    try:
        resource = await service.reprocess_resource(resource_id)
        return _to_detail(resource)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Reprocessing failed for resource %s", resource_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reprocessing failed: {e}",
        )


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: str,
    service: ResourceProcessingService = Depends(get_resource_processing_service),
):
    """Delete a resource — removes both the stored file and database record(s)."""
    deleted = await service.delete_resource(resource_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
