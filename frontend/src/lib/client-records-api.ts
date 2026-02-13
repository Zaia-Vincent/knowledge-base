/**
 * Client Records API — typed functions for the generic data storage service.
 *
 * Uses the apiClient to communicate with /api/v1/client-records.
 */

import { apiClient } from '@/lib/api-client';

export interface ClientRecord<T = Record<string, unknown>> {
    id: string;
    module_name: string;
    entity_type: string;
    data: T;
    parent_id: string | null;
    user_id: string | null;
    created_at: string;
    updated_at: string;
}

interface CreateRecordPayload<T = Record<string, unknown>> {
    module_name: string;
    entity_type: string;
    data: T;
    parent_id?: string | null;
    user_id?: string | null;
}

interface UpdateRecordPayload<T = Record<string, unknown>> {
    data?: T;
    parent_id?: string | null;
}

const BASE = '/client-records';

export const clientRecordsApi = {
    /**
     * List records, optionally filtered by module_name, entity_type, etc.
     */
    list: <T = Record<string, unknown>>(params?: {
        module_name?: string;
        entity_type?: string;
        parent_id?: string;
        user_id?: string;
        skip?: number;
        limit?: number;
    }) => {
        const query = new URLSearchParams();
        if (params) {
            Object.entries(params).forEach(([k, v]) => {
                if (v !== undefined) query.set(k, String(v));
            });
        }
        const qs = query.toString();
        return apiClient.get<ClientRecord<T>[]>(`${BASE}${qs ? `?${qs}` : ''}`);
    },

    /**
     * Get a single record by ID.
     */
    getById: <T = Record<string, unknown>>(id: string) =>
        apiClient.get<ClientRecord<T>>(`${BASE}/${id}`),

    /**
     * Create a new record.
     */
    create: <T = Record<string, unknown>>(payload: CreateRecordPayload<T>) =>
        apiClient.post<ClientRecord<T>>(BASE, payload),

    /**
     * Update an existing record.
     */
    update: <T = Record<string, unknown>>(id: string, payload: UpdateRecordPayload<T>) =>
        apiClient.put<ClientRecord<T>>(`${BASE}/${id}`, payload),

    /**
     * Delete a record by ID.
     */
    delete: (id: string) => apiClient.delete<void>(`${BASE}/${id}`),
};
