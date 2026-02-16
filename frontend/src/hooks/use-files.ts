/**
 * React hook for file processing operations.
 * Manages state for file listing, upload, and detail fetching.
 */

import { useCallback, useEffect, useState } from 'react';
import { filesApi } from '@/lib/files-api';
import type { ProcessedFileDetail, ProcessedFileSummary } from '@/types/files';

export function useFiles() {
    const [files, setFiles] = useState<ProcessedFileSummary[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [uploading, setUploading] = useState(false);

    const fetchFiles = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const data = await filesApi.list();
            setFiles(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load files');
        } finally {
            setLoading(false);
        }
    }, []);

    const uploadFiles = useCallback(
        async (fileList: File[]) => {
            try {
                setUploading(true);
                setError(null);
                const result = await filesApi.upload(fileList);
                // Refresh list after upload
                await fetchFiles();
                return result;
            } catch (e) {
                const msg = e instanceof Error ? e.message : 'Upload failed';
                setError(msg);
                throw e;
            } finally {
                setUploading(false);
            }
        },
        [fetchFiles],
    );

    const deleteFile = useCallback(
        async (fileId: string) => {
            try {
                setError(null);
                await filesApi.deleteFile(fileId);
                await fetchFiles();
            } catch (e) {
                const msg = e instanceof Error ? e.message : 'Delete failed';
                setError(msg);
                throw e;
            }
        },
        [fetchFiles],
    );

    useEffect(() => {
        fetchFiles();
    }, [fetchFiles]);

    return { files, loading, error, uploading, uploadFiles, deleteFile, refetch: fetchFiles };
}

export function useFileDetail(fileId: string | undefined) {
    const [file, setFile] = useState<ProcessedFileDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!fileId) return;

        let cancelled = false;

        async function load() {
            try {
                setLoading(true);
                setError(null);
                const data = await filesApi.getById(fileId!);
                if (!cancelled) setFile(data);
            } catch (e) {
                if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load file');
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        load();
        return () => { cancelled = true; };
    }, [fileId]);

    return { file, loading, error };
}
