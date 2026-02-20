/**
 * API client for data sources and processing jobs endpoints.
 */

import { apiClient } from './api-client';
import type {
    DataSource,
    CreateDataSourceRequest,
    ProcessFilesRequest,
    ProcessTextsRequest,
    ProcessingJob,
    SourceFilesResponse,
    SourceTextsResponse,
    SourceUrlsResponse,
    SubmitJobsResponse,
    SubmitTextRequest,
    SubmitUrlsRequest,
    UpdateSourceUrlsRequest,
    UploadFilesResponse,
} from '@/types/data-sources';

const BASE = '/data-sources';

export const dataSourcesApi = {
    // ── Data Source CRUD ─────────────────────────────────────────────

    /** Create a new data source. */
    create(data: CreateDataSourceRequest): Promise<DataSource> {
        return apiClient.post<DataSource>(`${BASE}/`, data);
    },

    /** List all data sources. */
    list(): Promise<DataSource[]> {
        return apiClient.get<DataSource[]>(`${BASE}/`);
    },

    /** Get a single data source by ID. */
    getById(id: string): Promise<DataSource> {
        return apiClient.get<DataSource>(`${BASE}/${id}`);
    },

    /** Delete a data source and all its jobs. */
    delete(id: string): Promise<void> {
        return apiClient.delete(`${BASE}/${id}`);
    },

    // ── Job Submission ──────────────────────────────────────────────

    /** Upload files to a file_upload data source (store only, no processing). */
    async uploadFiles(sourceId: string, files: File[]): Promise<UploadFilesResponse> {
        const form = new FormData();
        files.forEach((f) => form.append('files', f));

        const response = await fetch(
            `${import.meta.env.VITE_API_BASE_URL ?? '/api/v1'}${BASE}/${sourceId}/upload`,
            { method: 'POST', body: form },
        );

        if (!response.ok) {
            const data = await response.json().catch(() => undefined);
            throw new Error(data?.detail ?? `Upload failed: ${response.statusText}`);
        }

        return response.json();
    },

    /** Submit website URLs for processing. */
    submitUrls(sourceId: string, request: SubmitUrlsRequest): Promise<SubmitJobsResponse> {
        return apiClient.post<SubmitJobsResponse>(`${BASE}/${sourceId}/submit-urls`, request);
    },

    // ── Job Queries ─────────────────────────────────────────────────

    /** List processing jobs for a specific data source. */
    listJobsForSource(sourceId: string): Promise<ProcessingJob[]> {
        return apiClient.get<ProcessingJob[]>(`${BASE}/${sourceId}/jobs`);
    },

    /** List all processing jobs across all data sources. */
    listAllJobs(): Promise<ProcessingJob[]> {
        return apiClient.get<ProcessingJob[]>(`${BASE}/jobs/all`);
    },

    /** Restart a completed or failed processing job. */
    restartJob(jobId: string): Promise<ProcessingJob> {
        return apiClient.post<ProcessingJob>(`${BASE}/jobs/${jobId}/restart`);
    },

    // ── URL Management ──────────────────────────────────────────────

    /** Get stored URLs for a website data source. */
    getUrls(sourceId: string): Promise<SourceUrlsResponse> {
        return apiClient.get<SourceUrlsResponse>(`${BASE}/${sourceId}/urls`);
    },

    /** Replace stored URLs for a website data source. */
    updateUrls(sourceId: string, request: UpdateSourceUrlsRequest): Promise<SourceUrlsResponse> {
        return apiClient.put<SourceUrlsResponse>(`${BASE}/${sourceId}/urls`, request);
    },

    // ── File Management ─────────────────────────────────────────────

    /** Get stored files for a file_upload data source. */
    getFiles(sourceId: string): Promise<SourceFilesResponse> {
        return apiClient.get<SourceFilesResponse>(`${BASE}/${sourceId}/files`);
    },

    /** Remove a stored file from a file_upload data source. */
    removeFile(sourceId: string, storedPath: string): Promise<SourceFilesResponse> {
        return apiClient.delete<SourceFilesResponse>(`${BASE}/${sourceId}/files?stored_path=${encodeURIComponent(storedPath)}`);
    },

    /** Process selected stored files. */
    processFiles(sourceId: string, request: ProcessFilesRequest): Promise<SubmitJobsResponse> {
        return apiClient.post<SubmitJobsResponse>(`${BASE}/${sourceId}/process-files`, request);
    },

    // ── Text Management ─────────────────────────────────────────────

    /** Get stored text entries for a text data source. */
    getTexts(sourceId: string): Promise<SourceTextsResponse> {
        return apiClient.get<SourceTextsResponse>(`${BASE}/${sourceId}/texts`);
    },

    /** Add a new text entry to a text data source. */
    addText(sourceId: string, request: SubmitTextRequest): Promise<SourceTextsResponse> {
        return apiClient.post<SourceTextsResponse>(`${BASE}/${sourceId}/texts`, request);
    },

    /** Remove a text entry from a text data source. */
    removeText(sourceId: string, textId: string): Promise<SourceTextsResponse> {
        return apiClient.delete<SourceTextsResponse>(`${BASE}/${sourceId}/texts?text_id=${encodeURIComponent(textId)}`);
    },

    /** Process selected text entries. */
    processTexts(sourceId: string, request: ProcessTextsRequest): Promise<SubmitJobsResponse> {
        return apiClient.post<SubmitJobsResponse>(`${BASE}/${sourceId}/process-texts`, request);
    },
};

/**
 * Returns the SSE stream URL for real-time job status updates.
 */
export function getJobStreamUrl(): string {
    const base = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
    return `${base}${BASE}/jobs/stream`;
}

