/**
 * FilesPage — Processed files overview with upload and status table.
 *
 * Features:
 * - Drag-and-drop file upload zone (accepts ZIP and individual files)
 * - Sortable/filterable table of processed files
 * - Status badges, confidence indicators, and quick navigation to detail view
 */

import { useCallback, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
    FileText,
    Loader2,
    AlertCircle,
    CheckCircle2,
    Clock,
    Search,
    RefreshCw,
    Upload,
    Trash2,
    X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { useFiles } from '@/hooks/use-files';
import type { ProcessedFileSummary, ProcessingStatus } from '@/types/files';

/* ── Helpers ─────────────────────────────────────────────────────── */

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('nl-NL', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

const STATUS_CONFIG: Record<
    ProcessingStatus,
    { label: string; color: string; icon: React.ReactNode }
> = {
    pending: {
        label: 'Pending',
        color: 'bg-muted text-muted-foreground',
        icon: <Clock className="size-3" />,
    },
    extracting_text: {
        label: 'Extracting',
        color: 'bg-blue-500/15 text-blue-600 dark:text-blue-400',
        icon: <Loader2 className="size-3 animate-spin" />,
    },
    classifying: {
        label: 'Classifying',
        color: 'bg-purple-500/15 text-purple-600 dark:text-purple-400',
        icon: <Loader2 className="size-3 animate-spin" />,
    },
    extracting_metadata: {
        label: 'Extracting Data',
        color: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
        icon: <Loader2 className="size-3 animate-spin" />,
    },
    done: {
        label: 'Done',
        color: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400',
        icon: <CheckCircle2 className="size-3" />,
    },
    error: {
        label: 'Error',
        color: 'bg-destructive/15 text-destructive',
        icon: <AlertCircle className="size-3" />,
    },
};

function StatusBadge({ status }: { status: string }) {
    const config = STATUS_CONFIG[status as ProcessingStatus] ?? STATUS_CONFIG.pending;
    return (
        <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${config.color}`}
        >
            {config.icon}
            {config.label}
        </span>
    );
}

function ConfidenceBadge({ confidence }: { confidence: number | null }) {
    if (confidence == null) return <span className="text-muted-foreground text-xs">—</span>;
    const pct = Math.round(confidence * 100);
    const color =
        pct >= 80
            ? 'text-emerald-600 dark:text-emerald-400'
            : pct >= 50
                ? 'text-amber-600 dark:text-amber-400'
                : 'text-destructive';

    return <span className={`text-xs font-medium tabular-nums ${color}`}>{pct}%</span>;
}

/* ── Upload Zone ─────────────────────────────────────────────────── */

function UploadZone({
    onUpload,
    uploading,
}: {
    onUpload: (files: File[]) => void;
    uploading: boolean;
}) {
    const [dragActive, setDragActive] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const handleDrop = useCallback(
        (e: React.DragEvent) => {
            e.preventDefault();
            setDragActive(false);
            const dropped = Array.from(e.dataTransfer.files);
            if (dropped.length > 0) onUpload(dropped);
        },
        [onUpload],
    );

    const handleChange = useCallback(
        (e: React.ChangeEvent<HTMLInputElement>) => {
            const selected = Array.from(e.target.files ?? []);
            if (selected.length > 0) onUpload(selected);
            e.target.value = '';
        },
        [onUpload],
    );

    return (
        <div
            onDragOver={(e) => {
                e.preventDefault();
                setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`
                relative flex cursor-pointer flex-col items-center justify-center gap-3
                rounded-xl border-2 border-dashed p-8 transition-all duration-200
                ${dragActive
                    ? 'border-primary bg-primary/5 scale-[1.01]'
                    : 'border-border hover:border-primary/50 hover:bg-accent/50'
                }
            `}
        >
            <input
                ref={inputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.xlsx,.msg,.txt,.csv,.md,.png,.jpg,.jpeg,.tiff,.zip"
                onChange={handleChange}
                className="hidden"
            />

            {uploading ? (
                <>
                    <Loader2 className="size-10 animate-spin text-primary" />
                    <p className="text-sm font-medium text-primary">Uploading & Processing…</p>
                </>
            ) : (
                <>
                    <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10">
                        <Upload className="size-6 text-primary" />
                    </div>
                    <div className="text-center">
                        <p className="text-sm font-medium">
                            Drop files here or <span className="text-primary underline underline-offset-2">browse</span>
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                            PDF, DOCX, XLSX, MSG, TXT, CSV, images, or ZIP archives
                        </p>
                    </div>
                </>
            )}
        </div>
    );
}

/* ── Files Table ─────────────────────────────────────────────────── */

function FilesTable({ files, onDelete }: { files: ProcessedFileSummary[]; onDelete: (id: string) => void }) {
    const [deletingId, setDeletingId] = useState<string | null>(null);

    const handleDelete = async (id: string, filename: string) => {
        if (!window.confirm(`Are you sure you want to delete "${filename}"? This action cannot be undone.`)) return;
        setDeletingId(id);
        try {
            await onDelete(id);
        } finally {
            setDeletingId(null);
        }
    };

    if (files.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                <FileText className="size-12 mb-4 opacity-30" />
                <p className="text-sm font-medium">No files processed yet</p>
                <p className="text-xs mt-1">Upload documents to start processing</p>
            </div>
        );
    }

    return (
        <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b bg-muted/50">
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                            File
                        </th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                            Status
                        </th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                            Classification
                        </th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                            Confidence
                        </th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                            Size
                        </th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                            Uploaded
                        </th>
                        <th className="px-4 py-3 w-10" />
                    </tr>
                </thead>
                <tbody className="divide-y">
                    {files.map((f) => (
                        <tr
                            key={f.id}
                            className="group transition-colors hover:bg-accent/50"
                        >
                            <td className="px-4 py-3">
                                <Link
                                    to={`/files/${f.id}`}
                                    className="flex items-center gap-2.5 text-foreground hover:text-primary transition-colors"
                                >
                                    <FileText className="size-4 shrink-0 text-muted-foreground group-hover:text-primary" />
                                    <div className="min-w-0">
                                        <p className="truncate font-medium text-sm leading-tight">
                                            {f.filename}
                                        </p>
                                        {f.original_path && f.original_path !== f.filename && (
                                            <p className="truncate text-xs text-muted-foreground mt-0.5">
                                                {f.original_path}
                                            </p>
                                        )}
                                    </div>
                                </Link>
                            </td>
                            <td className="px-4 py-3">
                                <StatusBadge status={f.status} />
                            </td>
                            <td className="px-4 py-3">
                                <span className="text-sm">
                                    {f.classification_concept_id ?? (
                                        <span className="text-muted-foreground">—</span>
                                    )}
                                </span>
                            </td>
                            <td className="px-4 py-3 text-right">
                                <ConfidenceBadge confidence={f.classification_confidence} />
                            </td>
                            <td className="px-4 py-3 text-right">
                                <span className="text-xs text-muted-foreground tabular-nums">
                                    {formatFileSize(f.file_size)}
                                </span>
                            </td>
                            <td className="px-4 py-3">
                                <span className="text-xs text-muted-foreground">
                                    {formatDate(f.uploaded_at)}
                                </span>
                            </td>
                            <td className="px-4 py-3">
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDelete(f.id, f.filename);
                                    }}
                                    disabled={deletingId === f.id}
                                    className="rounded-md p-1.5 text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 disabled:opacity-50"
                                    title="Delete file"
                                >
                                    {deletingId === f.id ? (
                                        <Loader2 className="size-3.5 animate-spin" />
                                    ) : (
                                        <Trash2 className="size-3.5" />
                                    )}
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

/* ── Page ─────────────────────────────────────────────────────────── */

export function FilesPage() {
    const { files, loading, error, uploading, uploadFiles, deleteFile, refetch } = useFiles();
    const [search, setSearch] = useState('');

    const filtered = search
        ? files.filter(
            (f) =>
                f.filename.toLowerCase().includes(search.toLowerCase()) ||
                f.classification_concept_id?.toLowerCase().includes(search.toLowerCase()),
        )
        : files;

    return (
        <div className="mx-auto max-w-6xl space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Processed Files</h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Upload, classify, and extract metadata from documents
                    </p>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={refetch}
                    disabled={loading}
                    className="gap-2"
                >
                    <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </Button>
            </div>

            {/* Upload Zone */}
            <UploadZone onUpload={uploadFiles} uploading={uploading} />

            {/* Error */}
            {error && (
                <Card className="flex items-center gap-3 border-destructive/50 bg-destructive/5 p-4">
                    <AlertCircle className="size-5 text-destructive shrink-0" />
                    <div className="flex-1">
                        <p className="text-sm font-medium text-destructive">Error</p>
                        <p className="text-xs text-destructive/80 mt-0.5">{error}</p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={refetch}>
                        Retry
                    </Button>
                </Card>
            )}

            {/* Search + Stats */}
            <div className="flex items-center gap-3">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <input
                        type="text"
                        placeholder="Search files or classifications…"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="h-9 w-full rounded-lg border bg-background pl-10 pr-8 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                    {search && (
                        <button
                            onClick={() => setSearch('')}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                            <X className="size-3.5" />
                        </button>
                    )}
                </div>
                <span className="text-xs text-muted-foreground tabular-nums">
                    {filtered.length} file{filtered.length !== 1 ? 's' : ''}
                </span>
            </div>

            {/* Table */}
            {loading && files.length === 0 ? (
                <div className="flex items-center justify-center py-16">
                    <Loader2 className="size-8 animate-spin text-primary" />
                </div>
            ) : (
                <FilesTable files={filtered} onDelete={deleteFile} />
            )}
        </div>
    );
}
