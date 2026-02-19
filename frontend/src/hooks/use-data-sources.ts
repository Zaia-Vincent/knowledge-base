/**
 * React hooks for data sources management.
 * Manages state for CRUD operations on data sources.
 */

import { useCallback, useEffect, useState } from 'react';
import { dataSourcesApi } from '@/lib/data-sources-api';
import type { DataSource, CreateDataSourceRequest } from '@/types/data-sources';

export function useDataSources() {
    const [sources, setSources] = useState<DataSource[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchSources = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await dataSourcesApi.list();
            setSources(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load data sources');
        } finally {
            setLoading(false);
        }
    }, []);

    const createSource = useCallback(
        async (request: CreateDataSourceRequest) => {
            try {
                setError(null);
                const source = await dataSourcesApi.create(request);
                await fetchSources();
                return source;
            } catch (e) {
                const msg = e instanceof Error ? e.message : 'Failed to create data source';
                setError(msg);
                throw e;
            }
        },
        [fetchSources],
    );

    const deleteSource = useCallback(
        async (sourceId: string) => {
            try {
                setError(null);
                await dataSourcesApi.delete(sourceId);
                await fetchSources();
            } catch (e) {
                const msg = e instanceof Error ? e.message : 'Failed to delete data source';
                setError(msg);
                throw e;
            }
        },
        [fetchSources],
    );

    useEffect(() => {
        fetchSources();
    }, [fetchSources]);

    return { sources, loading, error, createSource, deleteSource, refetch: fetchSources };
}
