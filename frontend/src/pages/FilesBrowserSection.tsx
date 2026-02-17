/**
 * FilesBrowserSection — Processed files browser with accordion grouping,
 * type filter, and resizable detail panel with raw/formatted metadata views.
 */

import { useEffect, useMemo, useState } from 'react';
import {
    FileText,
    Loader2,
    AlertCircle,
    CheckCircle2,
    Clock,
    Search,
    Trash2,
    X,
    ChevronRight,
    ChevronDown,
    Tag,
    Calendar,
    Hash,
    Type,
    Sparkles,
    Code2,
    LayoutList,
    Brain,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { useFileDetail } from '@/hooks/use-files';
import { ontologyApi } from '@/lib/ontology-api';
import type { ProcessedFileSummary, ProcessingStatus, MetadataField } from '@/types/files';
import type { ConceptDetail, ConceptProperty } from '@/types/ontology';

/* ── Helpers ─────────────────────────────────────────────────────── */

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('nl-NL', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

const STATUS_CONFIG: Record<ProcessingStatus, { label: string; color: string; icon: React.ReactNode }> = {
    pending: { label: 'Pending', color: 'bg-muted text-muted-foreground', icon: <Clock className="size-3" /> },
    extracting_text: { label: 'Extracting', color: 'bg-blue-500/15 text-blue-600 dark:text-blue-400', icon: <Loader2 className="size-3 animate-spin" /> },
    classifying: { label: 'Classifying', color: 'bg-purple-500/15 text-purple-600 dark:text-purple-400', icon: <Loader2 className="size-3 animate-spin" /> },
    extracting_metadata: { label: 'Extracting Data', color: 'bg-amber-500/15 text-amber-600 dark:text-amber-400', icon: <Loader2 className="size-3 animate-spin" /> },
    done: { label: 'Done', color: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400', icon: <CheckCircle2 className="size-3" /> },
    error: { label: 'Error', color: 'bg-destructive/15 text-destructive', icon: <AlertCircle className="size-3" /> },
};

function StatusBadge({ status }: { status: string }) {
    const config = STATUS_CONFIG[status as ProcessingStatus] ?? STATUS_CONFIG.pending;
    return (
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${config.color}`}>
            {config.icon}
            {config.label}
        </span>
    );
}

function ConfidenceBadge({ confidence }: { confidence: number | null }) {
    if (confidence == null) return <span className="text-muted-foreground text-xs">—</span>;
    const pct = Math.round(confidence * 100);
    const color = pct >= 80 ? 'text-emerald-600 dark:text-emerald-400' : pct >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-destructive';
    return <span className={`text-xs font-medium tabular-nums ${color}`}>{pct}%</span>;
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

function formatMetadataValue(value: unknown): string {
    if (value == null) return '—';
    if (typeof value === 'object') {
        if (Array.isArray(value)) {
            return value.map((item) => formatMetadataValue(item)).join(', ');
        }

        const obj = value as Record<string, unknown>;
        const label = obj.label;
        if (typeof label === 'string' && label.trim()) return label;

        const name = obj.name;
        if (typeof name === 'string' && name.trim()) return name;

        try {
            return JSON.stringify(value);
        } catch {
            return '[Object]';
        }
    }
    return String(value);
}

/* ── Grouping ────────────────────────────────────────────────────── */

interface FileGroup {
    parent: ProcessedFileSummary;
    children: ProcessedFileSummary[];
    groupName: string;
    rootId: string;
}

function stripDocumentSuffix(filename: string): string {
    return filename.replace(/\s+\(document\s+\d+\)$/i, '').trim();
}

function parsePageStart(pageRange: string | null): number | null {
    if (!pageRange) return null;
    const match = pageRange.match(/^(\d+)/);
    if (!match) return null;
    return Number.parseInt(match[1], 10);
}

function sortDocsInGroup(a: ProcessedFileSummary, b: ProcessedFileSummary): number {
    const aPage = parsePageStart(a.page_range);
    const bPage = parsePageStart(b.page_range);

    if (aPage != null && bPage != null && aPage !== bPage) return aPage - bPage;
    if (aPage != null && bPage == null) return -1;
    if (aPage == null && bPage != null) return 1;

    return b.uploaded_at.localeCompare(a.uploaded_at);
}

function groupFiles(files: ProcessedFileSummary[]): FileGroup[] {
    const rootMap = new Map<string, { parent?: ProcessedFileSummary; children: ProcessedFileSummary[] }>();

    for (const file of files) {
        const rootId = file.origin_file_id ?? file.id;
        const entry = rootMap.get(rootId) ?? { children: [] };
        if (file.origin_file_id) {
            entry.children.push(file);
        } else {
            entry.parent = file;
        }
        rootMap.set(rootId, entry);
    }

    const groups: FileGroup[] = [];
    for (const [rootId, entry] of rootMap.entries()) {
        const sortedChildren = [...entry.children].sort(sortDocsInGroup);
        if (entry.parent) {
            groups.push({
                parent: entry.parent,
                children: sortedChildren,
                groupName: stripDocumentSuffix(entry.parent.filename),
                rootId,
            });
            continue;
        }

        // Orphan recovery: keep legacy children visible and grouped even if
        // the original parent row was removed earlier.
        if (sortedChildren.length > 0) {
            groups.push({
                parent: sortedChildren[0],
                children: sortedChildren.slice(1),
                groupName: stripDocumentSuffix(sortedChildren[0].filename),
                rootId,
            });
        }
    }

    return groups.sort((a, b) => b.parent.uploaded_at.localeCompare(a.parent.uploaded_at));
}

/* ── Type Filter Pills ───────────────────────────────────────────── */

function TypeFilter({ types, selected, onSelect }: {
    types: string[];
    selected: string | null;
    onSelect: (type: string | null) => void;
}) {
    if (types.length === 0) return null;
    return (
        <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-muted-foreground mr-1">Type:</span>
            <button
                onClick={() => onSelect(null)}
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${selected === null ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-accent hover:text-foreground'
                    }`}
            >All</button>
            {types.map((type) => (
                <button
                    key={type}
                    onClick={() => onSelect(type === selected ? null : type)}
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${selected === type ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-accent hover:text-foreground'
                        }`}
                >
                    <Tag className="size-3" />
                    {type}
                </button>
            ))}
        </div>
    );
}

/* ── File Row ────────────────────────────────────────────────────── */

function FileRow({ file, onSelect, onDelete, isSelected, indent = false, showDelete = true }: {
    file: ProcessedFileSummary;
    onSelect: (id: string) => void;
    onDelete: (id: string) => void;
    isSelected: boolean;
    indent?: boolean;
    showDelete?: boolean;
}) {
    const [deleting, setDeleting] = useState(false);

    const handleDelete = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!window.confirm(`Delete "${file.filename}" and all related extracted documents?`)) return;
        setDeleting(true);
        try { await onDelete(file.id); } finally { setDeleting(false); }
    };

    return (
        <tr
            onClick={() => onSelect(file.id)}
            className={`group cursor-pointer transition-colors ${isSelected ? 'bg-primary/5 border-l-2 border-l-primary' : 'hover:bg-accent/50'}`}
        >
            <td className={`px-4 py-3 ${indent ? 'pl-12' : ''}`}>
                <div className="flex items-center gap-2.5">
                    <FileText className={`size-4 shrink-0 ${isSelected ? 'text-primary' : 'text-muted-foreground group-hover:text-primary'}`} />
                    <div className="min-w-0">
                        <p className="truncate font-medium text-sm leading-tight">{file.display_name || file.filename}</p>
                        {file.page_range && <p className="truncate text-xs text-muted-foreground mt-0.5">Pages {file.page_range}</p>}
                    </div>
                </div>
            </td>
            <td className="px-4 py-3"><StatusBadge status={file.status} /></td>
            <td className="px-4 py-3">
                <span className="text-sm">{file.classification_concept_id ?? <span className="text-muted-foreground">—</span>}</span>
            </td>
            <td className="px-4 py-3 text-right"><ConfidenceBadge confidence={file.classification_confidence} /></td>
            <td className="px-4 py-3 text-right"><span className="text-xs text-muted-foreground tabular-nums">{formatFileSize(file.file_size)}</span></td>
            <td className="px-4 py-3"><span className="text-xs text-muted-foreground">{formatDate(file.uploaded_at)}</span></td>
            <td className="px-4 py-3">
                {showDelete ? (
                    <button onClick={handleDelete} disabled={deleting} className="rounded-md p-1.5 text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 disabled:opacity-50" title="Delete group">
                        {deleting ? <Loader2 className="size-3.5 animate-spin" /> : <Trash2 className="size-3.5" />}
                    </button>
                ) : null}
            </td>
        </tr>
    );
}

/* ── Accordion Group ─────────────────────────────────────────────── */

function AccordionGroup({ group, selectedId, onSelect, onDelete }: {
    group: FileGroup; selectedId: string | null; onSelect: (id: string) => void; onDelete: (id: string) => void;
}) {
    const [expanded, setExpanded] = useState(false);
    const hasChildren = group.children.length > 0;
    const documents = useMemo(
        () => [group.parent, ...group.children].sort(sortDocsInGroup),
        [group.parent, group.children],
    );

    if (!hasChildren) {
        return <FileRow file={group.parent} onSelect={onSelect} onDelete={onDelete} isSelected={selectedId === group.parent.id} />;
    }

    const anyChildSelected = group.children.some((c) => c.id === selectedId);
    const parentSelected = selectedId === group.parent.id;

    return (
        <>
            <tr
                onClick={() => onSelect(group.parent.id)}
                className={`group cursor-pointer transition-colors ${parentSelected ? 'bg-primary/5 border-l-2 border-l-primary' : 'hover:bg-accent/50'}`}
            >
                <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                        <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }} className="rounded p-0.5 hover:bg-accent">
                            {expanded ? <ChevronDown className="size-4 text-muted-foreground" /> : <ChevronRight className="size-4 text-muted-foreground" />}
                        </button>
                        <FileText className={`size-4 shrink-0 ${parentSelected ? 'text-primary' : 'text-muted-foreground group-hover:text-primary'}`} />
                        <div className="min-w-0">
                            <p className="truncate font-medium text-sm leading-tight">{group.groupName}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">{group.children.length + 1} document{group.children.length > 0 ? 's' : ''}</p>
                        </div>
                    </div>
                </td>
                <td className="px-4 py-3"><StatusBadge status={group.parent.status} /></td>
                <td className="px-4 py-3"><span className="text-sm">{group.parent.classification_concept_id ?? <span className="text-muted-foreground">—</span>}</span></td>
                <td className="px-4 py-3 text-right"><ConfidenceBadge confidence={group.parent.classification_confidence} /></td>
                <td className="px-4 py-3 text-right"><span className="text-xs text-muted-foreground tabular-nums">{formatFileSize(group.parent.file_size)}</span></td>
                <td className="px-4 py-3"><span className="text-xs text-muted-foreground">{formatDate(group.parent.uploaded_at)}</span></td>
                <td className="px-4 py-3">
                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            const total = group.children.length + 1;
                            if (window.confirm(`Delete "${group.groupName}" and all ${total} related document${total === 1 ? '' : 's'}?`)) {
                                onDelete(group.parent.id);
                            }
                        }}
                        className="rounded-md p-1.5 text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                    ><Trash2 className="size-3.5" /></button>
                </td>
            </tr>
            {(expanded || anyChildSelected) && documents.map((child) => (
                <FileRow key={child.id} file={child} onSelect={onSelect} onDelete={onDelete} isSelected={selectedId === child.id} indent showDelete={false} />
            ))}
        </>
    );
}

/* ── Files Table ─────────────────────────────────────────────────── */

function FilesTable({ groups, selectedId, onSelect, onDelete }: {
    groups: FileGroup[]; selectedId: string | null; onSelect: (id: string) => void; onDelete: (id: string) => void;
}) {
    if (groups.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                <FileText className="size-12 mb-4 opacity-30" />
                <p className="text-sm font-medium">No processed files found</p>
                <p className="text-xs mt-1">Upload documents in the Upload tab to start processing</p>
            </div>
        );
    }

    return (
        <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b bg-muted/50">
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">File</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Classification</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">Confidence</th>
                        <th className="px-4 py-3 text-right font-medium text-muted-foreground">Size</th>
                        <th className="px-4 py-3 text-left font-medium text-muted-foreground">Uploaded</th>
                        <th className="px-4 py-3 w-10" />
                    </tr>
                </thead>
                <tbody className="divide-y">
                    {groups.map((g) => <AccordionGroup key={g.parent.id} group={g} selectedId={selectedId} onSelect={onSelect} onDelete={onDelete} />)}
                </tbody>
            </table>
        </div>
    );
}

/* ── Detail Panel Helpers ────────────────────────────────────────── */

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

function FormattedField({ fieldKey, field, propertyDef }: {
    fieldKey: string; field: MetadataField; propertyDef?: ConceptProperty;
}) {
    const pct = Math.round(field.confidence * 100);
    const propType = propertyDef?.type?.toLowerCase() ?? '';
    let displayValue: React.ReactNode;
    let icon: React.ReactNode;

    if (Array.isArray(field.value)) {
        icon = <LayoutList className="size-3.5" />;
        displayValue = (
            <div className="space-y-1">
                {field.value.map((item, i) => (
                    <div key={i} className="rounded border bg-muted/30 p-2 text-xs">
                        {typeof item === 'object' && item !== null ? (
                            <div className="grid gap-1">
                                {Object.entries(item).map(([k, v]) => (
                                    <div key={k} className="flex gap-2">
                                        <span className="font-medium text-muted-foreground min-w-[80px]">{k.replace(/_/g, ' ')}:</span>
                                        <span>{formatMetadataValue(v)}</span>
                                    </div>
                                ))}
                            </div>
                        ) : formatMetadataValue(item)}
                    </div>
                ))}
            </div>
        );
    } else if (propType.startsWith('ref:') || (typeof field.value === 'object' && field.value !== null)) {
        icon = <Tag className="size-3.5" />;
        displayValue = formatMetadataValue(field.value);
    } else if (propType.includes('date') || (typeof field.value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(field.value))) {
        icon = <Calendar className="size-3.5" />;
        displayValue = formatDate(String(field.value));
    } else if (['number', 'decimal', 'integer', 'float'].includes(propType) || typeof field.value === 'number') {
        icon = <Hash className="size-3.5" />;
        const num = typeof field.value === 'number' ? field.value : parseFloat(String(field.value));
        displayValue = isNaN(num) ? String(field.value) : num.toLocaleString('nl-NL', { maximumFractionDigits: 2 });
    } else if (propType === 'enum' || propType === 'boolean') {
        icon = <Tag className="size-3.5" />;
        displayValue = <Badge variant="secondary">{String(field.value)}</Badge>;
    } else {
        icon = <Type className="size-3.5" />;
        displayValue = formatMetadataValue(field.value);
    }

    return (
        <div className="rounded-lg border bg-card p-3 transition-colors hover:bg-accent/30">
            <div className="flex items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2 text-muted-foreground min-w-0">
                    {icon}
                    <span className="text-xs font-medium uppercase tracking-wider truncate">{fieldKey.replace(/_/g, ' ')}</span>
                </div>
                <span className={`text-xs font-medium tabular-nums shrink-0 ${confidenceColor(pct)}`}>{pct}%</span>
            </div>
            {propertyDef?.description && <p className="text-[10px] text-muted-foreground mb-1">{propertyDef.description}</p>}
            <div className="text-sm font-medium break-words">{displayValue}</div>
        </div>
    );
}

function SignalCard({ signal }: { signal: { method: string; concept_id: string; score: number; details: string } }) {
    const pct = Math.round(signal.score * 100);
    const methodLabels: Record<string, string> = {
        file_pattern: 'File Pattern', hint_match: 'Hint Matching',
        llm_analysis: 'LLM Analysis', llm_tool_processing: 'LLM Tool Processing',
    };
    return (
        <div className="flex items-center gap-3 rounded-lg border bg-card p-2.5 transition-colors hover:bg-accent/30">
            <div className="flex size-7 items-center justify-center rounded-full bg-primary/10 text-primary"><Brain className="size-3" /></div>
            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-medium truncate">{methodLabels[signal.method] ?? signal.method}</p>
                    <span className={`text-xs font-semibold tabular-nums ${confidenceColor(pct)}`}>{pct}%</span>
                </div>
                <p className="text-[10px] text-muted-foreground truncate">{signal.concept_id} — {signal.details}</p>
            </div>
        </div>
    );
}

/* ── Detail Panel ────────────────────────────────────────────────── */

function DetailPanel({ fileId, onClose }: { fileId: string; onClose: () => void }) {
    const { file, loading, error } = useFileDetail(fileId);
    const [viewMode, setViewMode] = useState<'formatted' | 'raw'>('formatted');
    const [conceptDetail, setConceptDetail] = useState<ConceptDetail | null>(null);
    const [conceptLoading, setConceptLoading] = useState(false);

    useEffect(() => {
        if (!file?.classification?.primary_concept_id) { setConceptDetail(null); return; }
        let cancelled = false;
        setConceptLoading(true);
        ontologyApi.getConcept(file.classification.primary_concept_id)
            .then((detail) => { if (!cancelled) setConceptDetail(detail); })
            .catch(() => { })
            .finally(() => { if (!cancelled) setConceptLoading(false); });
        return () => { cancelled = true; };
    }, [file?.classification?.primary_concept_id]);

    const propertyMap = useMemo(() => {
        const map = new Map<string, ConceptProperty>();
        if (!conceptDetail) return map;
        for (const p of conceptDetail.properties) map.set(p.name, p);
        if (conceptDetail.inherited_properties) {
            for (const group of conceptDetail.inherited_properties) {
                for (const p of group.properties) { if (!map.has(p.name)) map.set(p.name, p); }
            }
        }
        return map;
    }, [conceptDetail]);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-full">
                <Loader2 className="size-6 animate-spin text-primary" />
                <p className="mt-2 text-xs text-muted-foreground">Loading details…</p>
            </div>
        );
    }

    if (error || !file) {
        return (
            <div className="flex flex-col items-center justify-center h-full">
                <AlertCircle className="size-8 text-destructive/50 mb-2" />
                <p className="text-sm font-medium">File not found</p>
                <Button variant="ghost" size="sm" onClick={onClose} className="mt-2">Close</Button>
            </div>
        );
    }

    const statusConf = STATUS_CONFIG[file.status as ProcessingStatus] ?? STATUS_CONFIG.pending;
    const classificationPct = file.classification ? Math.round(file.classification.confidence * 100) : null;
    const metadataEntries = Object.entries(file.metadata ?? {});

    return (
        <div className="flex h-full flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-start justify-between gap-3 border-b px-5 py-3 shrink-0">
                <div className="space-y-0.5 min-w-0">
                    <h2 className="text-base font-semibold tracking-tight truncate">{file.filename}</h2>
                    <div className="flex items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${statusConf.color}`}>{statusConf.label}</span>
                        <span className="text-[10px] text-muted-foreground">{formatFileSize(file.file_size)} · {file.mime_type}</span>
                    </div>
                </div>
                <Button variant="ghost" size="icon" className="shrink-0 size-7" onClick={onClose}><X className="size-3.5" /></Button>
            </div>

            <ScrollArea className="flex-1 min-h-0">
                <div className="p-5 space-y-5">
                    {/* File info */}
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                        <InfoRow label="Uploaded" icon={<Calendar className="size-3.5" />} value={<span className="text-xs">{formatDate(file.uploaded_at)}</span>} />
                        {file.processed_at && <InfoRow label="Processed" icon={<CheckCircle2 className="size-3.5" />} value={<span className="text-xs">{formatDate(file.processed_at)}</span>} />}
                        {file.processing_time_ms != null && <InfoRow label="Duration" icon={<Clock className="size-3.5" />} value={<span className="text-xs">{(file.processing_time_ms / 1000).toFixed(1)}s</span>} />}
                        {file.language && <InfoRow label="Language" value={<span className="text-xs">{file.language.toUpperCase()}</span>} />}
                    </div>

                    {/* Classification */}
                    {file.classification && (
                        <>
                            <Separator />
                            <div>
                                <div className="flex items-center gap-2 mb-3">
                                    <Tag className="size-3.5 text-primary" />
                                    <h3 className="text-xs font-semibold uppercase tracking-wider">Classification</h3>
                                </div>
                                <div className="flex items-center gap-4 mb-3">
                                    <div className="flex-1"><p className="text-base font-bold">{file.classification.primary_concept_id}</p></div>
                                    {classificationPct != null && (
                                        <div className="text-center">
                                            <p className={`text-xl font-bold tabular-nums ${confidenceColor(classificationPct)}`}>{classificationPct}%</p>
                                            <div className="mt-1 h-1.5 w-20 rounded-full bg-muted overflow-hidden">
                                                <div className={`h-full rounded-full transition-all duration-500 ${confidenceBg(classificationPct)}`} style={{ width: `${classificationPct}%` }} />
                                            </div>
                                        </div>
                                    )}
                                </div>
                                {file.classification.signals.length > 0 && (
                                    <div className="space-y-1.5">{file.classification.signals.map((s, i) => <SignalCard key={i} signal={s} />)}</div>
                                )}
                            </div>
                        </>
                    )}

                    {/* Metadata */}
                    {metadataEntries.length > 0 && (
                        <>
                            <Separator />
                            <div>
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        <Sparkles className="size-3.5 text-primary" />
                                        <h3 className="text-xs font-semibold uppercase tracking-wider">Extracted Metadata</h3>
                                        <span className="text-[10px] text-muted-foreground tabular-nums">{metadataEntries.length} fields</span>
                                    </div>
                                    <div className="flex items-center gap-0.5 rounded-lg border p-0.5">
                                        <button onClick={() => setViewMode('formatted')} className={`rounded-md px-2 py-1 text-[10px] font-medium transition-colors ${viewMode === 'formatted' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}>
                                            <LayoutList className="size-3 inline mr-1" />Formatted
                                        </button>
                                        <button onClick={() => setViewMode('raw')} className={`rounded-md px-2 py-1 text-[10px] font-medium transition-colors ${viewMode === 'raw' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}>
                                            <Code2 className="size-3 inline mr-1" />Raw
                                        </button>
                                    </div>
                                </div>
                                {conceptLoading && viewMode === 'formatted' && (
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3"><Loader2 className="size-3 animate-spin" />Loading property definitions…</div>
                                )}
                                {viewMode === 'formatted' ? (
                                    <div className="grid gap-2.5 sm:grid-cols-1">{metadataEntries.map(([key, field]) => <FormattedField key={key} fieldKey={key} field={field} propertyDef={propertyMap.get(key)} />)}</div>
                                ) : (
                                    <pre className="whitespace-pre-wrap text-xs leading-relaxed rounded-lg bg-muted/50 p-4 font-mono overflow-x-auto max-h-96">{JSON.stringify(file.metadata, null, 2)}</pre>
                                )}
                            </div>
                        </>
                    )}

                    {/* Extra Fields */}
                    {file.extra_fields && file.extra_fields.length > 0 && (
                        <>
                            <Separator />
                            <div>
                                <div className="flex items-center gap-2 mb-3"><Sparkles className="size-3.5 text-amber-500" /><h3 className="text-xs font-semibold uppercase tracking-wider">Additional Discovered Fields</h3></div>
                                <div className="grid gap-2">
                                    {file.extra_fields.map((ef, i) => (
                                        <div key={i} className="rounded-lg border bg-card p-3">
                                            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">{ef.field_name.replace(/_/g, ' ')}</p>
                                            <p className="text-sm font-medium break-words">{String(ef.value ?? '—')}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}

                    {/* Summary */}
                    {file.summary && (
                        <><Separator /><div><h3 className="text-xs font-semibold uppercase tracking-wider mb-2">Document Summary</h3><p className="text-sm text-muted-foreground leading-relaxed">{file.summary}</p></div></>
                    )}

                    {/* Text Preview */}
                    {file.extracted_text_preview && (
                        <><Separator /><div><h3 className="text-xs font-semibold uppercase tracking-wider mb-2">Text Preview</h3><pre className="whitespace-pre-wrap text-xs text-muted-foreground leading-relaxed max-h-60 overflow-y-auto rounded-lg bg-muted/50 p-3 font-mono">{file.extracted_text_preview}</pre></div></>
                    )}

                    {/* Error */}
                    {file.error_message && (
                        <><Separator /><Card className="border-destructive/50 bg-destructive/5 p-3"><div className="flex items-start gap-2"><AlertCircle className="size-4 text-destructive shrink-0 mt-0.5" /><p className="text-xs text-destructive break-words">{file.error_message}</p></div></Card></>
                    )}
                </div>
            </ScrollArea>
        </div>
    );
}

/* ── Main Section ────────────────────────────────────────────────── */

export function FilesBrowserSection({
    files,
    onDelete,
}: {
    files: ProcessedFileSummary[];
    onDelete: (id: string) => void;
}) {
    const [search, setSearch] = useState('');
    const [typeFilter, setTypeFilter] = useState<string | null>(null);
    const [selectedFileId, setSelectedFileId] = useState<string | null>(null);

    // Only show completed files (done + error)
    const completedFiles = useMemo(() => files.filter((f) => f.status === 'done' || f.status === 'error'), [files]);

    const distinctTypes = useMemo(() => {
        const types = new Set<string>();
        for (const f of completedFiles) { if (f.classification_concept_id) types.add(f.classification_concept_id); }
        return Array.from(types).sort();
    }, [completedFiles]);

    const filtered = useMemo(() => {
        let result = completedFiles;
        if (search) {
            const q = search.toLowerCase();
            result = result.filter((f) => f.filename.toLowerCase().includes(q) || f.classification_concept_id?.toLowerCase().includes(q));
        }
        if (typeFilter) result = result.filter((f) => f.classification_concept_id === typeFilter);
        return result;
    }, [completedFiles, search, typeFilter]);

    const groups = useMemo(() => groupFiles(filtered), [filtered]);
    const totalCount = useMemo(() => groups.reduce((acc, g) => acc + 1 + g.children.length, 0), [groups]);

    return (
        <div className="h-full flex flex-col space-y-4">
            {/* Search + Type Filter + Count */}
            <div className="flex items-center gap-3 flex-wrap shrink-0">
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
                        <button onClick={() => setSearch('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                            <X className="size-3.5" />
                        </button>
                    )}
                </div>
                <TypeFilter types={distinctTypes} selected={typeFilter} onSelect={setTypeFilter} />
                <span className="text-xs text-muted-foreground tabular-nums ml-auto">{totalCount} file{totalCount !== 1 ? 's' : ''}</span>
            </div>

            {/* Content with optional detail panel */}
            <div className="flex-1 min-h-0">
                {selectedFileId ? (
                    <ResizablePanelGroup orientation="horizontal" className="h-full rounded-lg border">
                        <ResizablePanel defaultSize={55} minSize={35}>
                            <ScrollArea className="h-full">
                                <FilesTable groups={groups} selectedId={selectedFileId} onSelect={setSelectedFileId} onDelete={onDelete} />
                            </ScrollArea>
                        </ResizablePanel>
                        <ResizableHandle withHandle />
                        <ResizablePanel defaultSize={45} minSize={30}>
                            <DetailPanel fileId={selectedFileId} onClose={() => setSelectedFileId(null)} />
                        </ResizablePanel>
                    </ResizablePanelGroup>
                ) : (
                    <FilesTable groups={groups} selectedId={selectedFileId} onSelect={setSelectedFileId} onDelete={onDelete} />
                )}
            </div>
        </div>
    );
}
