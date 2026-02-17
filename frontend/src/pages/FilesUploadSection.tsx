/**
 * FilesUploadSection — Upload zone with live processing queue.
 * Shows drag-and-drop upload area and a list of files currently being processed
 * with their real-time status. Auto-refreshes while files are in-progress.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
    FileText,
    Loader2,
    AlertCircle,
    CheckCircle2,
    Clock,
    Upload,
    RefreshCw,
    ArrowRight,
    Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { ProcessedFileSummary, ProcessingStatus } from '@/types/files';

/* ── Helpers ─────────────────────────────────────────────────────── */

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatRelativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    return `${hours}h ago`;
}

const PROCESSING_STATUSES = new Set<string>(['pending', 'extracting_text', 'classifying', 'extracting_metadata']);

const STATUS_CONFIG: Record<ProcessingStatus, { label: string; color: string; icon: React.ReactNode; step: number }> = {
    pending: { label: 'Queued', color: 'bg-muted text-muted-foreground', icon: <Clock className="size-3.5" />, step: 0 },
    extracting_text: { label: 'Extracting Text', color: 'bg-blue-500/15 text-blue-600 dark:text-blue-400', icon: <Loader2 className="size-3.5 animate-spin" />, step: 1 },
    classifying: { label: 'Classifying', color: 'bg-purple-500/15 text-purple-600 dark:text-purple-400', icon: <Loader2 className="size-3.5 animate-spin" />, step: 2 },
    extracting_metadata: { label: 'Extracting Data', color: 'bg-amber-500/15 text-amber-600 dark:text-amber-400', icon: <Loader2 className="size-3.5 animate-spin" />, step: 3 },
    done: { label: 'Complete', color: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400', icon: <CheckCircle2 className="size-3.5" />, step: 4 },
    error: { label: 'Error', color: 'bg-destructive/15 text-destructive', icon: <AlertCircle className="size-3.5" />, step: -1 },
};

const PIPELINE_STEPS = [
    { key: 'pending', label: 'Queued' },
    { key: 'extracting_text', label: 'Text' },
    { key: 'classifying', label: 'Classify' },
    { key: 'extracting_metadata', label: 'Extract' },
    { key: 'done', label: 'Done' },
];

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
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
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

/* ── Pipeline Progress ───────────────────────────────────────────── */

function PipelineProgress({ status }: { status: string }) {
    const config = STATUS_CONFIG[status as ProcessingStatus] ?? STATUS_CONFIG.pending;
    const currentStep = config.step;

    if (currentStep === -1) {
        return (
            <div className="flex items-center gap-1.5">
                <AlertCircle className="size-3.5 text-destructive" />
                <span className="text-xs font-medium text-destructive">Error</span>
            </div>
        );
    }

    return (
        <div className="flex items-center gap-1">
            {PIPELINE_STEPS.map((step, i) => {
                const isComplete = i < currentStep;
                const isCurrent = i === currentStep;
                const isPending = i > currentStep;

                return (
                    <div key={step.key} className="flex items-center gap-1">
                        {i > 0 && (
                            <div className={`h-px w-3 ${isComplete ? 'bg-primary' : 'bg-border'}`} />
                        )}
                        <div
                            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium transition-all ${isCurrent
                                ? 'bg-primary/15 text-primary ring-1 ring-primary/30'
                                : isComplete
                                    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                                    : 'bg-muted text-muted-foreground/50'
                                }`}
                        >
                            {isCurrent && <Loader2 className="size-2.5 animate-spin" />}
                            {isComplete && <CheckCircle2 className="size-2.5" />}
                            {isPending && <span className="size-2.5 rounded-full border border-current opacity-40" />}
                            {step.label}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

/* ── Processing Card ─────────────────────────────────────────────── */

function ProcessingCard({ file }: { file: ProcessedFileSummary }) {
    const config = STATUS_CONFIG[file.status as ProcessingStatus] ?? STATUS_CONFIG.pending;
    const isError = file.status === 'error';
    const isDone = file.status === 'done';

    return (
        <Card className={`p-4 transition-all ${isError ? 'border-destructive/30' : isDone ? 'border-emerald-500/30 opacity-70' : ''}`}>
            <div className="flex items-start gap-3">
                {/* Icon */}
                <div className={`flex size-10 items-center justify-center rounded-xl shrink-0 ${isError ? 'bg-destructive/10' : isDone ? 'bg-emerald-500/10' : 'bg-primary/10'
                    }`}>
                    {isError ? (
                        <AlertCircle className="size-5 text-destructive" />
                    ) : isDone ? (
                        <CheckCircle2 className="size-5 text-emerald-600 dark:text-emerald-400" />
                    ) : (
                        <Zap className="size-5 text-primary" />
                    )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 space-y-2">
                    <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                            <p className="font-medium text-sm truncate">{file.filename}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">
                                {formatFileSize(file.file_size)} · {formatRelativeTime(file.uploaded_at)}
                            </p>
                        </div>
                        <Badge
                            variant="secondary"
                            className={`shrink-0 text-[10px] ${config.color}`}
                        >
                            {config.icon}
                            <span className="ml-1">{config.label}</span>
                        </Badge>
                    </div>

                    {/* Pipeline progress */}
                    {!isError && <PipelineProgress status={file.status} />}

                    {/* Classification result (if done) */}
                    {isDone && file.classification_concept_id && (
                        <div className="flex items-center gap-2 text-xs">
                            <ArrowRight className="size-3 text-muted-foreground" />
                            <span className="text-muted-foreground">Classified as</span>
                            <Badge variant="outline" className="text-xs">{file.classification_concept_id}</Badge>
                            {file.classification_confidence != null && (
                                <span className="text-emerald-600 dark:text-emerald-400 font-medium tabular-nums">
                                    {Math.round(file.classification_confidence * 100)}%
                                </span>
                            )}
                        </div>
                    )}

                    {/* Error message */}
                    {isError && file.error_message && (
                        <p className="text-xs text-destructive/80 break-words">{file.error_message}</p>
                    )}
                </div>
            </div>
        </Card>
    );
}

/* ── Main Section ────────────────────────────────────────────────── */

export function FilesUploadSection({
    files,
    uploading,
    loading,
    error,
    onUpload,
    onRefetch,
}: {
    files: ProcessedFileSummary[];
    uploading: boolean;
    loading: boolean;
    error: string | null;
    onUpload: (files: File[]) => void;
    onRefetch: () => void;
}) {
    // Separate processing files from recently completed
    const processingFiles = files.filter((f) => PROCESSING_STATUSES.has(f.status));
    const recentlyCompleted = files
        .filter((f) => f.status === 'done' || f.status === 'error')
        .slice(0, 5); // Show last 5 completed

    const hasInProgress = processingFiles.length > 0;

    // Auto-refresh while files are processing
    useEffect(() => {
        if (!hasInProgress) return;
        const interval = setInterval(onRefetch, 3000);
        return () => clearInterval(interval);
    }, [hasInProgress, onRefetch]);

    return (
        <div className="flex flex-col h-full">
            {/* ── Fixed top area: upload zone, error, processing queue ── */}
            <div className="shrink-0 space-y-6">
                {/* Upload Zone */}
                <UploadZone onUpload={onUpload} uploading={uploading} />

                {/* Error */}
                {error && (
                    <Card className="flex items-center gap-3 border-destructive/50 bg-destructive/5 p-4">
                        <AlertCircle className="size-5 text-destructive shrink-0" />
                        <div className="flex-1">
                            <p className="text-sm font-medium text-destructive">Error</p>
                            <p className="text-xs text-destructive/80 mt-0.5">{error}</p>
                        </div>
                        <Button variant="ghost" size="sm" onClick={onRefetch}>Retry</Button>
                    </Card>
                )}

                {/* Processing Queue */}
                {processingFiles.length > 0 && (
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <div className="relative">
                                    <Zap className="size-4 text-primary" />
                                    <span className="absolute -top-0.5 -right-0.5 flex size-2.5">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                                        <span className="relative inline-flex size-2.5 rounded-full bg-primary" />
                                    </span>
                                </div>
                                <h3 className="text-sm font-semibold">Processing Queue</h3>
                                <Badge variant="secondary" className="tabular-nums">
                                    {processingFiles.length}
                                </Badge>
                            </div>
                            <Button variant="ghost" size="sm" onClick={onRefetch} disabled={loading} className="gap-1.5 h-7 text-xs">
                                <RefreshCw className={`size-3 ${loading ? 'animate-spin' : ''}`} />
                                Refresh
                            </Button>
                        </div>
                        <div className="space-y-2">
                            {processingFiles.map((f) => (
                                <ProcessingCard key={f.id} file={f} />
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* ── Scrollable bottom area: recently processed ── */}
            <div className="flex-1 min-h-0 mt-6 overflow-y-auto">
                {recentlyCompleted.length > 0 && (
                    <div>
                        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 sticky top-0 bg-background py-2 z-10">
                            <CheckCircle2 className="size-4 text-emerald-500" />
                            Recently Processed
                        </h3>
                        <div className="space-y-2">
                            {recentlyCompleted.map((f) => (
                                <ProcessingCard key={f.id} file={f} />
                            ))}
                        </div>
                    </div>
                )}

                {/* Empty state */}
                {!hasInProgress && recentlyCompleted.length === 0 && !uploading && !error && (
                    <div className="flex flex-col items-center py-8 text-muted-foreground">
                        <FileText className="size-10 opacity-30 mb-3" />
                        <p className="text-sm font-medium">No files in the processing queue</p>
                        <p className="text-xs mt-1">Upload documents above to start processing</p>
                    </div>
                )}
            </div>
        </div>
    );
}
