/**
 * DataSourcesPage — Unified interface for managing data sources and monitoring processing.
 *
 * Tab 1: Data Sources — Master-detail view with source sidebar + context-dependent detail panel
 * Tab 2: Processing — Live processing overview powered by SSE
 */

import { useState, useCallback, useEffect } from 'react';
import {
    Database,
    Activity,
    RefreshCw,
    Plus,
    Trash2,
    Globe,
    FileUp,
    FileText,
    ExternalLink,
    CheckCircle2,
    XCircle,
    Loader2,
    Clock,
    RotateCcw,
    Upload,
    ChevronRight,
    Type,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useDataSources } from '@/hooks/use-data-sources';
import { useProcessingJobs } from '@/hooks/use-processing-jobs';
import { dataSourcesApi } from '@/lib/data-sources-api';
import type {
    DataSource,
    DataSourceType,
    JobStatus,
    ProcessingJob,
    SourceFileEntry,
    SourceTextEntry,
} from '@/types/data-sources';

/* ── Tab Navigation ──────────────────────────────────────────────── */

type TabId = 'sources' | 'processing';

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'sources', label: 'Data Sources', icon: <Database className="size-4" /> },
    { id: 'processing', label: 'Processing', icon: <Activity className="size-4" /> },
];

/* ── Page ─────────────────────────────────────────────────────────── */

export function DataSourcesPage() {
    const { sources, loading, error, createSource, deleteSource, refetch } = useDataSources();
    const { jobs, loading: jobsLoading, restartJob } = useProcessingJobs();
    const [activeTab, setActiveTab] = useState<TabId>('sources');

    const activeCount = jobs.filter((j) => j.status === 'queued' || j.status === 'processing').length;

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="px-6 pt-6 pb-2 shrink-0">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Data Sources</h1>
                        <p className="text-sm text-muted-foreground mt-1">
                            Manage file, website, and text data sources with background processing
                        </p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={refetch} disabled={loading} className="gap-2">
                        <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>

                {/* Tab bar */}
                <div className="flex items-center gap-1 border-b">
                    {TABS.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`
                                group relative flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors
                                ${activeTab === tab.id
                                    ? 'text-primary'
                                    : 'text-muted-foreground hover:text-foreground'
                                }
                            `}
                        >
                            {tab.icon}
                            {tab.label}

                            {tab.id === 'processing' && activeCount > 0 && (
                                <span className="flex items-center justify-center size-5 rounded-full bg-primary text-primary-foreground text-[10px] font-bold tabular-nums animate-pulse">
                                    {activeCount}
                                </span>
                            )}
                            {tab.id === 'sources' && sources.length > 0 && (
                                <span className="flex items-center justify-center min-w-[20px] h-5 px-1 rounded-full bg-muted text-muted-foreground text-[10px] font-bold tabular-nums">
                                    {sources.length}
                                </span>
                            )}

                            {activeTab === tab.id && (
                                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-t-full" />
                            )}
                        </button>
                    ))}
                </div>
            </div>

            {/* Tab content */}
            <div className="flex-1 min-h-0 px-6 py-4 overflow-y-auto">
                {error && (
                    <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                        {error}
                    </div>
                )}

                {activeTab === 'sources' && (
                    <SourcesPanel
                        sources={sources}
                        loading={loading}
                        onCreate={createSource}
                        onDelete={deleteSource}
                    />
                )}
                {activeTab === 'processing' && (
                    <ProcessingTab jobs={jobs} loading={jobsLoading} onRestart={restartJob} />
                )}
            </div>
        </div>
    );
}

/* ── Sources Panel (Master-Detail) ───────────────────────────────── */

function SourcesPanel({
    sources,
    loading,
    onCreate,
    onDelete,
}: {
    sources: DataSource[];
    loading: boolean;
    onCreate: (req: { name: string; source_type: DataSourceType; description?: string }) => Promise<unknown>;
    onDelete: (id: string) => Promise<void>;
}) {
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [showAddForm, setShowAddForm] = useState(false);

    // Auto-select first source when sources load
    useEffect(() => {
        if (sources.length > 0 && !selectedId) {
            setSelectedId(sources[0].id);
        }
    }, [sources, selectedId]);

    // Clear selection if source was deleted
    useEffect(() => {
        if (selectedId && !sources.find((s) => s.id === selectedId)) {
            setSelectedId(sources.length > 0 ? sources[0].id : null);
        }
    }, [sources, selectedId]);

    const selectedSource = sources.find((s) => s.id === selectedId) ?? null;

    const handleCreate = async (name: string, description: string, sourceType: DataSourceType) => {
        const source = await onCreate({ name, source_type: sourceType, description });
        setShowAddForm(false);
        if (source && typeof source === 'object' && 'id' in source) {
            setSelectedId((source as DataSource).id);
        }
    };

    const handleDelete = async (id: string) => {
        await onDelete(id);
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="flex gap-6 h-full min-h-[500px]">
            {/* ── Left: Source List ─────────────────────────────────── */}
            <div className="w-72 shrink-0 flex flex-col gap-2">
                {/* Source items */}
                <div className="flex-1 space-y-1.5 overflow-y-auto">
                    {sources.length === 0 && !showAddForm ? (
                        <div className="text-center py-8 text-muted-foreground">
                            <Database className="size-10 mx-auto mb-3 opacity-20" />
                            <p className="text-xs">No data sources yet.</p>
                            <p className="text-xs mt-1 opacity-70">Create your first source below.</p>
                        </div>
                    ) : (
                        sources.map((source) => (
                            <button
                                key={source.id}
                                onClick={() => setSelectedId(source.id)}
                                className={`
                                    w-full text-left rounded-xl border px-3.5 py-3 transition-all group
                                    ${selectedId === source.id
                                        ? 'border-primary/40 bg-primary/5 shadow-sm'
                                        : 'hover:bg-accent/50 hover:border-border/80'
                                    }
                                `}
                            >
                                <div className="flex items-center gap-2.5">
                                    <SourceTypeIcon type={source.source_type} size="sm" />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{source.name}</p>
                                        <p className="text-[11px] text-muted-foreground capitalize">
                                            {source.source_type.replace('_', ' ')}
                                        </p>
                                    </div>
                                    <ChevronRight
                                        className={`size-4 shrink-0 transition-colors ${selectedId === source.id
                                            ? 'text-primary'
                                            : 'text-muted-foreground/30 group-hover:text-muted-foreground/60'
                                            }`}
                                    />
                                </div>
                            </button>
                        ))
                    )}

                    {/* Inline add form */}
                    {showAddForm && <AddSourceForm onSubmit={handleCreate} onCancel={() => setShowAddForm(false)} />}
                </div>

                {/* Add Source button */}
                {!showAddForm && (
                    <Button
                        variant="outline"
                        size="sm"
                        className="w-full gap-2 mt-1"
                        onClick={() => setShowAddForm(true)}
                    >
                        <Plus className="size-3.5" />
                        Add Source
                    </Button>
                )}
            </div>

            {/* ── Right: Detail Panel ──────────────────────────────── */}
            <div className="flex-1 min-w-0">
                {selectedSource ? (
                    <SourceDetailPanel source={selectedSource} onDelete={handleDelete} />
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                        <Database className="size-12 mb-3 opacity-15" />
                        <p className="text-sm">Select a source to manage</p>
                    </div>
                )}
            </div>
        </div>
    );
}

/* ── Source Type Icon ─────────────────────────────────────────────── */

function SourceTypeIcon({ type, size = 'md' }: { type: DataSourceType; size?: 'sm' | 'md' }) {
    const dim = size === 'sm' ? 'size-8' : 'size-10';
    const radius = size === 'sm' ? 'rounded-lg' : 'rounded-xl';
    const iconSize = size === 'sm' ? 'size-3.5' : 'size-5';

    switch (type) {
        case 'website':
            return (
                <div className={`flex items-center justify-center ${dim} ${radius} bg-blue-500/10 text-blue-500 shrink-0`}>
                    <Globe className={iconSize} />
                </div>
            );
        case 'text':
            return (
                <div className={`flex items-center justify-center ${dim} ${radius} bg-purple-500/10 text-purple-500 shrink-0`}>
                    <FileText className={iconSize} />
                </div>
            );
        default:
            return (
                <div className={`flex items-center justify-center ${dim} ${radius} bg-emerald-500/10 text-emerald-500 shrink-0`}>
                    <FileUp className={iconSize} />
                </div>
            );
    }
}

const SOURCE_TYPE_OPTIONS: { value: DataSourceType; label: string }[] = [
    { value: 'website', label: 'Website' },
    { value: 'text', label: 'Text' },
    { value: 'file_upload', label: 'File Upload' },
];

/* ── Add Source Form ─────────────────────────────────────────────── */

function AddSourceForm({
    onSubmit,
    onCancel,
}: {
    onSubmit: (name: string, description: string, sourceType: DataSourceType) => Promise<void>;
    onCancel: () => void;
}) {
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [sourceType, setSourceType] = useState<DataSourceType>('text');
    const [creating, setCreating] = useState(false);

    const handleSubmit = async () => {
        if (!name.trim()) return;
        setCreating(true);
        try {
            await onSubmit(name.trim(), description.trim(), sourceType);
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-3.5 space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-semibold text-primary">
                <Plus className="size-3.5" />
                New Source
            </div>

            {/* Source type selector */}
            <div className="flex gap-1 p-0.5 bg-muted/50 rounded-lg">
                {SOURCE_TYPE_OPTIONS.map((opt) => (
                    <button
                        key={opt.value}
                        onClick={() => setSourceType(opt.value)}
                        className={`
                            flex-1 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all
                            ${sourceType === opt.value
                                ? 'bg-background shadow-sm text-foreground'
                                : 'text-muted-foreground hover:text-foreground'
                            }
                        `}
                    >
                        {opt.label}
                    </button>
                ))}
            </div>

            <Input
                placeholder="Source name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                autoFocus
                className="h-8 text-sm"
            />
            <Input
                placeholder="Description (optional)"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                className="h-8 text-sm"
            />
            <div className="flex gap-2">
                <Button size="sm" onClick={handleSubmit} disabled={!name.trim() || creating} className="gap-1.5 h-7 text-xs">
                    {creating ? <Loader2 className="size-3 animate-spin" /> : <Plus className="size-3" />}
                    Create
                </Button>
                <Button size="sm" variant="ghost" onClick={onCancel} className="h-7 text-xs">
                    Cancel
                </Button>
            </div>
        </div>
    );
}

/* ── Source Detail Panel ─────────────────────────────────────────── */

const SOURCE_TYPE_LABELS: Record<DataSourceType, string> = {
    website: 'Website Source',
    file_upload: 'File Upload',
    text: 'Text Source',
};

function SourceDetailPanel({
    source,
    onDelete,
}: {
    source: DataSource;
    onDelete: (id: string) => Promise<void>;
}) {
    return (
        <div className="space-y-5">
            {/* Source header */}
            <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                    <SourceTypeIcon type={source.source_type} size="md" />
                    <div>
                        <h2 className="text-lg font-semibold">{source.name}</h2>
                        <p className="text-xs text-muted-foreground">
                            {SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type} ·{' '}
                            {new Date(source.created_at).toLocaleDateString()}
                        </p>
                    </div>
                </div>
                <Button
                    variant="ghost"
                    size="icon"
                    className="size-8 text-muted-foreground hover:text-destructive"
                    onClick={() => onDelete(source.id)}
                    title="Delete source"
                >
                    <Trash2 className="size-4" />
                </Button>
            </div>

            {source.description && (
                <p className="text-sm text-muted-foreground -mt-2">{source.description}</p>
            )}

            {/* Type-specific panel */}
            {source.source_type === 'file_upload' && <FileUploadPanel sourceId={source.id} />}
            {source.source_type === 'website' && <WebsitePanel sourceId={source.id} />}
            {source.source_type === 'text' && <TextPanel sourceId={source.id} />}
        </div>
    );
}

/* ── File Upload Panel ───────────────────────────────────────────── */

function FileUploadPanel({ sourceId }: { sourceId: string }) {
    const [storedFiles, setStoredFiles] = useState<SourceFileEntry[]>([]);
    const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
    const [uploading, setUploading] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [loadingFiles, setLoadingFiles] = useState(true);
    const [result, setResult] = useState<string | null>(null);

    // Fetch stored files on mount / source change
    useEffect(() => {
        let cancelled = false;
        setLoadingFiles(true);
        setResult(null);
        dataSourcesApi
            .getFiles(sourceId)
            .then((res) => {
                if (!cancelled) {
                    setStoredFiles(res.files);
                    setSelectedPaths(new Set(res.files.map((f) => f.stored_path)));
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setStoredFiles([]);
                    setSelectedPaths(new Set());
                }
            })
            .finally(() => {
                if (!cancelled) setLoadingFiles(false);
            });
        return () => {
            cancelled = true;
        };
    }, [sourceId]);

    // Upload files (store only)
    const handleFileUpload = useCallback(
        async (e: React.ChangeEvent<HTMLInputElement>) => {
            if (!e.target.files) return;
            const files = Array.from(e.target.files);
            setUploading(true);
            setResult(null);
            try {
                const res = await dataSourcesApi.uploadFiles(sourceId, files);
                setResult(res.message);
                // Refresh file list
                const updated = await dataSourcesApi.getFiles(sourceId);
                setStoredFiles(updated.files);
                // Select newly uploaded files
                const newPaths = res.uploaded.map((f) => f.stored_path);
                setSelectedPaths((prev) => new Set([...prev, ...newPaths]));
            } catch (err) {
                setResult(err instanceof Error ? err.message : 'Upload failed');
            } finally {
                setUploading(false);
                e.target.value = '';
            }
        },
        [sourceId],
    );

    // Remove a stored file
    const handleRemove = useCallback(
        async (storedPath: string) => {
            try {
                const res = await dataSourcesApi.removeFile(sourceId, storedPath);
                setStoredFiles(res.files);
                setSelectedPaths((prev) => {
                    const next = new Set(prev);
                    next.delete(storedPath);
                    return next;
                });
            } catch {
                /* silent */
            }
        },
        [sourceId],
    );

    // Toggle selection
    const toggle = (path: string) => {
        setSelectedPaths((prev) => {
            const next = new Set(prev);
            if (next.has(path)) next.delete(path);
            else next.add(path);
            return next;
        });
    };

    // Process selected files
    const handleProcess = async (paths: string[]) => {
        if (!paths.length) return;
        setProcessing(true);
        setResult(null);
        try {
            const res = await dataSourcesApi.processFiles(sourceId, { stored_paths: paths });
            setResult(res.message);
            // Remove processed files from the list (one-time processing)
            const processed = new Set(paths);
            setStoredFiles((prev) => prev.filter((f) => !processed.has(f.stored_path)));
            setSelectedPaths(new Set());
        } catch (err) {
            setResult(err instanceof Error ? err.message : 'Processing failed');
        } finally {
            setProcessing(false);
        }
    };

    return (
        <div className="space-y-4">
            {/* Upload zone */}
            <div className="rounded-xl border bg-card p-5">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                    <Upload className="size-4" />
                    Upload Files
                </h3>
                <label
                    className={`
                        flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 cursor-pointer transition-all
                        ${uploading ? 'opacity-50 pointer-events-none' : 'hover:border-primary/50 hover:bg-accent/30'}
                    `}
                >
                    {uploading ? (
                        <Loader2 className="size-8 animate-spin text-primary" />
                    ) : (
                        <div className="flex items-center justify-center size-12 rounded-2xl bg-emerald-500/10 text-emerald-500">
                            <Upload className="size-5" />
                        </div>
                    )}
                    <div className="text-center">
                        <p className="text-sm font-medium">
                            {uploading ? 'Uploading...' : 'Click to select files'}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">or drag & drop</p>
                    </div>
                    <input
                        type="file"
                        multiple
                        className="hidden"
                        onChange={handleFileUpload}
                        disabled={uploading}
                    />
                </label>
            </div>

            {/* Stored files list */}
            <div className="rounded-xl border bg-card p-5 space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                    <FileUp className="size-4" />
                    Stored Files
                </h3>

                {loadingFiles ? (
                    <div className="flex items-center justify-center py-6">
                        <Loader2 className="size-5 animate-spin text-muted-foreground" />
                    </div>
                ) : storedFiles.length === 0 ? (
                    <div className="text-center py-6 text-muted-foreground">
                        <FileUp className="size-10 mx-auto mb-2 opacity-15" />
                        <p className="text-sm">No files uploaded yet</p>
                        <p className="text-xs mt-1 opacity-70">Upload files above to get started.</p>
                    </div>
                ) : (
                    <>
                        {/* Select controls */}
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>
                                {selectedPaths.size} of {storedFiles.length} selected
                            </span>
                            <div className="flex gap-3">
                                <button
                                    onClick={() =>
                                        setSelectedPaths(new Set(storedFiles.map((f) => f.stored_path)))
                                    }
                                    className="hover:text-foreground transition-colors"
                                >
                                    Select all
                                </button>
                                <button
                                    onClick={() => setSelectedPaths(new Set())}
                                    className="hover:text-foreground transition-colors"
                                >
                                    Deselect all
                                </button>
                            </div>
                        </div>

                        {/* File checklist */}
                        <div className="space-y-1 max-h-72 overflow-y-auto">
                            {storedFiles.map((file) => (
                                <div
                                    key={file.stored_path}
                                    className={`
                                        group flex items-center gap-2.5 rounded-lg border px-3 py-2.5 transition-all cursor-pointer
                                        ${selectedPaths.has(file.stored_path) ? 'border-primary/30 bg-primary/5' : 'hover:bg-accent/50'}
                                    `}
                                    onClick={() => toggle(file.stored_path)}
                                >
                                    <input
                                        type="checkbox"
                                        checked={selectedPaths.has(file.stored_path)}
                                        onChange={() => toggle(file.stored_path)}
                                        className="size-3.5 rounded border-input accent-primary shrink-0"
                                    />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{file.filename}</p>
                                        <p className="text-[11px] text-muted-foreground">
                                            {formatFileSize(file.file_size)} · {file.mime_type}
                                        </p>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="size-6 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive shrink-0"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleRemove(file.stored_path);
                                        }}
                                    >
                                        <Trash2 className="size-3" />
                                    </Button>
                                </div>
                            ))}
                        </div>

                        {/* Process buttons */}
                        <div className="flex gap-2 pt-1">
                            <Button
                                size="sm"
                                onClick={() => handleProcess(Array.from(selectedPaths))}
                                disabled={selectedPaths.size === 0 || processing}
                                className="gap-1.5"
                            >
                                {processing ? (
                                    <Loader2 className="size-3.5 animate-spin" />
                                ) : (
                                    <ExternalLink className="size-3.5" />
                                )}
                                Process Selected ({selectedPaths.size})
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                    handleProcess(storedFiles.map((f) => f.stored_path))
                                }
                                disabled={storedFiles.length === 0 || processing}
                                className="gap-1.5"
                            >
                                <ExternalLink className="size-3.5" />
                                Process All ({storedFiles.length})
                            </Button>
                        </div>
                    </>
                )}
            </div>

            {/* Result message */}
            {result && (
                <div className="p-3 rounded-lg bg-primary/10 text-primary text-sm">{result}</div>
            )}
        </div>
    );
}

/** Format bytes to human-readable size. */
function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ── Website Panel ───────────────────────────────────────────────── */

function WebsitePanel({ sourceId }: { sourceId: string }) {
    const [storedUrls, setStoredUrls] = useState<string[]>([]);
    const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
    const [newUrl, setNewUrl] = useState('');
    const [loadingUrls, setLoadingUrls] = useState(true);
    const [processing, setProcessing] = useState(false);
    const [result, setResult] = useState<string | null>(null);

    // Fetch URLs on mount / source change
    useEffect(() => {
        let cancelled = false;
        setLoadingUrls(true);
        setResult(null);
        dataSourcesApi
            .getUrls(sourceId)
            .then((res) => {
                if (!cancelled) {
                    setStoredUrls(res.urls);
                    setSelectedUrls(new Set(res.urls));
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setStoredUrls([]);
                    setSelectedUrls(new Set());
                }
            })
            .finally(() => {
                if (!cancelled) setLoadingUrls(false);
            });
        return () => {
            cancelled = true;
        };
    }, [sourceId]);

    // Add URL
    const handleAdd = useCallback(async () => {
        const url = newUrl.trim();
        if (!url) return;
        setNewUrl('');
        try {
            const res = await dataSourcesApi.updateUrls(sourceId, { urls: [...storedUrls, url] });
            setStoredUrls(res.urls);
            setSelectedUrls((prev) => new Set([...prev, url]));
        } catch {
            /* silent */
        }
    }, [newUrl, sourceId, storedUrls]);

    // Remove URL
    const handleRemove = useCallback(
        async (url: string) => {
            try {
                const res = await dataSourcesApi.updateUrls(sourceId, {
                    urls: storedUrls.filter((u) => u !== url),
                });
                setStoredUrls(res.urls);
                setSelectedUrls((prev) => {
                    const next = new Set(prev);
                    next.delete(url);
                    return next;
                });
            } catch {
                /* silent */
            }
        },
        [sourceId, storedUrls],
    );

    // Toggle selection
    const toggle = (url: string) => {
        setSelectedUrls((prev) => {
            const next = new Set(prev);
            if (next.has(url)) next.delete(url);
            else next.add(url);
            return next;
        });
    };

    // Process URLs
    const handleProcess = async (urls: string[]) => {
        if (!urls.length) return;
        setProcessing(true);
        setResult(null);
        try {
            const res = await dataSourcesApi.submitUrls(sourceId, { urls });
            setResult(res.message);
            // Uncheck processed URLs but keep definitions (content may change)
            setSelectedUrls(new Set());
        } catch (err) {
            setResult(err instanceof Error ? err.message : 'Submit failed');
        } finally {
            setProcessing(false);
        }
    };

    return (
        <div className="space-y-4">
            {/* Add URL input */}
            <div className="rounded-xl border bg-card p-5 space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                    <Globe className="size-4" />
                    Manage URLs
                </h3>

                <div className="flex gap-2">
                    <Input
                        placeholder="https://example.com/page"
                        value={newUrl}
                        onChange={(e) => setNewUrl(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                e.preventDefault();
                                handleAdd();
                            }
                        }}
                        className="font-mono text-sm"
                    />
                    <Button
                        size="sm"
                        onClick={handleAdd}
                        disabled={!newUrl.trim()}
                        className="gap-1.5 shrink-0"
                    >
                        <Plus className="size-3.5" />
                        Add
                    </Button>
                </div>

                {/* URL List */}
                {loadingUrls ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="size-5 animate-spin text-muted-foreground" />
                    </div>
                ) : storedUrls.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                        <Globe className="size-10 mx-auto mb-2 opacity-15" />
                        <p className="text-sm">No URLs configured yet</p>
                        <p className="text-xs mt-1 opacity-70">
                            Add URLs above to start managing this source.
                        </p>
                    </div>
                ) : (
                    <>
                        {/* Select controls */}
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>
                                {selectedUrls.size} of {storedUrls.length} selected
                            </span>
                            <div className="flex gap-3">
                                <button
                                    onClick={() => setSelectedUrls(new Set(storedUrls))}
                                    className="hover:text-foreground transition-colors"
                                >
                                    Select all
                                </button>
                                <button
                                    onClick={() => setSelectedUrls(new Set())}
                                    className="hover:text-foreground transition-colors"
                                >
                                    Deselect all
                                </button>
                            </div>
                        </div>

                        {/* URL checklist */}
                        <div className="space-y-1 max-h-72 overflow-y-auto">
                            {storedUrls.map((url) => (
                                <div
                                    key={url}
                                    className={`
                                        group flex items-center gap-2.5 rounded-lg border px-3 py-2.5 transition-all cursor-pointer
                                        ${selectedUrls.has(url) ? 'border-primary/30 bg-primary/5' : 'hover:bg-accent/50'}
                                    `}
                                    onClick={() => toggle(url)}
                                >
                                    <input
                                        type="checkbox"
                                        checked={selectedUrls.has(url)}
                                        onChange={() => toggle(url)}
                                        className="size-3.5 rounded border-input accent-primary shrink-0"
                                    />
                                    <span className="flex-1 text-sm font-mono truncate">{url}</span>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="size-6 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive shrink-0"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleRemove(url);
                                        }}
                                    >
                                        <Trash2 className="size-3" />
                                    </Button>
                                </div>
                            ))}
                        </div>

                        {/* Action buttons */}
                        <div className="flex gap-2 pt-1">
                            <Button
                                size="sm"
                                onClick={() => handleProcess(Array.from(selectedUrls))}
                                disabled={selectedUrls.size === 0 || processing}
                                className="gap-1.5"
                            >
                                {processing ? (
                                    <Loader2 className="size-3.5 animate-spin" />
                                ) : (
                                    <ExternalLink className="size-3.5" />
                                )}
                                Process Selected ({selectedUrls.size})
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleProcess(storedUrls)}
                                disabled={storedUrls.length === 0 || processing}
                                className="gap-1.5"
                            >
                                <ExternalLink className="size-3.5" />
                                Process All ({storedUrls.length})
                            </Button>
                        </div>
                    </>
                )}
            </div>

            {/* Result message */}
            {result && (
                <div className="p-3 rounded-lg bg-primary/10 text-primary text-sm">{result}</div>
            )}
        </div>
    );
}

/* ── Text Panel ──────────────────────────────────────────────────── */

function TextPanel({ sourceId }: { sourceId: string }) {
    const [storedTexts, setStoredTexts] = useState<SourceTextEntry[]>([]);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [newTitle, setNewTitle] = useState('');
    const [newContent, setNewContent] = useState('');
    const [loadingTexts, setLoadingTexts] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [result, setResult] = useState<string | null>(null);

    // Fetch texts on mount / source change
    useEffect(() => {
        let cancelled = false;
        setLoadingTexts(true);
        setResult(null);
        dataSourcesApi
            .getTexts(sourceId)
            .then((res) => {
                if (!cancelled) {
                    setStoredTexts(res.texts);
                    setSelectedIds(new Set(res.texts.map((t) => t.id)));
                }
            })
            .catch(() => {
                if (!cancelled) {
                    setStoredTexts([]);
                    setSelectedIds(new Set());
                }
            })
            .finally(() => {
                if (!cancelled) setLoadingTexts(false);
            });
        return () => {
            cancelled = true;
        };
    }, [sourceId]);

    // Add text entry
    const handleAdd = useCallback(async () => {
        const title = newTitle.trim();
        const content = newContent.trim();
        if (!title || !content) return;
        setSubmitting(true);
        setResult(null);
        try {
            const res = await dataSourcesApi.addText(sourceId, { title, content });
            setStoredTexts(res.texts);
            // Select the newly added entry
            const newEntry = res.texts[res.texts.length - 1];
            if (newEntry) {
                setSelectedIds((prev) => new Set([...prev, newEntry.id]));
            }
            setNewTitle('');
            setNewContent('');
        } catch (err) {
            setResult(err instanceof Error ? err.message : 'Failed to add text');
        } finally {
            setSubmitting(false);
        }
    }, [newTitle, newContent, sourceId]);

    // Remove text entry
    const handleRemove = useCallback(
        async (textId: string) => {
            try {
                const res = await dataSourcesApi.removeText(sourceId, textId);
                setStoredTexts(res.texts);
                setSelectedIds((prev) => {
                    const next = new Set(prev);
                    next.delete(textId);
                    return next;
                });
            } catch {
                /* silent */
            }
        },
        [sourceId],
    );

    // Toggle selection
    const toggle = (id: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    // Process texts
    const handleProcess = async (ids: string[]) => {
        if (!ids.length) return;
        setProcessing(true);
        setResult(null);
        try {
            const res = await dataSourcesApi.processTexts(sourceId, { text_ids: ids });
            setResult(res.message);
            setSelectedIds(new Set());
        } catch (err) {
            setResult(err instanceof Error ? err.message : 'Processing failed');
        } finally {
            setProcessing(false);
        }
    };

    return (
        <div className="space-y-4">
            {/* Add text form */}
            <div className="rounded-xl border bg-card p-5 space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                    <Type className="size-4" />
                    Add Text
                </h3>

                <Input
                    placeholder="Title (e.g. Meeting Notes, Article, ...)"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    className="text-sm"
                />
                <textarea
                    placeholder="Paste or type your text content here..."
                    value={newContent}
                    onChange={(e) => setNewContent(e.target.value)}
                    rows={6}
                    className="
                        w-full rounded-lg border bg-background px-3 py-2 text-sm resize-y
                        placeholder:text-muted-foreground focus-visible:outline-none
                        focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2
                        min-h-[120px]
                    "
                />
                <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                        {newContent.length.toLocaleString()} characters
                    </span>
                    <Button
                        size="sm"
                        onClick={handleAdd}
                        disabled={!newTitle.trim() || !newContent.trim() || submitting}
                        className="gap-1.5"
                    >
                        {submitting ? (
                            <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                            <Plus className="size-3.5" />
                        )}
                        Add Text
                    </Button>
                </div>
            </div>

            {/* Stored texts list */}
            <div className="rounded-xl border bg-card p-5 space-y-4">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                    <FileText className="size-4" />
                    Stored Texts
                </h3>

                {loadingTexts ? (
                    <div className="flex items-center justify-center py-6">
                        <Loader2 className="size-5 animate-spin text-muted-foreground" />
                    </div>
                ) : storedTexts.length === 0 ? (
                    <div className="text-center py-6 text-muted-foreground">
                        <FileText className="size-10 mx-auto mb-2 opacity-15" />
                        <p className="text-sm">No text entries yet</p>
                        <p className="text-xs mt-1 opacity-70">Add text above to get started.</p>
                    </div>
                ) : (
                    <>
                        {/* Select controls */}
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>
                                {selectedIds.size} of {storedTexts.length} selected
                            </span>
                            <div className="flex gap-3">
                                <button
                                    onClick={() =>
                                        setSelectedIds(new Set(storedTexts.map((t) => t.id)))
                                    }
                                    className="hover:text-foreground transition-colors"
                                >
                                    Select all
                                </button>
                                <button
                                    onClick={() => setSelectedIds(new Set())}
                                    className="hover:text-foreground transition-colors"
                                >
                                    Deselect all
                                </button>
                            </div>
                        </div>

                        {/* Text checklist */}
                        <div className="space-y-1 max-h-72 overflow-y-auto">
                            {storedTexts.map((entry) => (
                                <div
                                    key={entry.id}
                                    className={`
                                        group flex items-center gap-2.5 rounded-lg border px-3 py-2.5 transition-all cursor-pointer
                                        ${selectedIds.has(entry.id) ? 'border-primary/30 bg-primary/5' : 'hover:bg-accent/50'}
                                    `}
                                    onClick={() => toggle(entry.id)}
                                >
                                    <input
                                        type="checkbox"
                                        checked={selectedIds.has(entry.id)}
                                        onChange={() => toggle(entry.id)}
                                        className="size-3.5 rounded border-input accent-primary shrink-0"
                                    />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{entry.title}</p>
                                        <p className="text-[11px] text-muted-foreground">
                                            {entry.char_count.toLocaleString()} chars ·{' '}
                                            {new Date(entry.created_at).toLocaleDateString()}
                                        </p>
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        className="size-6 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive shrink-0"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleRemove(entry.id);
                                        }}
                                    >
                                        <Trash2 className="size-3" />
                                    </Button>
                                </div>
                            ))}
                        </div>

                        {/* Process buttons */}
                        <div className="flex gap-2 pt-1">
                            <Button
                                size="sm"
                                onClick={() => handleProcess(Array.from(selectedIds))}
                                disabled={selectedIds.size === 0 || processing}
                                className="gap-1.5"
                            >
                                {processing ? (
                                    <Loader2 className="size-3.5 animate-spin" />
                                ) : (
                                    <ExternalLink className="size-3.5" />
                                )}
                                Process Selected ({selectedIds.size})
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                    handleProcess(storedTexts.map((t) => t.id))
                                }
                                disabled={storedTexts.length === 0 || processing}
                                className="gap-1.5"
                            >
                                <ExternalLink className="size-3.5" />
                                Process All ({storedTexts.length})
                            </Button>
                        </div>
                    </>
                )}
            </div>

            {/* Result message */}
            {result && (
                <div className="p-3 rounded-lg bg-primary/10 text-primary text-sm">{result}</div>
            )}
        </div>
    );
}

/* ── Processing Tab ──────────────────────────────────────────────── */

const STATUS_CONFIG: Record<JobStatus, { icon: React.ReactNode; color: string; label: string }> = {
    queued: {
        icon: <Clock className="size-4" />,
        color: 'text-muted-foreground',
        label: 'Queued',
    },
    processing: {
        icon: <Loader2 className="size-4 animate-spin" />,
        color: 'text-blue-500',
        label: 'Processing',
    },
    completed: {
        icon: <CheckCircle2 className="size-4" />,
        color: 'text-emerald-500',
        label: 'Completed',
    },
    failed: {
        icon: <XCircle className="size-4" />,
        color: 'text-destructive',
        label: 'Failed',
    },
};

function ProcessingTab({
    jobs,
    loading,
    onRestart,
}: {
    jobs: ProcessingJob[];
    loading: boolean;
    onRestart: (jobId: string) => Promise<void>;
}) {
    const [restartingId, setRestartingId] = useState<string | null>(null);

    const handleRestart = async (jobId: string) => {
        setRestartingId(jobId);
        try {
            await onRestart(jobId);
        } catch {
            // Error handled upstream
        } finally {
            setRestartingId(null);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (jobs.length === 0) {
        return (
            <div className="text-center py-12 text-muted-foreground">
                <Activity className="size-12 mx-auto mb-3 opacity-30" />
                <p className="text-sm">No processing jobs yet.</p>
                <p className="text-xs mt-1">Submit files or URLs from a data source to start processing.</p>
            </div>
        );
    }

    const canRestart = (status: JobStatus) => status === 'completed' || status === 'failed';

    return (
        <div className="space-y-2">
            <div className="flex items-center gap-3 mb-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                    <span className="inline-block size-2 rounded-full bg-blue-500 animate-pulse" />
                    {jobs.filter((j) => j.status === 'processing').length} processing
                </span>
                <span>{jobs.filter((j) => j.status === 'queued').length} queued</span>
                <span>{jobs.filter((j) => j.status === 'completed').length} completed</span>
                <span>{jobs.filter((j) => j.status === 'failed').length} failed</span>
            </div>

            {jobs.map((job) => {
                const cfg = STATUS_CONFIG[job.status];
                const isRestarting = restartingId === job.id;
                return (
                    <div
                        key={job.id}
                        className={`
                            flex items-center gap-3 rounded-lg border px-4 py-3 transition-all
                            ${job.status === 'processing' ? 'border-blue-500/30 bg-blue-500/5' : ''}
                            ${job.status === 'failed' ? 'border-destructive/30 bg-destructive/5' : ''}
                        `}
                    >
                        <div className={cfg.color}>{cfg.icon}</div>

                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">
                                {job.resource_identifier.length > 80
                                    ? job.resource_identifier.slice(0, 80) + '…'
                                    : job.resource_identifier}
                            </p>
                            {job.progress_message && (
                                <p className="text-xs text-muted-foreground truncate mt-0.5">
                                    {job.progress_message}
                                </p>
                            )}
                            {job.error_message && (
                                <p className="text-xs text-destructive mt-0.5">
                                    {job.error_message}
                                </p>
                            )}
                        </div>

                        <div className="shrink-0 flex items-center gap-2">
                            {canRestart(job.status) && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="size-7 text-muted-foreground hover:text-primary"
                                    onClick={() => handleRestart(job.id)}
                                    disabled={isRestarting}
                                    title="Restart processing"
                                >
                                    {isRestarting ? (
                                        <Loader2 className="size-3.5 animate-spin" />
                                    ) : (
                                        <RotateCcw className="size-3.5" />
                                    )}
                                </Button>
                            )}
                            <div className="text-right">
                                <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
                                <p className="text-[10px] text-muted-foreground/60 mt-0.5 font-mono">
                                    {new Date(job.created_at).toLocaleTimeString()}
                                </p>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
