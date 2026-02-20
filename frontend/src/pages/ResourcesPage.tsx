/**
 * ResourcesPage — Browse all processed resources.
 *
 * 3-level hierarchy:
 *   L1 — Classification concept accordion (e.g. "Invoice", "Unclassified")
 *   L2 — Resource Name group (PDF filename or URL)
 *   L3 — Individual resource objects extracted from that source
 *
 * Features:
 *   • Full-text search + type filter
 *   • Delete at resource-name level (cascading) or individual object level
 *   • Resizable detail panel for inspecting metadata
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Search,
    Loader2,
    FileText,
    ChevronDown,
    ChevronRight,
    Trash2,
    AlertCircle,
    CheckCircle2,
    Clock,
    RefreshCw,
    RotateCcw,
    Tag,
    Database,
    X,
    Globe,
    File,
    ExternalLink,
} from 'lucide-react';
import { useResources, useResourceDetail } from '@/hooks/use-resources';
import { resourcesApi } from '@/lib/resources-api';
import { ontologyApi } from '@/lib/ontology-api';
import type { ResourceSummary, ResourceDetail, MetadataField, ExtraField } from '@/types/resources';
import type { ConceptSummary } from '@/types/ontology';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
    ResizablePanelGroup,
    ResizablePanel,
    ResizableHandle,
} from '@/components/ui/resizable';

/* ── Status helpers ──────────────────────────────────────────────── */

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
    done: { icon: <CheckCircle2 className="size-3.5" />, color: 'text-emerald-500', label: 'Done' },
    error: { icon: <AlertCircle className="size-3.5" />, color: 'text-destructive', label: 'Error' },
    pending: { icon: <Clock className="size-3.5" />, color: 'text-amber-500', label: 'Pending' },
    extracting_text: { icon: <RefreshCw className="size-3.5 animate-spin" />, color: 'text-blue-500', label: 'Extracting' },
    classifying: { icon: <RefreshCw className="size-3.5 animate-spin" />, color: 'text-blue-500', label: 'Classifying' },
    extracting_metadata: { icon: <RefreshCw className="size-3.5 animate-spin" />, color: 'text-blue-500', label: 'Metadata' },
};

function StatusBadge({ status }: { status: string }) {
    const cfg = STATUS_CONFIG[status] ?? { icon: <Clock className="size-3.5" />, color: 'text-muted-foreground', label: status };
    return (
        <span className={`inline-flex items-center gap-1 text-xs font-medium ${cfg.color}`}>
            {cfg.icon}
            {cfg.label}
        </span>
    );
}

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
    return new Date(iso).toLocaleString();
}

/* ── Grouping types ──────────────────────────────────────────────── */

interface ResourceNameEntry {
    /** Display label (filename or URL) */
    name: string;
    /** The root resource ID used for group-level deletion */
    rootId: string;
    /** Whether this is a URL-based resource */
    isUrl: boolean;
    /** All resource objects within this name group */
    items: ResourceSummary[];
}

interface ConceptGroup {
    concept: string;
    nameGroups: ResourceNameEntry[];
    totalCount: number;
}

/* ── Page ─────────────────────────────────────────────────────────── */

export function ResourcesPage() {
    const { resources, loading, error, refetch } = useResources();
    const [search, setSearch] = useState('');
    const [typeFilter, setTypeFilter] = useState<string | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);

    // Unique concept types for the filter dropdown
    const conceptTypes = useMemo(() => {
        const types = new Set<string>();
        resources.forEach((r) => {
            if (r.classification_concept_id) types.add(r.classification_concept_id);
        });
        return Array.from(types).sort();
    }, [resources]);

    // Filter resources
    const filtered = useMemo(() => {
        return resources.filter((r) => {
            if (typeFilter && r.classification_concept_id !== typeFilter) return false;
            if (search) {
                const q = search.toLowerCase();
                const name = (r.display_name ?? r.filename).toLowerCase();
                const concept = (r.classification_concept_id ?? '').toLowerCase();
                if (!name.includes(q) && !concept.includes(q) && !r.filename.toLowerCase().includes(q)) return false;
            }
            return true;
        });
    }, [resources, search, typeFilter]);

    // Build 3-level hierarchy: Concept → Resource Name → Objects
    const groups: ConceptGroup[] = useMemo(() => {
        // Step 1: group by concept
        const conceptMap = new Map<string, ResourceSummary[]>();
        for (const r of filtered) {
            const key = r.concept_label ?? r.classification_concept_id ?? 'Unclassified';
            const list = conceptMap.get(key) ?? [];
            list.push(r);
            conceptMap.set(key, list);
        }

        // Step 2: within each concept, group by resource name
        const result: ConceptGroup[] = [];
        for (const [concept, items] of Array.from(conceptMap.entries()).sort(([a], [b]) => a.localeCompare(b))) {
            // Group by origin_file_id first; standalone resources by their own id
            const nameMap = new Map<string, ResourceSummary[]>();
            for (const item of items) {
                const groupKey = item.origin_file_id ?? item.id;
                const list = nameMap.get(groupKey) ?? [];
                list.push(item);
                nameMap.set(groupKey, list);
            }

            const nameGroups: ResourceNameEntry[] = [];
            for (const [, groupItems] of nameMap) {
                // Find the root resource (no origin_file_id) or use the first item
                const root = groupItems.find((r) => !r.origin_file_id) ?? groupItems[0];
                const isUrl = root.original_path.startsWith('http://') || root.original_path.startsWith('https://');

                nameGroups.push({
                    name: isUrl ? root.original_path : root.filename,
                    rootId: root.id,
                    isUrl,
                    items: groupItems.sort((a, b) => {
                        // Sort by page_range if available, otherwise by filename
                        if (a.page_range && b.page_range) {
                            const aStart = parseInt(a.page_range.split('-')[0], 10);
                            const bStart = parseInt(b.page_range.split('-')[0], 10);
                            return aStart - bStart;
                        }
                        return (a.display_name ?? a.filename).localeCompare(b.display_name ?? b.filename);
                    }),
                });
            }

            // Sort name groups alphabetically
            nameGroups.sort((a, b) => a.name.localeCompare(b.name));

            result.push({
                concept,
                nameGroups,
                totalCount: items.length,
            });
        }

        return result;
    }, [filtered]);

    // Delete a single resource object
    const handleDeleteObject = useCallback(async (id: string) => {
        try {
            await resourcesApi.delete(id);
            if (selectedId === id) setSelectedId(null);
            await refetch();
        } catch (err) {
            console.error('Delete failed:', err);
        }
    }, [selectedId, refetch]);

    // Delete an entire resource-name group (uses root ID — backend cascades)
    const handleDeleteGroup = useCallback(async (rootId: string) => {
        try {
            await resourcesApi.delete(rootId);
            if (selectedId === rootId) setSelectedId(null);
            await refetch();
        } catch (err) {
            console.error('Delete group failed:', err);
        }
    }, [selectedId, refetch]);

    return (
        <div className="flex h-full flex-col">
            {/* Header */}
            <div className="pb-4">
                <div className="flex items-center gap-2 mb-1">
                    <Database className="size-5 text-muted-foreground" />
                    <h1 className="text-2xl font-bold tracking-tight">Resources</h1>
                    <Badge variant="secondary" className="ml-2">{resources.length}</Badge>
                </div>
                <p className="text-muted-foreground text-sm">
                    Browse all processed documents across data sources.
                </p>
            </div>

            {/* Toolbar */}
            <div className="flex items-center gap-2 mb-4">
                <div className="relative flex-1 max-w-sm">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search resources…"
                        className="w-full rounded-lg border bg-background pl-8 pr-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring/30"
                    />
                </div>

                {/* Type filter */}
                {conceptTypes.length > 0 && (
                    <select
                        value={typeFilter ?? ''}
                        onChange={(e) => setTypeFilter(e.target.value || null)}
                        className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring/30"
                    >
                        <option value="">All types</option>
                        {conceptTypes.map((t) => (
                            <option key={t} value={t}>{t}</option>
                        ))}
                    </select>
                )}

                <Button variant="ghost" size="icon" onClick={refetch} title="Refresh">
                    <RefreshCw className="size-4" />
                </Button>
            </div>

            {/* Error state */}
            {error && (
                <Card className="mb-4 border-destructive/50 bg-destructive/5">
                    <CardContent className="flex items-center gap-2 py-3 text-sm text-destructive">
                        <AlertCircle className="size-4 shrink-0" />
                        {error}
                    </CardContent>
                </Card>
            )}

            {/* Loading */}
            {loading && (
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="size-8 animate-spin text-primary" />
                </div>
            )}

            {/* Empty */}
            {!loading && resources.length === 0 && (
                <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center">
                    <div className="flex size-14 items-center justify-center rounded-2xl bg-muted/60">
                        <FileText className="size-7 text-muted-foreground" />
                    </div>
                    <div>
                        <h3 className="font-semibold">No resources yet</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            Upload and process files via Data Sources to see them here.
                        </p>
                    </div>
                </div>
            )}

            {/* Main content: list + detail panel */}
            {!loading && filtered.length > 0 && (
                <ResizablePanelGroup orientation="horizontal" className="flex-1 rounded-lg border">
                    {/* Resource list */}
                    <ResizablePanel defaultSize={selectedId ? 55 : 100} minSize={35}>
                        <div className="h-full overflow-y-auto p-2 space-y-1">
                            {groups.map((group) => (
                                <ConceptAccordion
                                    key={group.concept}
                                    group={group}
                                    selectedId={selectedId}
                                    onSelect={setSelectedId}
                                    onDeleteObject={handleDeleteObject}
                                    onDeleteGroup={handleDeleteGroup}
                                />
                            ))}
                        </div>
                    </ResizablePanel>

                    {/* Detail panel */}
                    {selectedId && (
                        <>
                            <ResizableHandle withHandle />
                            <ResizablePanel defaultSize={45} minSize={25}>
                                <DetailPanel
                                    resourceId={selectedId}
                                    onClose={() => setSelectedId(null)}
                                    onReprocess={async (conceptId?: string) => {
                                        await resourcesApi.reprocess(selectedId, conceptId);
                                        await refetch();
                                    }}
                                />
                            </ResizablePanel>
                        </>
                    )}
                </ResizablePanelGroup>
            )}
        </div>
    );
}

/* ── L1: Concept Accordion ───────────────────────────────────────── */

function ConceptAccordion({
    group,
    selectedId,
    onSelect,
    onDeleteObject,
    onDeleteGroup,
}: {
    group: ConceptGroup;
    selectedId: string | null;
    onSelect: (id: string) => void;
    onDeleteObject: (id: string) => void;
    onDeleteGroup: (rootId: string) => void;
}) {
    const [open, setOpen] = useState(true);

    return (
        <div className="rounded-lg border bg-card">
            <button
                className="flex w-full items-center gap-2 px-3 py-2 text-sm font-medium hover:bg-accent/50 rounded-t-lg transition-colors"
                onClick={() => setOpen(!open)}
            >
                {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                <Tag className="size-3.5 text-muted-foreground" />
                <span className="truncate">{group.concept}</span>
                <Badge variant="secondary" className="ml-auto text-xs">{group.totalCount}</Badge>
            </button>

            {open && (
                <div className="border-t space-y-px">
                    {group.nameGroups.map((entry) => (
                        <ResourceNameGroup
                            key={entry.rootId}
                            entry={entry}
                            selectedId={selectedId}
                            onSelect={onSelect}
                            onDeleteObject={onDeleteObject}
                            onDeleteGroup={onDeleteGroup}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

/* ── L2: Resource Name Group ─────────────────────────────────────── */

function ResourceNameGroup({
    entry,
    selectedId,
    onSelect,
    onDeleteObject,
    onDeleteGroup,
}: {
    entry: ResourceNameEntry;
    selectedId: string | null;
    onSelect: (id: string) => void;
    onDeleteObject: (id: string) => void;
    onDeleteGroup: (rootId: string) => void;
}) {
    const [expanded, setExpanded] = useState(false);
    const isSingle = entry.items.length === 1;

    // For single-item groups, clicking the row selects the item directly
    if (isSingle) {
        const item = entry.items[0];
        return (
            <ResourceRow
                resource={item}
                isSelected={item.id === selectedId}
                onSelect={() => onSelect(item.id)}
                onDelete={() => onDeleteObject(item.id)}
                indent={1}
                showSourceIcon={entry.isUrl}
            />
        );
    }

    // Multi-item group: expandable header + children
    return (
        <div>
            {/* Group header */}
            <div
                className="group flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-accent/40 transition-colors"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="pl-2">
                    {expanded ? <ChevronDown className="size-3.5 text-muted-foreground" /> : <ChevronRight className="size-3.5 text-muted-foreground" />}
                </div>
                {entry.isUrl ? (
                    <Globe className="size-4 shrink-0 text-blue-500" />
                ) : (
                    <File className="size-4 shrink-0 text-muted-foreground" />
                )}
                <span className="flex-1 min-w-0 text-sm font-medium truncate">
                    {entry.name}
                </span>
                <Badge variant="outline" className="text-[10px] shrink-0">
                    {entry.items.length} objects
                </Badge>
                <button
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/10 hover:text-destructive transition-all shrink-0"
                    onClick={(e) => { e.stopPropagation(); onDeleteGroup(entry.rootId); }}
                    title="Delete all objects from this source"
                >
                    <Trash2 className="size-3.5" />
                </button>
            </div>

            {/* Child resource objects */}
            {expanded && (
                <div className="border-t border-dashed">
                    {entry.items.map((r) => (
                        <ResourceRow
                            key={r.id}
                            resource={r}
                            isSelected={r.id === selectedId}
                            onSelect={() => onSelect(r.id)}
                            onDelete={() => onDeleteObject(r.id)}
                            indent={2}
                            showSourceIcon={false}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}

/* ── L3: Resource Row ────────────────────────────────────────────── */

function ResourceRow({
    resource,
    isSelected,
    onSelect,
    onDelete,
    indent = 0,
    showSourceIcon = false,
}: {
    resource: ResourceSummary;
    isSelected: boolean;
    onSelect: () => void;
    onDelete: () => void;
    indent?: number;
    showSourceIcon?: boolean;
}) {
    const paddingLeft = indent === 0 ? 'pl-3' : indent === 1 ? 'pl-5' : 'pl-10';

    return (
        <div
            className={`flex items-center gap-3 ${paddingLeft} pr-3 py-2 cursor-pointer transition-colors hover:bg-accent/40 group ${isSelected ? 'bg-accent/60' : ''
                }`}
            onClick={onSelect}
        >
            {showSourceIcon ? (
                resource.original_path.startsWith('http') ? (
                    <Globe className="size-4 shrink-0 text-blue-500" />
                ) : (
                    <File className="size-4 shrink-0 text-muted-foreground" />
                )
            ) : (
                <FileText className="size-3.5 shrink-0 text-muted-foreground/60" />
            )}

            <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">
                    {resource.display_name ?? resource.filename}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{formatBytes(resource.file_size)}</span>
                    <span>•</span>
                    <span>{resource.mime_type}</span>
                    {resource.page_range && (
                        <>
                            <span>•</span>
                            <span>pp. {resource.page_range}</span>
                        </>
                    )}
                </div>
            </div>

            <StatusBadge status={resource.status} />

            <button
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/10 hover:text-destructive transition-all"
                onClick={(e) => { e.stopPropagation(); onDelete(); }}
                title="Delete"
            >
                <Trash2 className="size-3.5" />
            </button>
        </div>
    );
}

/* ── Detail Panel ────────────────────────────────────────────────── */

function DetailPanel({ resourceId, onClose, onReprocess }: { resourceId: string; onClose: () => void; onReprocess: (conceptId?: string) => Promise<void> }) {
    const { resource, loading, error, refetch: refetchDetail } = useResourceDetail(resourceId);
    const [viewMode, setViewMode] = useState<'formatted' | 'raw'>('formatted');
    const [reprocessing, setReprocessing] = useState(false);
    const [overrideConcept, setOverrideConcept] = useState<string | null>(null);
    const [conceptList, setConceptList] = useState<ConceptSummary[]>([]);

    // Fetch concept list for the dropdown
    useEffect(() => {
        ontologyApi.listConcepts().then((concepts) => {
            // Only show non-abstract concepts that can be assigned
            setConceptList(concepts.filter((c) => !c.abstract));
        }).catch(() => { });
    }, []);

    // Reset override when resource changes
    useEffect(() => {
        setOverrideConcept(null);
    }, [resourceId]);

    const handleReprocess = async () => {
        setReprocessing(true);
        try {
            await onReprocess(overrideConcept ?? undefined);
            await refetchDetail();
            setOverrideConcept(null);
        } catch (err) {
            console.error('Reprocess failed:', err);
        } finally {
            setReprocessing(false);
        }
    };

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center">
                <Loader2 className="size-6 animate-spin text-primary" />
            </div>
        );
    }

    if (error || !resource) {
        return (
            <div className="flex h-full items-center justify-center p-4 text-sm text-destructive">
                {error ?? 'Resource not found'}
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b">
                <h3 className="text-sm font-semibold truncate">{resource.filename}</h3>
                <div className="flex items-center gap-1 shrink-0">
                    {resource.stored_path && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => window.open(resourcesApi.viewUrl(resourceId), '_blank')}
                            className="gap-1.5 text-xs h-7"
                            title="View stored resource"
                        >
                            <ExternalLink className="size-3.5" />
                            View
                        </Button>
                    )}
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleReprocess}
                        disabled={reprocessing}
                        className="gap-1.5 text-xs h-7"
                        title={overrideConcept ? `Reprocess as "${overrideConcept}"` : 'Reprocess this resource'}
                    >
                        {reprocessing ? (
                            <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                            <RotateCcw className="size-3.5" />
                        )}
                        {overrideConcept ? 'Reprocess as…' : 'Reprocess'}
                    </Button>
                    <Button variant="ghost" size="icon" onClick={onClose} className="size-7">
                        <X className="size-4" />
                    </Button>
                </div>
            </div>

            {/* View mode toggle */}
            <div className="flex gap-1 px-4 pt-3">
                <button
                    className={`px-3 py-1 text-xs rounded-md transition-colors ${viewMode === 'formatted' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent'}`}
                    onClick={() => setViewMode('formatted')}
                >
                    Formatted
                </button>
                <button
                    className={`px-3 py-1 text-xs rounded-md transition-colors ${viewMode === 'raw' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent'}`}
                    onClick={() => setViewMode('raw')}
                >
                    Raw JSON
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {viewMode === 'raw' ? (
                    <pre className="text-xs bg-muted/50 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words">
                        {JSON.stringify(resource, null, 2)}
                    </pre>
                ) : (
                    <FormattedDetail
                        resource={resource}
                        overrideConcept={overrideConcept}
                        conceptList={conceptList}
                        onConceptChange={setOverrideConcept}
                    />
                )}
            </div>
        </div>
    );
}

/* ── Formatted Detail ────────────────────────────────────────────── */

function FormattedDetail({ resource, overrideConcept, conceptList, onConceptChange }: {
    resource: ResourceDetail;
    overrideConcept: string | null;
    conceptList: ConceptSummary[];
    onConceptChange: (id: string | null) => void;
}) {
    return (
        <div className="space-y-4">
            {/* General info */}
            <Card>
                <CardHeader className="py-3 px-4">
                    <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">General</CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-3 space-y-2 text-sm">
                    <InfoRow label="Status" value={<StatusBadge status={resource.status} />} />
                    <InfoRow label="File Size" value={formatBytes(resource.file_size)} />
                    <InfoRow label="MIME Type" value={resource.mime_type} />
                    <InfoRow label="Uploaded" value={formatDate(resource.uploaded_at)} />
                    {resource.processed_at && <InfoRow label="Processed" value={formatDate(resource.processed_at)} />}
                    {resource.processing_time_ms != null && <InfoRow label="Processing Time" value={`${resource.processing_time_ms} ms`} />}
                    {resource.language && <InfoRow label="Language" value={resource.language} />}
                    {resource.data_source_id && <InfoRow label="Data Source" value={resource.data_source_name ?? resource.data_source_id} />}
                    {resource.stored_path && <InfoRow label="Stored Path" value={resource.stored_path} />}
                </CardContent>
            </Card>

            {/* Classification */}
            <Card>
                <CardHeader className="py-3 px-4">
                    <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Classification</CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-3 space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground font-medium">Concept</span>
                        <div className="flex items-center gap-2">
                            {resource.classification && !overrideConcept && (
                                <Badge variant="secondary">{resource.classification.primary_concept_id}</Badge>
                            )}
                            <select
                                className="text-xs border rounded-md px-2 py-1 bg-background cursor-pointer max-w-[180px]"
                                value={overrideConcept ?? resource.classification?.primary_concept_id ?? ''}
                                onChange={(e) => {
                                    const val = e.target.value;
                                    const originalConcept = resource.classification?.primary_concept_id;
                                    onConceptChange(val && val !== originalConcept ? val : null);
                                }}
                            >
                                {!resource.classification && <option value="">Select concept…</option>}
                                {conceptList.map((c) => (
                                    <option key={c.id} value={c.id}>
                                        {c.label} ({c.layer})
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    {overrideConcept && (
                        <div className="flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 dark:bg-amber-950/30 dark:text-amber-400 rounded px-2 py-1">
                            <RefreshCw className="size-3" />
                            Will reprocess as <strong>{overrideConcept}</strong>
                        </div>
                    )}
                    {resource.classification && (
                        <>
                            <InfoRow label="Confidence" value={`${Math.round(resource.classification.confidence * 100)}%`} />
                            {resource.classification.signals.length > 0 && (
                                <div className="pt-1">
                                    <span className="text-xs text-muted-foreground font-medium">Signals</span>
                                    <div className="mt-1 space-y-1">
                                        {resource.classification.signals.map((s, i) => (
                                            <div key={i} className="text-xs flex items-center gap-2 bg-muted/50 rounded px-2 py-1">
                                                <Badge variant="outline" className="text-[10px]">{s.method}</Badge>
                                                <span className="truncate">{s.details}</span>
                                                <span className="ml-auto text-muted-foreground">{Math.round(s.score * 100)}%</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </CardContent>
            </Card>

            {/* Summary */}
            {resource.summary && (
                <Card>
                    <CardHeader className="py-3 px-4">
                        <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Summary</CardTitle>
                    </CardHeader>
                    <CardContent className="px-4 pb-3 text-sm">
                        {resource.summary}
                    </CardContent>
                </Card>
            )}

            {/* Metadata */}
            {Object.keys(resource.metadata).length > 0 && (
                <Card>
                    <CardHeader className="py-3 px-4">
                        <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Extracted Metadata</CardTitle>
                    </CardHeader>
                    <CardContent className="px-4 pb-3 space-y-2">
                        {Object.entries(resource.metadata).map(([key, field]) => (
                            <MetadataRow key={key} fieldName={key} field={field} />
                        ))}
                    </CardContent>
                </Card>
            )}

            {/* Extra fields */}
            {resource.extra_fields.length > 0 && (
                <Card>
                    <CardHeader className="py-3 px-4">
                        <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Additional Fields</CardTitle>
                    </CardHeader>
                    <CardContent className="px-4 pb-3 space-y-2">
                        {resource.extra_fields.map((f, i) => (
                            <ExtraFieldRow key={i} field={f} />
                        ))}
                    </CardContent>
                </Card>
            )}

            {/* Text preview */}
            {resource.extracted_text_preview && (
                <Card>
                    <CardHeader className="py-3 px-4">
                        <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Text Preview</CardTitle>
                    </CardHeader>
                    <CardContent className="px-4 pb-3">
                        <pre className="text-xs bg-muted/50 rounded-lg p-3 whitespace-pre-wrap break-words max-h-64 overflow-y-auto">
                            {resource.extracted_text_preview}
                        </pre>
                    </CardContent>
                </Card>
            )}

            {/* Error */}
            {resource.error_message && (
                <Card className="border-destructive/50 bg-destructive/5">
                    <CardHeader className="py-3 px-4">
                        <CardTitle className="text-xs font-semibold text-destructive uppercase tracking-wider">Error</CardTitle>
                    </CardHeader>
                    <CardContent className="px-4 pb-3 text-sm text-destructive">
                        {resource.error_message}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

/* ── Helper Components ───────────────────────────────────────────── */

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
    return (
        <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-muted-foreground">{label}</span>
            <span className="text-xs font-medium text-right">{value}</span>
        </div>
    );
}

function MetadataRow({ fieldName, field }: { fieldName: string; field: MetadataField }) {
    const displayValue = typeof field.value === 'object' && field.value !== null
        ? JSON.stringify(field.value)
        : String(field.value ?? '—');

    return (
        <div className="text-xs space-y-0.5">
            <div className="flex items-center justify-between">
                <span className="font-medium capitalize">{fieldName.replace(/_/g, ' ')}</span>
                <span className="text-muted-foreground">{Math.round(field.confidence * 100)}%</span>
            </div>
            <div className="text-muted-foreground">{displayValue}</div>
            {field.source_quote && (
                <div className="text-[10px] text-muted-foreground/70 italic border-l-2 border-muted pl-2">
                    "{field.source_quote}"
                </div>
            )}
        </div>
    );
}

function ExtraFieldRow({ field }: { field: ExtraField }) {
    return (
        <div className="text-xs space-y-0.5">
            <div className="flex items-center justify-between">
                <span className="font-medium capitalize">{field.field_name.replace(/_/g, ' ')}</span>
                <span className="text-muted-foreground">{Math.round(field.confidence * 100)}%</span>
            </div>
            <div className="text-muted-foreground">{String(field.value ?? '—')}</div>
            {field.source_quote && (
                <div className="text-[10px] text-muted-foreground/70 italic border-l-2 border-muted pl-2">
                    "{field.source_quote}"
                </div>
            )}
        </div>
    );
}
