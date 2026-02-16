/**
 * API client for file processing endpoints.
 */

import { apiClient } from './api-client';
import type { ProcessedFileDetail, ProcessedFileSummary, UploadResult } from '@/types/files';

const BASE = '/files';

export const filesApi = {
    /** Upload one or more files via multipart/form-data. */
    async upload(files: File[]): Promise<UploadResult> {
        const form = new FormData();
        files.forEach((f) => form.append('files', f));

        const response = await fetch(
            `${import.meta.env.VITE_API_BASE_URL ?? '/api/v1'}${BASE}/upload`,
            { method: 'POST', body: form },
        );

        if (!response.ok) {
            const data = await response.json().catch(() => undefined);
            throw new Error(data?.detail ?? `Upload failed: ${response.statusText}`);
        }

        return response.json();
    },

    /** List all processed files. */
    list(skip = 0, limit = 100): Promise<ProcessedFileSummary[]> {
        return apiClient.get<ProcessedFileSummary[]>(`${BASE}?skip=${skip}&limit=${limit}`);
    },

    /** Get full detail of a single file. */
    getById(id: string): Promise<ProcessedFileDetail> {
        return apiClient.get<ProcessedFileDetail>(`${BASE}/${id}`);
    },

    /** Get total file count. */
    getCount(): Promise<{ count: number }> {
        return apiClient.get<{ count: number }>(`${BASE}/count`);
    },

    /** Delete a processed file (removes file from disk + database). */
    deleteFile(id: string): Promise<void> {
        return apiClient.delete(`${BASE}/${id}`);
    },
};
