"""Pydantic schemas for the data sources and processing jobs API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.entities.data_source import DataSourceType
from app.domain.entities.processing_job import JobStatus


# ── Data Source Schemas ──────────────────────────────────────────────


class CreateDataSourceRequest(BaseModel):
    """Request body for creating a new Data Source."""

    name: str = Field(min_length=1, max_length=255)
    source_type: DataSourceType
    description: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class DataSourceResponse(BaseModel):
    """Data Source representation returned to clients."""

    id: str
    name: str
    source_type: DataSourceType
    description: str
    config: dict[str, Any]
    created_at: str
    updated_at: str


class SubmitUrlsRequest(BaseModel):
    """Request body for submitting website URLs for processing."""

    urls: list[str] = Field(min_length=1)


class UpdateSourceUrlsRequest(BaseModel):
    """Request body for updating stored URLs on a website data source."""

    urls: list[str] = Field(default_factory=list)


class SourceUrlsResponse(BaseModel):
    """Response with stored URLs for a website data source."""

    source_id: str
    urls: list[str]


# ── File Management Schemas ──────────────────────────────────────────


class SourceFileEntry(BaseModel):
    """Metadata for a single stored file."""

    stored_path: str
    filename: str
    file_size: int
    mime_type: str


class SourceFilesResponse(BaseModel):
    """Response with stored files for a file_upload data source."""

    source_id: str
    files: list[SourceFileEntry]


class ProcessFilesRequest(BaseModel):
    """Request body for processing selected stored files."""

    stored_paths: list[str] = Field(min_length=1)


class UploadFilesResponse(BaseModel):
    """Response after uploading files (store-only, no processing)."""

    source_id: str
    uploaded: list[SourceFileEntry]
    message: str


# ── Text Management Schemas ──────────────────────────────────────────


class SubmitTextRequest(BaseModel):
    """Request body for adding a text entry to a text data source."""

    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1)


class SourceTextEntry(BaseModel):
    """Metadata for a single stored text entry."""

    id: str
    title: str
    content: str
    char_count: int
    created_at: str


class SourceTextsResponse(BaseModel):
    """Response with stored text entries for a text data source."""

    source_id: str
    texts: list[SourceTextEntry]


class ProcessTextsRequest(BaseModel):
    """Request body for processing selected stored text entries."""

    text_ids: list[str] = Field(min_length=1)


# ── Processing Job Schemas ───────────────────────────────────────────


class ProcessingJobResponse(BaseModel):
    """Processing Job representation returned to clients."""

    id: str
    data_source_id: str
    resource_identifier: str
    resource_type: str
    status: JobStatus
    progress_message: str | None = None
    result_file_id: str | None = None
    error_message: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class SubmitJobsResponse(BaseModel):
    """Response after submitting resources for processing."""

    jobs: list[ProcessingJobResponse]
    message: str
