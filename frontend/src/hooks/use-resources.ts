/**
 * React hooks for fetching processed resources.
 */

import { useCallback, useEffect, useState } from 'react';
import { resourcesApi } from '@/lib/resources-api';
import type { ResourceSummary, ResourceDetail } from '@/types/resources';

/** Fetch all processed resources. */
export function useResources() {
    const [resources, setResources] = useState<ResourceSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchResources = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await resourcesApi.list();
            setResources(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load resources');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchResources();
    }, [fetchResources]);

    return { resources, loading, error, refetch: fetchResources };
}

/** Fetch a single resource by ID. */
export function useResourceDetail(id: string | null) {
    const [resource, setResource] = useState<ResourceDetail | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchDetail = useCallback(async () => {
        if (!id) {
            setResource(null);
            return;
        }
        try {
            setLoading(true);
            setError(null);
            const data = await resourcesApi.getById(id);
            setResource(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load resource detail');
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => {
        fetchDetail();
    }, [fetchDetail]);

    return { resource, loading, error, refetch: fetchDetail };
}
