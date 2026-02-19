/**
 * API client for browsing processed resources.
 * Talks to the /api/v1/resources endpoint.
 */

import { apiClient } from './api-client';
import type { ResourceSummary, ResourceDetail } from '@/types/resources';

const BASE = '/resources';

export const resourcesApi = {
    /** List processed resources with optional pagination. */
    list(skip = 0, limit = 500): Promise<ResourceSummary[]> {
        return apiClient.get<ResourceSummary[]>(`${BASE}?skip=${skip}&limit=${limit}`);
    },

    /** Get full detail for a single resource. */
    getById(id: string): Promise<ResourceDetail> {
        return apiClient.get<ResourceDetail>(`${BASE}/${id}`);
    },

    /** Get total count of processed resources. */
    async count(): Promise<number> {
        const data = await apiClient.get<{ count: number }>(`${BASE}/count`);
        return data.count;
    },

    /** Delete a resource (file + DB record). */
    delete(id: string): Promise<void> {
        return apiClient.delete(`${BASE}/${id}`);
    },

    /** Reprocess a resource — re-run the full processing pipeline. */
    reprocess(id: string): Promise<ResourceDetail> {
        return apiClient.post<ResourceDetail>(`${BASE}/${id}/reprocess`);
    },
};
