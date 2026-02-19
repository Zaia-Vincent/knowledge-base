"""Data Sources API controller — CRUD, job submission, and SSE streaming."""

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.application.schemas.data_source import (
    CreateDataSourceRequest,
    DataSourceResponse,
    ProcessFilesRequest,
    ProcessingJobResponse,
    SourceFileEntry,
    SourceFilesResponse,
    SourceUrlsResponse,
    SubmitJobsResponse,
    SubmitUrlsRequest,
    UpdateSourceUrlsRequest,
    UploadFilesResponse,
)
from app.application.services.data_source_service import DataSourceService
from app.application.services.sse_manager import SSEManager
from app.infrastructure.dependencies import get_data_source_service, get_sse_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])


# ── Helpers ──────────────────────────────────────────────────────────


def _source_to_response(source) -> DataSourceResponse:
    """Map a DataSource domain entity to its API response."""
    return DataSourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        description=source.description,
        config=source.config,
        created_at=source.created_at.isoformat(),
        updated_at=source.updated_at.isoformat(),
    )


def _job_to_response(job) -> ProcessingJobResponse:
    """Map a ProcessingJob domain entity to its API response."""
    return ProcessingJobResponse(
        id=job.id,
        data_source_id=job.data_source_id,
        resource_identifier=job.resource_identifier,
        resource_type=job.resource_type,
        status=job.status,
        progress_message=job.progress_message,
        result_file_id=job.result_file_id,
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


# ── Data Source CRUD ─────────────────────────────────────────────────


@router.post("/", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    request: CreateDataSourceRequest,
    service: DataSourceService = Depends(get_data_source_service),
) -> DataSourceResponse:
    """Create a new data source."""
    source = await service.create_source(
        name=request.name,
        source_type=request.source_type,
        description=request.description,
        config=request.config,
    )
    return _source_to_response(source)


@router.get("/", response_model=list[DataSourceResponse])
async def list_sources(
    service: DataSourceService = Depends(get_data_source_service),
) -> list[DataSourceResponse]:
    """List all registered data sources."""
    sources = await service.list_sources()
    return [_source_to_response(s) for s in sources]


@router.get("/{source_id}", response_model=DataSourceResponse)
async def get_source(
    source_id: str,
    service: DataSourceService = Depends(get_data_source_service),
) -> DataSourceResponse:
    """Get a single data source by ID."""
    source = await service.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return _source_to_response(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    service: DataSourceService = Depends(get_data_source_service),
) -> None:
    """Delete a data source and all its jobs."""
    deleted = await service.delete_source(source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Data source not found")


# ── URL Management ───────────────────────────────────────────────────


@router.get("/{source_id}/urls", response_model=SourceUrlsResponse)
async def get_source_urls(
    source_id: str,
    service: DataSourceService = Depends(get_data_source_service),
) -> SourceUrlsResponse:
    """Get stored URLs for a website data source."""
    try:
        urls = await service.get_source_urls(source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SourceUrlsResponse(source_id=source_id, urls=urls)


@router.put("/{source_id}/urls", response_model=SourceUrlsResponse)
async def update_source_urls(
    source_id: str,
    request: UpdateSourceUrlsRequest,
    service: DataSourceService = Depends(get_data_source_service),
) -> SourceUrlsResponse:
    """Replace stored URLs for a website data source."""
    try:
        urls = await service.update_source_urls(source_id, request.urls)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SourceUrlsResponse(source_id=source_id, urls=urls)


# ── Job Submission ───────────────────────────────────────────────────


@router.post("/{source_id}/upload", response_model=UploadFilesResponse)
async def upload_files(
    source_id: str,
    files: list[UploadFile],
    service: DataSourceService = Depends(get_data_source_service),
) -> UploadFilesResponse:
    """Upload files to a file_upload data source (store only, no processing)."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    file_data: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        file_data.append((f.filename or "unnamed", content))

    try:
        entries = await service.store_files(source_id, file_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return UploadFilesResponse(
        source_id=source_id,
        uploaded=[SourceFileEntry(**e) for e in entries],
        message=f"Uploaded {len(entries)} file(s)",
    )


@router.get("/{source_id}/files", response_model=SourceFilesResponse)
async def get_files(
    source_id: str,
    service: DataSourceService = Depends(get_data_source_service),
) -> SourceFilesResponse:
    """List stored files for a file_upload data source."""
    try:
        entries = await service.get_source_files(source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SourceFilesResponse(
        source_id=source_id,
        files=[SourceFileEntry(**e) for e in entries],
    )


@router.delete("/{source_id}/files", response_model=SourceFilesResponse)
async def remove_file(
    source_id: str,
    stored_path: str,
    service: DataSourceService = Depends(get_data_source_service),
) -> SourceFilesResponse:
    """Remove a stored file from a file_upload data source."""
    try:
        entries = await service.remove_source_file(source_id, stored_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SourceFilesResponse(
        source_id=source_id,
        files=[SourceFileEntry(**e) for e in entries],
    )


@router.post("/{source_id}/process-files", response_model=SubmitJobsResponse)
async def process_files(
    source_id: str,
    body: ProcessFilesRequest,
    service: DataSourceService = Depends(get_data_source_service),
) -> SubmitJobsResponse:
    """Create processing jobs for selected stored files."""
    try:
        jobs = await service.process_files(source_id, body.stored_paths)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SubmitJobsResponse(
        jobs=[_job_to_response(j) for j in jobs],
        message=f"Submitted {len(jobs)} file(s) for processing",
    )


@router.post("/{source_id}/submit-urls", response_model=SubmitJobsResponse)
async def submit_urls(
    source_id: str,
    request: SubmitUrlsRequest,
    service: DataSourceService = Depends(get_data_source_service),
) -> SubmitJobsResponse:
    """Submit website URLs for a website data source for background processing."""
    try:
        jobs = await service.submit_urls(source_id, request.urls)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SubmitJobsResponse(
        jobs=[_job_to_response(j) for j in jobs],
        message=f"Submitted {len(jobs)} URL(s) for processing",
    )


# ── Job Listing ──────────────────────────────────────────────────────


@router.get("/{source_id}/jobs", response_model=list[ProcessingJobResponse])
async def list_jobs_for_source(
    source_id: str,
    service: DataSourceService = Depends(get_data_source_service),
) -> list[ProcessingJobResponse]:
    """List processing jobs for a specific data source."""
    jobs = await service.list_jobs(source_id=source_id)
    return [_job_to_response(j) for j in jobs]


@router.get("/jobs/all", response_model=list[ProcessingJobResponse])
async def list_all_jobs(
    service: DataSourceService = Depends(get_data_source_service),
) -> list[ProcessingJobResponse]:
    """List all processing jobs across all data sources."""
    jobs = await service.list_jobs()
    return [_job_to_response(j) for j in jobs]


# ── Job Actions ──────────────────────────────────────────────────────


@router.post("/jobs/{job_id}/restart", response_model=ProcessingJobResponse)
async def restart_job(
    job_id: str,
    service: DataSourceService = Depends(get_data_source_service),
) -> ProcessingJobResponse:
    """Restart a completed or failed job — resets to queued, deletes old results."""
    try:
        job = await service.restart_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _job_to_response(job)


# ── SSE Stream ───────────────────────────────────────────────────────


@router.get("/jobs/stream")
async def job_status_stream(
    sse: SSEManager = Depends(get_sse_manager),
) -> StreamingResponse:
    """SSE endpoint for real-time processing job status updates.

    Clients connect via EventSource and receive 'job_update' events
    as background jobs progress through their lifecycle.
    """
    return StreamingResponse(
        sse.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
