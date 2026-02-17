/**
 * API client for query endpoints.
 */

import { apiClient } from './api-client';
import type { QueryRequest, QueryResult, QueryIntent } from '@/types/query';

const BASE = '/query';

export const queryApi = {
    /** Execute a full query: NL question → intent + search results. */
    submit(request: QueryRequest): Promise<QueryResult> {
        return apiClient.post<QueryResult>(BASE, request);
    },

    /** Resolve intent only (no search) — useful for debugging. */
    resolveIntent(request: QueryRequest): Promise<QueryIntent> {
        return apiClient.post<QueryIntent>(`${BASE}/intent`, request);
    },
};
