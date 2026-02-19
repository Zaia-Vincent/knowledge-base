/**
 * TypeScript types for the data sources and processing jobs module.
 * Mirrors backend Pydantic schemas in data_source.py.
 */

export type DataSourceType = 'file_upload' | 'website';

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed';

export interface DataSource {
    id: string;
    name: string;
    source_type: DataSourceType;
    description: string;
    config: Record<string, unknown>;
    created_at: string;
    updated_at: string;
}

export interface CreateDataSourceRequest {
    name: string;
    source_type: DataSourceType;
    description?: string;
    config?: Record<string, unknown>;
}

export interface ProcessingJob {
    id: string;
    data_source_id: string;
    resource_identifier: string;
    resource_type: string;
    status: JobStatus;
    progress_message: string | null;
    result_file_id: string | null;
    error_message: string | null;
    created_at: string;
    started_at: string | null;
    completed_at: string | null;
}

export interface SubmitUrlsRequest {
    urls: string[];
}

export interface UpdateSourceUrlsRequest {
    urls: string[];
}

export interface SourceUrlsResponse {
    source_id: string;
    urls: string[];
}

export interface SourceFileEntry {
    stored_path: string;
    filename: string;
    file_size: number;
    mime_type: string;
}

export interface SourceFilesResponse {
    source_id: string;
    files: SourceFileEntry[];
}

export interface ProcessFilesRequest {
    stored_paths: string[];
}

export interface UploadFilesResponse {
    source_id: string;
    uploaded: SourceFileEntry[];
    message: string;
}

export interface SubmitJobsResponse {
    jobs: ProcessingJob[];
    message: string;
}

/** SSE event payload for real-time job updates */
export interface JobUpdateEvent {
    id: string;
    data_source_id: string;
    resource_identifier: string;
    resource_type: string;
    status: JobStatus;
    progress_message: string | null;
    result_file_id: string | null;
    error_message: string | null;
    started_at: string | null;
    completed_at: string | null;
}
