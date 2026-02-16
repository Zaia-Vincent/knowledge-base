/**
 * FileDetailPage — Full detail view for a single processed file.
 *
 * Displays classification results, extracted JSONB metadata,
 * document summary, text preview, and processing signals.
 */

import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
    ArrowLeft,
    FileText,
    Loader2,
    AlertCircle,
    CheckCircle2,
    Tag,
    Calendar,
    Hash,
    Type,
    Brain,
    Clock,
    Sparkles,
    Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useFileDetail } from '@/hooks/use-files';
import { filesApi } from '@/lib/files-api';
import type { ClassificationSignal, MetadataField } from '@/types/files';

/* ── Helpers ─────────────────────────────────────────────────────── */

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('nl-NL', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function confidenceColor(pct: number): string {
    if (pct >= 80) return 'text-emerald-600 dark:text-emerald-400';
    if (pct >= 50) return 'text-amber-600 dark:text-amber-400';
    return 'text-destructive';
}

function confidenceBg(pct: number): string {
    if (pct >= 80) return 'bg-emerald-500';
    if (pct >= 50) return 'bg-amber-500';
    return 'bg-destructive';
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
    pending: { label: 'Pending', color: 'bg-muted text-muted-foreground' },
    extracting_text: { label: 'Extracting Text', color: 'bg-blue-500/15 text-blue-600 dark:text-blue-400' },
    classifying: { label: 'Classifying', color: 'bg-purple-500/15 text-purple-600 dark:text-purple-400' },
    extracting_metadata: { label: 'Extracting Metadata', color: 'bg-amber-500/15 text-amber-600 dark:text-amber-400' },
    done: { label: 'Done', color: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400' },
    error: { label: 'Error', color: 'bg-destructive/15 text-destructive' },
};

/* ── Sub-components ──────────────────────────────────────────────── */

function InfoRow({ label, value, icon }: { label: string; value: React.ReactNode; icon?: React.ReactNode }) {
    return (
        <div className="flex items-start gap-3 py-2">
            {icon && <div className="mt-0.5 text-muted-foreground">{icon}</div>}
            <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
                <div className="text-sm mt-0.5">{value}</div>
            </div>
        </div>
    );
}

function SignalCard({ signal }: { signal: ClassificationSignal }) {
    const pct = Math.round(signal.score * 100);

    const methodLabels: Record<string, string> = {
        file_pattern: 'File Pattern',
        hint_match: 'Hint Matching',
        llm_analysis: 'LLM Analysis',
        llm_tool_processing: 'LLM Tool Processing',
    };

    const methodIcons: Record<string, React.ReactNode> = {
        file_pattern: <FileText className="size-3.5" />,
        hint_match: <Tag className="size-3.5" />,
        llm_analysis: <Brain className="size-3.5" />,
        llm_tool_processing: <Brain className="size-3.5" />,
    };

    return (
        <div className="flex items-center gap-3 rounded-lg border bg-card p-3 transition-colors hover:bg-accent/30">
            <div className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-primary">
                {methodIcons[signal.method] ?? <Sparkles className="size-3.5" />}
            </div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium truncate">
                        {methodLabels[signal.method] ?? signal.method}
                    </p>
                    <span className={`text-xs font-semibold tabular-nums ${confidenceColor(pct)}`}>
                        {pct}%
                    </span>
                </div>
                <p className="text-xs text-muted-foreground truncate mt-0.5">
                    {signal.concept_id} — {signal.details}
                </p>
            </div>
        </div>
    );
}

function MetadataCard({ fieldKey, field }: { fieldKey: string; field: MetadataField }) {
    const pct = Math.round(field.confidence * 100);

    // Determine display value and icon based on the value type
    let displayValue: string;
    let icon: React.ReactNode;

    if (typeof field.value === 'number') {
        displayValue = field.value.toLocaleString('nl-NL', { maximumFractionDigits: 2 });
        icon = <Hash className="size-3.5" />;
    } else if (field.value && /^\d{4}-\d{2}-\d{2}/.test(String(field.value))) {
        displayValue = formatDate(String(field.value));
        icon = <Calendar className="size-3.5" />;
    } else {
        displayValue = String(field.value ?? '—');
        icon = <Type className="size-3.5" />;
    }

    return (
        <div className="rounded-lg border bg-card p-4 transition-colors hover:bg-accent/30">
            <div className="flex items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 text-muted-foreground">
                    {icon}
                    <span className="text-xs font-medium uppercase tracking-wider">
                        {fieldKey.replace(/_/g, ' ')}
                    </span>
                </div>
                <span className={`text-xs font-medium tabular-nums ${confidenceColor(pct)}`}>
                    {pct}%
                </span>
            </div>
            <p className="text-sm font-medium break-words">{displayValue}</p>
        </div>
    );
}

/* ── Page ─────────────────────────────────────────────────────────── */

export function FileDetailPage() {
    const { id } = useParams<{ id: string }>();
    const { file, loading, error } = useFileDetail(id);
    const navigate = useNavigate();
    const [deleting, setDeleting] = useState(false);

    const handleDelete = async () => {
        if (!file || !window.confirm(`Are you sure you want to delete "${file.filename}"? This action cannot be undone.`)) return;
        setDeleting(true);
        try {
            await filesApi.deleteFile(file.id);
            navigate('/files');
        } catch {
            setDeleting(false);
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-32">
                <Loader2 className="size-8 animate-spin text-primary" />
                <p className="mt-3 text-sm text-muted-foreground">Loading file details…</p>
            </div>
        );
    }

    if (error || !file) {
        return (
            <div className="mx-auto max-w-3xl py-16 text-center">
                <AlertCircle className="mx-auto size-12 text-destructive/50 mb-4" />
                <h2 className="text-lg font-semibold">File not found</h2>
                <p className="text-sm text-muted-foreground mt-1">{error ?? 'The requested file does not exist.'}</p>
                <Button asChild variant="ghost" className="mt-4">
                    <Link to="/files">← Back to files</Link>
                </Button>
            </div>
        );
    }

    const statusConf = STATUS_LABELS[file.status] ?? STATUS_LABELS.pending;
    const classificationPct = file.classification ? Math.round(file.classification.confidence * 100) : null;
    const metadataEntries = Object.entries(file.metadata ?? {});

    return (
        <div className="mx-auto max-w-5xl space-y-6">
            {/* Back + Header */}
            <div className="flex items-center gap-3">
                <Button asChild variant="ghost" size="sm">
                    <Link to="/files">
                        <ArrowLeft className="size-4" />
                    </Link>
                </Button>
                <div className="min-w-0 flex-1">
                    <h1 className="text-xl font-bold tracking-tight truncate">{file.filename}</h1>
                    {file.original_path && file.original_path !== file.filename && (
                        <p className="text-xs text-muted-foreground truncate">{file.original_path}</p>
                    )}
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusConf.color}`}>
                    {statusConf.label}
                </span>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDelete}
                    disabled={deleting}
                    className="gap-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                >
                    {deleting ? (
                        <Loader2 className="size-4 animate-spin" />
                    ) : (
                        <Trash2 className="size-4" />
                    )}
                    Delete
                </Button>
            </div>

            <div className="grid gap-6 lg:grid-cols-3">
                {/* Left: Classification + Metadata */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Classification Card */}
                    {file.classification && (
                        <Card className="p-5">
                            <div className="flex items-center gap-2 mb-4">
                                <Tag className="size-4 text-primary" />
                                <h2 className="text-sm font-semibold">Classification</h2>
                            </div>

                            <div className="flex items-center gap-4 mb-4">
                                <div className="flex-1">
                                    <p className="text-lg font-bold">
                                        {file.classification.primary_concept_id}
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        Primary concept
                                    </p>
                                </div>

                                {classificationPct != null && (
                                    <div className="text-center">
                                        <p className={`text-2xl font-bold tabular-nums ${confidenceColor(classificationPct)}`}>
                                            {classificationPct}%
                                        </p>
                                        <p className="text-xs text-muted-foreground">confidence</p>
                                        {/* Confidence bar */}
                                        <div className="mt-2 h-1.5 w-24 rounded-full bg-muted overflow-hidden">
                                            <div
                                                className={`h-full rounded-full transition-all duration-500 ${confidenceBg(classificationPct)}`}
                                                style={{ width: `${classificationPct}%` }}
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Signals */}
                            {file.classification.signals.length > 0 && (
                                <>
                                    <Separator className="my-4" />
                                    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                                        Classification Signals
                                    </h3>
                                    <div className="space-y-2">
                                        {file.classification.signals.map((s, i) => (
                                            <SignalCard key={i} signal={s} />
                                        ))}
                                    </div>
                                </>
                            )}
                        </Card>
                    )}

                    {/* Extracted Metadata (JSONB) */}
                    {metadataEntries.length > 0 && (
                        <Card className="p-5">
                            <div className="flex items-center gap-2 mb-4">
                                <Sparkles className="size-4 text-primary" />
                                <h2 className="text-sm font-semibold">Extracted Metadata</h2>
                                <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                                    {metadataEntries.length} properties
                                </span>
                            </div>
                            <div className="grid gap-3 sm:grid-cols-2">
                                {metadataEntries.map(([key, field]) => (
                                    <MetadataCard key={key} fieldKey={key} field={field} />
                                ))}
                            </div>
                        </Card>
                    )}

                    {/* Extra Fields */}
                    {file.extra_fields && file.extra_fields.length > 0 && (
                        <Card className="p-5">
                            <div className="flex items-center gap-2 mb-4">
                                <Sparkles className="size-4 text-amber-500" />
                                <h2 className="text-sm font-semibold">Additional Discovered Fields</h2>
                                <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                                    {file.extra_fields.length} fields
                                </span>
                            </div>
                            <div className="grid gap-3 sm:grid-cols-2">
                                {file.extra_fields.map((ef, i) => (
                                    <div key={i} className="rounded-lg border bg-card p-4">
                                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">
                                            {ef.field_name.replace(/_/g, ' ')}
                                        </p>
                                        <p className="text-sm font-medium break-words">{String(ef.value ?? '—')}</p>
                                    </div>
                                ))}
                            </div>
                        </Card>
                    )}

                    {/* Summary */}
                    {file.summary && (
                        <Card className="p-5">
                            <h2 className="text-sm font-semibold mb-2">Document Summary</h2>
                            <p className="text-sm text-muted-foreground leading-relaxed">
                                {file.summary}
                            </p>
                        </Card>
                    )}

                    {/* Text Preview */}
                    {file.extracted_text_preview && (
                        <Card className="p-5">
                            <h2 className="text-sm font-semibold mb-3">Text Preview</h2>
                            <pre className="whitespace-pre-wrap text-xs text-muted-foreground leading-relaxed max-h-80 overflow-y-auto rounded-lg bg-muted/50 p-4 font-mono">
                                {file.extracted_text_preview}
                            </pre>
                        </Card>
                    )}
                </div>

                {/* Right: File Info */}
                <div>
                    <Card className="p-5 sticky top-6">
                        <h2 className="text-sm font-semibold mb-3">File Information</h2>
                        <div className="divide-y">
                            <InfoRow
                                label="Status"
                                icon={file.status === 'done' ? <CheckCircle2 className="size-4 text-emerald-500" /> : <Clock className="size-4" />}
                                value={
                                    <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${statusConf.color}`}>
                                        {statusConf.label}
                                    </span>
                                }
                            />
                            <InfoRow
                                label="MIME Type"
                                icon={<FileText className="size-4" />}
                                value={<code className="text-xs bg-muted px-1.5 py-0.5 rounded">{file.mime_type}</code>}
                            />
                            <InfoRow
                                label="File Size"
                                value={formatFileSize(file.file_size)}
                            />
                            <InfoRow
                                label="Uploaded"
                                icon={<Calendar className="size-4" />}
                                value={formatDate(file.uploaded_at)}
                            />
                            {file.processed_at && (
                                <InfoRow
                                    label="Processed"
                                    icon={<CheckCircle2 className="size-4" />}
                                    value={formatDate(file.processed_at)}
                                />
                            )}
                            {file.language && (
                                <InfoRow
                                    label="Language"
                                    value={file.language.toUpperCase()}
                                />
                            )}
                            {file.processing_time_ms != null && (
                                <InfoRow
                                    label="Processing Time"
                                    icon={<Clock className="size-4" />}
                                    value={`${(file.processing_time_ms / 1000).toFixed(1)}s`}
                                />
                            )}
                            {file.error_message && (
                                <InfoRow
                                    label="Error"
                                    icon={<AlertCircle className="size-4 text-destructive" />}
                                    value={
                                        <p className="text-xs text-destructive break-words">
                                            {file.error_message}
                                        </p>
                                    }
                                />
                            )}
                        </div>
                    </Card>
                </div>
            </div>
        </div>
    );
}
