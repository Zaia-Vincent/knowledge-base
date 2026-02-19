/**
 * React hook for processing jobs with SSE real-time updates.
 * Connects to the backend's SSE endpoint and receives live job status changes.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { dataSourcesApi, getJobStreamUrl } from '@/lib/data-sources-api';
import type { JobUpdateEvent, ProcessingJob } from '@/types/data-sources';

export function useProcessingJobs(sourceId?: string) {
    const [jobs, setJobs] = useState<ProcessingJob[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const eventSourceRef = useRef<EventSource | null>(null);

    // ── Initial fetch ───────────────────────────────────────────────

    const fetchJobs = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = sourceId
                ? await dataSourcesApi.listJobsForSource(sourceId)
                : await dataSourcesApi.listAllJobs();
            setJobs(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load jobs');
        } finally {
            setLoading(false);
        }
    }, [sourceId]);

    // ── SSE real-time updates ───────────────────────────────────────

    useEffect(() => {
        fetchJobs();

        // Connect to the SSE stream
        const es = new EventSource(getJobStreamUrl());
        eventSourceRef.current = es;

        es.addEventListener('job_update', (event: MessageEvent) => {
            try {
                const update: JobUpdateEvent = JSON.parse(event.data);

                // Only apply if the job matches our current source filter (if any)
                if (sourceId && update.data_source_id !== sourceId) return;

                setJobs((prev) => {
                    const idx = prev.findIndex((j) => j.id === update.id);
                    const updatedJob: ProcessingJob = {
                        ...update,
                        created_at: idx >= 0 ? prev[idx].created_at : new Date().toISOString(),
                    };

                    if (idx >= 0) {
                        const next = [...prev];
                        next[idx] = updatedJob;
                        return next;
                    }
                    return [updatedJob, ...prev];
                });
            } catch {
                // Ignore malformed events
            }
        });

        es.onerror = () => {
            // EventSource auto-reconnects; no action needed
        };

        return () => {
            es.close();
            eventSourceRef.current = null;
        };
    }, [sourceId, fetchJobs]);

    // ── Restart a job ──────────────────────────────────────────────

    const restartJob = useCallback(async (jobId: string) => {
        try {
            const updated = await dataSourcesApi.restartJob(jobId);
            setJobs((prev) =>
                prev.map((j) => (j.id === jobId ? { ...j, ...updated } : j)),
            );
        } catch (e) {
            throw e instanceof Error ? e : new Error('Failed to restart job');
        }
    }, []);

    return { jobs, loading, error, refetch: fetchJobs, restartJob };
}
