/**
 * API client for ontology management endpoints.
 */

import { apiClient } from './api-client';
import type {
    ConceptDetail,
    ConceptSummary,
    ConceptTreeNode,
    CreateConceptPayload,
    OntologyStats,
} from '@/types/ontology';

const BASE = '/ontology';

export const ontologyApi = {
    /** Fetch the full ontology tree hierarchy. */
    getTree(): Promise<ConceptTreeNode[]> {
        return apiClient.get<ConceptTreeNode[]>(`${BASE}/tree`);
    },

    /** Fetch ontology statistics. */
    getStats(): Promise<OntologyStats> {
        return apiClient.get<OntologyStats>(`${BASE}/stats`);
    },

    /** Get detailed info for a specific concept. */
    getConcept(id: string): Promise<ConceptDetail> {
        return apiClient.get<ConceptDetail>(`${BASE}/concepts/${id}`);
    },

    /** List all concepts with optional filters. */
    listConcepts(params?: { layer?: string; pillar?: string }): Promise<ConceptSummary[]> {
        const query = new URLSearchParams();
        if (params?.layer) query.set('layer', params.layer);
        if (params?.pillar) query.set('pillar', params.pillar);
        const qs = query.toString();
        return apiClient.get<ConceptSummary[]>(`${BASE}/concepts${qs ? `?${qs}` : ''}`);
    },

    /** Search concepts by label, synonym, or hint. */
    search(q: string): Promise<ConceptSummary[]> {
        return apiClient.get<ConceptSummary[]>(`${BASE}/search?q=${encodeURIComponent(q)}`);
    },

    /** Create a new L3 concept. */
    createConcept(data: CreateConceptPayload): Promise<ConceptDetail> {
        return apiClient.post<ConceptDetail>(`${BASE}/concepts`, data);
    },

    /** Delete an L3+ concept. */
    deleteConcept(id: string): Promise<void> {
        return apiClient.delete(`${BASE}/concepts/${id}`);
    },
};
