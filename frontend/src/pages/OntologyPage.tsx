import { useEffect, useState, useCallback, useMemo } from 'react';
import {
    ChevronRight,
    ChevronDown,
    Search,
    Plus,
    Layers,
    Network,
    BookOpen,
    Trash2,
    Info,
    GitBranch,
    X,
    Pencil,
    Save,
    XCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ontologyApi } from '@/lib/ontology-api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from '@/components/ui/resizable';
import { TooltipProvider } from '@/components/ui/tooltip';
import { CreateConceptDialog } from '@/pages/create-concept-wizard/CreateConceptDialog';
import type {
    ConceptDetail,
    ConceptTreeNode,
    EmbeddedType,
    InheritedPropertyGroup,
    OntologyStats,
} from '@/types/ontology';


/* ────────────────────────────────────────────────────────────────────
   LAYER STYLING
   ──────────────────────────────────────────────────────────────────── */

const LAYER_STYLES: Record<string, { bg: string; text: string; label: string }> = {
    L1: { bg: 'bg-zinc-100 dark:bg-zinc-800', text: 'text-zinc-600 dark:text-zinc-400', label: 'Foundation' },
    L2: { bg: 'bg-blue-100 dark:bg-blue-900/40', text: 'text-blue-700 dark:text-blue-300', label: 'Enterprise' },
    L3: { bg: 'bg-emerald-100 dark:bg-emerald-900/40', text: 'text-emerald-700 dark:text-emerald-300', label: 'Industry' },
    L4: { bg: 'bg-amber-100 dark:bg-amber-900/40', text: 'text-amber-700 dark:text-amber-300', label: 'Organisation' },
};

function LayerBadge({ layer, size = 'sm' }: { layer: string; size?: 'sm' | 'xs' }) {
    const style = LAYER_STYLES[layer] ?? LAYER_STYLES.L1;
    return (
        <span
            className={cn(
                'inline-flex items-center font-mono font-semibold rounded-md',
                style.bg,
                style.text,
                size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-1 py-px text-[9px]',
            )}
        >
            {layer}
        </span>
    );
}


/* ────────────────────────────────────────────────────────────────────
   PROPERTY TYPE CELL — clickable when referring to an embedded type
   ──────────────────────────────────────────────────────────────────── */

/**
 * Strip trailing `[]` from a type string and check if the base name
 * matches any embedded type in the current concept's `embedded_types`.
 */
function PropertyTypeCell({
    typeStr,
    embeddedTypes,
    onEmbeddedTypeClick,
}: {
    typeStr: string;
    embeddedTypes: EmbeddedType[];
    onEmbeddedTypeClick: (et: EmbeddedType) => void;
}) {
    // Normalise: "InvoiceLineItem[]" → baseName "InvoiceLineItem"
    const isArray = typeStr.endsWith('[]');
    const baseName = isArray ? typeStr.slice(0, -2) : typeStr;
    const match = embeddedTypes.find((et) => et.id === baseName);

    if (!match) {
        return <span>{typeStr}</span>;
    }

    return (
        <button
            type="button"
            onClick={() => onEmbeddedTypeClick(match)}
            className="text-primary hover:underline underline-offset-2 cursor-pointer font-medium"
        >
            {typeStr}
        </button>
    );
}


/* ────────────────────────────────────────────────────────────────────
   TREE VIEW
   ──────────────────────────────────────────────────────────────────── */

function TreeNode({
    node,
    selectedId,
    onSelect,
    depth = 0,
    searchQuery = '',
}: {
    node: ConceptTreeNode;
    selectedId: string | null;
    onSelect: (id: string) => void;
    depth?: number;
    searchQuery?: string;
}) {
    const hasChildren = node.children.length > 0;
    const isSelected = selectedId === node.id;
    const [expanded, setExpanded] = useState(depth < 2);

    // Auto-expand if the selected node is a descendant
    const containsSelected = useMemo(() => {
        if (!selectedId) return false;
        const find = (n: ConceptTreeNode): boolean =>
            n.id === selectedId || n.children.some(find);
        return node.children.some(find);
    }, [node, selectedId]);

    useEffect(() => {
        if (containsSelected) setExpanded(true);
    }, [containsSelected]);

    // Auto-expand if search matches a descendant
    const matchesSearch = useMemo(() => {
        if (!searchQuery) return true;
        const q = searchQuery.toLowerCase();
        const matches = (n: ConceptTreeNode): boolean =>
            n.label.toLowerCase().includes(q) ||
            n.id.toLowerCase().includes(q) ||
            n.children.some(matches);
        return matches(node);
    }, [node, searchQuery]);

    useEffect(() => {
        if (searchQuery && matchesSearch) setExpanded(true);
    }, [searchQuery, matchesSearch]);

    if (!matchesSearch) return null;

    const selfMatches =
        !searchQuery ||
        node.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
        node.id.toLowerCase().includes(searchQuery.toLowerCase());

    return (
        <div>
            <button
                onClick={() => {
                    if (hasChildren) setExpanded(!expanded);
                    onSelect(node.id);
                }}
                className={cn(
                    'flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-sm transition-colors',
                    'hover:bg-accent/60',
                    isSelected && 'bg-primary/10 text-primary font-medium',
                    !selfMatches && 'opacity-50',
                )}
                style={{ paddingLeft: `${depth * 16 + 8}px` }}
            >
                {hasChildren ? (
                    expanded ? (
                        <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
                    ) : (
                        <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
                    )
                ) : (
                    <span className="w-3.5 shrink-0" />
                )}
                <LayerBadge layer={node.layer} size="xs" />
                <span className="truncate text-left">{node.label}</span>
                {node.abstract && (
                    <span className="ml-auto text-[10px] italic text-muted-foreground">abstract</span>
                )}
            </button>

            {expanded && hasChildren && (
                <div>
                    {node.children.map((child) => (
                        <TreeNode
                            key={child.id}
                            node={child}
                            selectedId={selectedId}
                            onSelect={onSelect}
                            depth={depth + 1}
                            searchQuery={searchQuery}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}


/* ────────────────────────────────────────────────────────────────────
   INHERITED GROUP (collapsible per ancestor)
   ──────────────────────────────────────────────────────────────────── */

function InheritedGroupSection({
    group,
    embeddedTypes,
    onEmbeddedTypeClick,
}: {
    group: InheritedPropertyGroup;
    embeddedTypes: EmbeddedType[];
    onEmbeddedTypeClick: (et: EmbeddedType) => void;
}) {
    const [open, setOpen] = useState(false);
    const totalItems =
        group.properties.length +
        group.relationships.length +
        (group.extraction_template ? 1 : 0);

    return (
        <div className="rounded-lg border overflow-hidden">
            <button
                onClick={() => setOpen(!open)}
                className="flex w-full items-center gap-2 px-3 py-2.5 text-sm hover:bg-accent/40 transition-colors"
            >
                {open ? (
                    <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
                ) : (
                    <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
                )}
                <LayerBadge layer={group.source_layer} size="xs" />
                <span className="font-medium">{group.source_label}</span>
                <span className="ml-auto text-xs text-muted-foreground">
                    {totalItems} item{totalItems !== 1 ? 's' : ''}
                </span>
            </button>

            {open && (
                <div className="border-t border-l-2 border-l-primary/20 px-3 py-3 space-y-4 bg-muted/20">
                    {/* Properties */}
                    {group.properties.length > 0 && (
                        <div>
                            <h4 className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
                                <BookOpen className="size-3" />
                                Properties
                            </h4>
                            <div className="rounded-md border overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b bg-muted/40">
                                            <th className="text-left px-3 py-1.5 font-medium text-xs">Name</th>
                                            <th className="text-left px-3 py-1.5 font-medium text-xs">Type</th>
                                            <th className="text-left px-3 py-1.5 font-medium text-xs">Required</th>
                                            <th className="text-left px-3 py-1.5 font-medium text-xs">Description</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {group.properties.map((p) => (
                                            <tr key={p.name} className="border-b last:border-0">
                                                <td className="px-3 py-1.5 font-mono text-xs">{p.name}</td>
                                                <td className="px-3 py-1.5 text-xs">
                                                    <PropertyTypeCell
                                                        typeStr={p.type}
                                                        embeddedTypes={embeddedTypes}
                                                        onEmbeddedTypeClick={onEmbeddedTypeClick}
                                                    />
                                                </td>
                                                <td className="px-3 py-1.5 text-xs">
                                                    {p.required ? (
                                                        <span className="text-primary font-medium">Yes</span>
                                                    ) : (
                                                        <span className="text-muted-foreground">No</span>
                                                    )}
                                                </td>
                                                <td className="px-3 py-1.5 text-xs text-muted-foreground">{p.description}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Relationships */}
                    {group.relationships.length > 0 && (
                        <div>
                            <h4 className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
                                <Network className="size-3" />
                                Relationships
                            </h4>
                            <div className="rounded-md border overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b bg-muted/40">
                                            <th className="text-left px-3 py-1.5 font-medium text-xs">Name</th>
                                            <th className="text-left px-3 py-1.5 font-medium text-xs">Target</th>
                                            <th className="text-left px-3 py-1.5 font-medium text-xs">Cardinality</th>
                                            <th className="text-left px-3 py-1.5 font-medium text-xs">Description</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {group.relationships.map((r) => (
                                            <tr key={r.name} className="border-b last:border-0">
                                                <td className="px-3 py-1.5 font-mono text-xs">{r.name}</td>
                                                <td className="px-3 py-1.5 font-mono text-xs">{r.target}</td>
                                                <td className="px-3 py-1.5 text-xs">{r.cardinality}</td>
                                                <td className="px-3 py-1.5 text-xs text-muted-foreground">{r.description}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Extraction Template */}
                    {group.extraction_template && (
                        <div>
                            <h4 className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
                                <Info className="size-3" />
                                Extraction Template
                            </h4>
                            <Card className="p-3 space-y-2">
                                {group.extraction_template.classification_hints.length > 0 && (
                                    <div>
                                        <p className="text-[10px] text-muted-foreground mb-0.5">Classification Hints</p>
                                        <div className="flex flex-wrap gap-1">
                                            {group.extraction_template.classification_hints.map((h) => (
                                                <Badge key={h} variant="secondary" className="text-xs">{h}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {group.extraction_template.file_patterns.length > 0 && (
                                    <div>
                                        <p className="text-[10px] text-muted-foreground mb-0.5">File Patterns</p>
                                        <div className="flex flex-wrap gap-1">
                                            {group.extraction_template.file_patterns.map((p) => (
                                                <code key={p} className="text-xs bg-muted px-1.5 py-0.5 rounded">{p}</code>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </Card>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}


/* ────────────────────────────────────────────────────────────────────
   DETAIL PANEL
   ──────────────────────────────────────────────────────────────────── */

function DetailPanel({
    concept,
    onDelete,
    onUpdated,
    isDeleting,
    onEmbeddedTypeClick,
}: {
    concept: ConceptDetail;
    onDelete: (id: string) => void;
    onUpdated: () => void;
    isDeleting: boolean;
    onEmbeddedTypeClick: (et: EmbeddedType) => void;
}) {
    const canEdit = concept.layer !== 'L1' && concept.layer !== 'L2';
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);

    // ── Edit form state ────────────────────────────────────────────
    const [editLabel, setEditLabel] = useState(concept.label);
    const [editDescription, setEditDescription] = useState(concept.description || '');
    const [editSynonyms, setEditSynonyms] = useState(concept.synonyms.join(', '));
    const [editProperties, setEditProperties] = useState(
        concept.properties.map((p) => ({ ...p }))
    );
    const [editHints, setEditHints] = useState(
        concept.extraction_template?.classification_hints.join(', ') || ''
    );
    const [editPatterns, setEditPatterns] = useState(
        concept.extraction_template?.file_patterns.join(', ') || ''
    );

    // Reset form when concept changes
    useEffect(() => {
        setEditing(false);
        setEditLabel(concept.label);
        setEditDescription(concept.description || '');
        setEditSynonyms(concept.synonyms.join(', '));
        setEditProperties(concept.properties.map((p) => ({ ...p })));
        setEditHints(concept.extraction_template?.classification_hints.join(', ') || '');
        setEditPatterns(concept.extraction_template?.file_patterns.join(', ') || '');
    }, [concept]);

    const handleSave = async () => {
        try {
            setSaving(true);
            const synonymsList = editSynonyms
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);

            const hintsList = editHints
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);
            const patternsList = editPatterns
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);

            await ontologyApi.updateConcept(concept.id, {
                label: editLabel,
                description: editDescription,
                synonyms: synonymsList,
                properties: editProperties.map((p) => ({
                    name: p.name,
                    type: p.type,
                    required: p.required,
                    description: p.description,
                })),
                extraction_template:
                    hintsList.length > 0 || patternsList.length > 0
                        ? {
                            classification_hints: hintsList,
                            file_patterns: patternsList,
                        }
                        : undefined,
            });
            setEditing(false);
            onUpdated();
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Save failed';
            alert(message);
        } finally {
            setSaving(false);
        }
    };

    const handleCancel = () => {
        setEditing(false);
        setEditLabel(concept.label);
        setEditDescription(concept.description || '');
        setEditSynonyms(concept.synonyms.join(', '));
        setEditProperties(concept.properties.map((p) => ({ ...p })));
        setEditHints(concept.extraction_template?.classification_hints.join(', ') || '');
        setEditPatterns(concept.extraction_template?.file_patterns.join(', ') || '');
    };

    const updateProperty = (
        index: number,
        field: 'name' | 'type' | 'required' | 'description',
        value: string | boolean
    ) => {
        setEditProperties((prev) => {
            const next = [...prev];
            next[index] = { ...next[index], [field]: value };
            return next;
        });
    };

    const addProperty = () => {
        setEditProperties((prev) => [
            ...prev,
            { name: '', type: 'string', required: false, default_value: null, description: '' },
        ]);
    };

    const removeProperty = (index: number) => {
        setEditProperties((prev) => prev.filter((_, i) => i !== index));
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        {editing ? (
                            <Input
                                value={editLabel}
                                onChange={(e) => setEditLabel(e.target.value)}
                                className="text-xl font-semibold h-9"
                            />
                        ) : (
                            <h2 className="text-xl font-semibold tracking-tight">{concept.label}</h2>
                        )}
                        <LayerBadge layer={concept.layer} />
                        {concept.abstract && (
                            <Badge variant="outline" className="text-xs">abstract</Badge>
                        )}
                    </div>
                    <p className="text-xs text-muted-foreground font-mono">{concept.id}</p>
                </div>
                {canEdit && (
                    <div className="flex items-center gap-1">
                        {editing ? (
                            <>
                                <Button
                                    variant="default"
                                    size="sm"
                                    onClick={handleSave}
                                    disabled={saving}
                                >
                                    <Save className="size-4 mr-1" />
                                    {saving ? 'Saving…' : 'Save'}
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleCancel}
                                    disabled={saving}
                                >
                                    <XCircle className="size-4 mr-1" />
                                    Cancel
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setEditing(true)}
                                >
                                    <Pencil className="size-4 mr-1" />
                                    Edit
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="text-destructive hover:text-destructive hover:bg-destructive/10"
                                    onClick={() => onDelete(concept.id)}
                                    disabled={isDeleting}
                                >
                                    <Trash2 className="size-4 mr-1" />
                                    Delete
                                </Button>
                            </>
                        )}
                    </div>
                )}
            </div>

            {/* Breadcrumb ancestors */}
            {concept.ancestors && concept.ancestors.length > 0 && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground flex-wrap">
                    {concept.ancestors.map((a, i) => (
                        <span key={a.id} className="flex items-center gap-1">
                            {i > 0 && <ChevronRight className="size-3" />}
                            <LayerBadge layer={a.layer} size="xs" />
                            <span>{a.label}</span>
                        </span>
                    ))}
                    <ChevronRight className="size-3" />
                    <span className="font-medium text-foreground">{concept.label}</span>
                </div>
            )}

            {/* Description */}
            {editing ? (
                <Card className="p-4">
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">Description</label>
                    <textarea
                        value={editDescription}
                        onChange={(e) => setEditDescription(e.target.value)}
                        className="w-full min-h-[80px] text-sm leading-relaxed border rounded-md p-2 bg-background resize-y"
                    />
                </Card>
            ) : concept.description ? (
                <Card className="p-4">
                    <p className="text-sm leading-relaxed">{concept.description}</p>
                </Card>
            ) : null}

            {/* Pillar + Synonyms */}
            <div className="grid grid-cols-2 gap-4">
                {concept.pillar && (
                    <div>
                        <h4 className="text-xs font-medium text-muted-foreground mb-1">Pillar</h4>
                        <Badge variant="secondary" className="capitalize">{concept.pillar}</Badge>
                    </div>
                )}
                <div>
                    <h4 className="text-xs font-medium text-muted-foreground mb-1">Synonyms</h4>
                    {editing ? (
                        <Input
                            value={editSynonyms}
                            onChange={(e) => setEditSynonyms(e.target.value)}
                            placeholder="comma-separated synonyms"
                            className="text-xs h-8"
                        />
                    ) : concept.synonyms.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                            {concept.synonyms.map((s) => (
                                <Badge key={s} variant="outline" className="text-xs">{s}</Badge>
                            ))}
                        </div>
                    ) : (
                        <span className="text-xs text-muted-foreground">None</span>
                    )}
                </div>
            </div>

            {/* Properties */}
            {(concept.properties.length > 0 || editing) && (
                <div>
                    <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                        <BookOpen className="size-3.5" />
                        Properties
                        {editing && (
                            <Button variant="ghost" size="sm" className="ml-auto h-6 text-xs" onClick={addProperty}>
                                <Plus className="size-3 mr-1" /> Add
                            </Button>
                        )}
                    </h3>
                    <div className="rounded-lg border overflow-hidden">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b bg-muted/40">
                                    <th className="text-left px-3 py-2 font-medium text-xs">Name</th>
                                    <th className="text-left px-3 py-2 font-medium text-xs">Type</th>
                                    <th className="text-left px-3 py-2 font-medium text-xs">Required</th>
                                    <th className="text-left px-3 py-2 font-medium text-xs">Description</th>
                                    {editing && <th className="px-2 py-2 w-8" />}
                                </tr>
                            </thead>
                            <tbody>
                                {(editing ? editProperties : concept.properties).map((p, idx) => (
                                    <tr key={editing ? idx : p.name} className="border-b last:border-0">
                                        <td className="px-3 py-2 font-mono text-xs">
                                            {editing ? (
                                                <Input
                                                    value={p.name}
                                                    onChange={(e) => updateProperty(idx, 'name', e.target.value)}
                                                    className="h-7 text-xs font-mono"
                                                />
                                            ) : (
                                                p.name
                                            )}
                                        </td>
                                        <td className="px-3 py-2 text-xs">
                                            {editing ? (
                                                <Input
                                                    value={p.type}
                                                    onChange={(e) => updateProperty(idx, 'type', e.target.value)}
                                                    className="h-7 text-xs"
                                                />
                                            ) : (
                                                <PropertyTypeCell
                                                    typeStr={p.type}
                                                    embeddedTypes={concept.embedded_types ?? []}
                                                    onEmbeddedTypeClick={onEmbeddedTypeClick}
                                                />
                                            )}
                                        </td>
                                        <td className="px-3 py-2 text-xs">
                                            {editing ? (
                                                <input
                                                    type="checkbox"
                                                    checked={p.required}
                                                    onChange={(e) => updateProperty(idx, 'required', e.target.checked)}
                                                    className="accent-primary"
                                                />
                                            ) : p.required ? (
                                                <span className="text-primary font-medium">Yes</span>
                                            ) : (
                                                <span className="text-muted-foreground">No</span>
                                            )}
                                        </td>
                                        <td className="px-3 py-2 text-xs text-muted-foreground">
                                            {editing ? (
                                                <Input
                                                    value={p.description}
                                                    onChange={(e) => updateProperty(idx, 'description', e.target.value)}
                                                    className="h-7 text-xs"
                                                />
                                            ) : (
                                                p.description
                                            )}
                                        </td>
                                        {editing && (
                                            <td className="px-2 py-2">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-6 w-6 p-0 text-destructive"
                                                    onClick={() => removeProperty(idx)}
                                                >
                                                    <Trash2 className="size-3" />
                                                </Button>
                                            </td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Inherited Properties — collapsible per ancestor */}
            {concept.inherited_properties && concept.inherited_properties.length > 0 && (
                <div className="space-y-2">
                    <h3 className="text-sm font-semibold flex items-center gap-1.5">
                        <GitBranch className="size-3.5" />
                        Inherited
                    </h3>
                    {concept.inherited_properties.map((group) => (
                        <InheritedGroupSection
                            key={group.source_id}
                            group={group}
                            embeddedTypes={concept.embedded_types ?? []}
                            onEmbeddedTypeClick={onEmbeddedTypeClick}
                        />
                    ))}
                </div>
            )}

            {/* Relationships */}
            {concept.relationships.length > 0 && (
                <div>
                    <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                        <Network className="size-3.5" />
                        Relationships
                    </h3>
                    <div className="rounded-lg border overflow-hidden">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b bg-muted/40">
                                    <th className="text-left px-3 py-2 font-medium text-xs">Name</th>
                                    <th className="text-left px-3 py-2 font-medium text-xs">Target</th>
                                    <th className="text-left px-3 py-2 font-medium text-xs">Cardinality</th>
                                    <th className="text-left px-3 py-2 font-medium text-xs">Description</th>
                                </tr>
                            </thead>
                            <tbody>
                                {concept.relationships.map((r) => (
                                    <tr key={r.name} className="border-b last:border-0">
                                        <td className="px-3 py-2 font-mono text-xs">{r.name}</td>
                                        <td className="px-3 py-2 font-mono text-xs">{r.target}</td>
                                        <td className="px-3 py-2 text-xs">{r.cardinality}</td>
                                        <td className="px-3 py-2 text-xs text-muted-foreground">{r.description}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Extraction Template */}
            {(concept.extraction_template || editing) && (
                <div>
                    <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                        <Info className="size-3.5" />
                        Extraction Template
                    </h3>
                    <Card className="p-4 space-y-3">
                        <div>
                            <h4 className="text-xs font-medium text-muted-foreground mb-1">
                                Classification Hints
                            </h4>
                            {editing ? (
                                <Input
                                    value={editHints}
                                    onChange={(e) => setEditHints(e.target.value)}
                                    placeholder="comma-separated hints"
                                    className="text-xs h-8"
                                />
                            ) : concept.extraction_template && concept.extraction_template.classification_hints.length > 0 ? (
                                <div className="flex flex-wrap gap-1">
                                    {concept.extraction_template.classification_hints.map((h) => (
                                        <Badge key={h} variant="secondary" className="text-xs">{h}</Badge>
                                    ))}
                                </div>
                            ) : (
                                <span className="text-xs text-muted-foreground">None</span>
                            )}
                        </div>
                        <div>
                            <h4 className="text-xs font-medium text-muted-foreground mb-1">
                                File Patterns
                            </h4>
                            {editing ? (
                                <Input
                                    value={editPatterns}
                                    onChange={(e) => setEditPatterns(e.target.value)}
                                    placeholder="comma-separated patterns"
                                    className="text-xs h-8"
                                />
                            ) : concept.extraction_template && concept.extraction_template.file_patterns.length > 0 ? (
                                <div className="flex flex-wrap gap-1">
                                    {concept.extraction_template.file_patterns.map((p) => (
                                        <code key={p} className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                            {p}
                                        </code>
                                    ))}
                                </div>
                            ) : (
                                <span className="text-xs text-muted-foreground">None</span>
                            )}
                        </div>
                    </Card>
                </div>
            )}

            {/* Mixins */}
            {concept.mixins.length > 0 && (
                <div>
                    <h4 className="text-xs font-medium text-muted-foreground mb-1">Mixins</h4>
                    <div className="flex flex-wrap gap-1">
                        {concept.mixins.map((m) => (
                            <Badge key={m} variant="outline" className="text-xs font-mono">{m}</Badge>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}


/* ────────────────────────────────────────────────────────────────────
   EMBEDDED TYPE INLINE PANEL
   ──────────────────────────────────────────────────────────────────── */

function EmbeddedTypeInlinePanel({
    embeddedType,
    onClose,
}: {
    embeddedType: EmbeddedType;
    onClose: () => void;
}) {
    return (
        <div className="flex h-full flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-start justify-between gap-3 border-b px-5 py-3 shrink-0">
                <div className="space-y-0.5 min-w-0">
                    <div className="flex items-center gap-2">
                        <h2 className="text-base font-semibold tracking-tight truncate">
                            {embeddedType.id}
                        </h2>
                        <LayerBadge layer={embeddedType.layer} />
                    </div>
                    <p className="text-[10px] text-muted-foreground font-mono">Embedded Type</p>
                </div>
                <Button variant="ghost" size="icon" className="shrink-0 size-7" onClick={onClose}>
                    <X className="size-3.5" />
                </Button>
            </div>

            {/* Scrollable content */}
            <ScrollArea className="flex-1 min-h-0">
                <div className="p-5 space-y-4">
                    {/* Description */}
                    {embeddedType.description && (
                        <Card className="p-3">
                            <p className="text-sm leading-relaxed">{embeddedType.description}</p>
                        </Card>
                    )}

                    {/* Synonyms */}
                    {embeddedType.synonyms.length > 0 && (
                        <div>
                            <h4 className="text-xs font-medium text-muted-foreground mb-1">Synonyms</h4>
                            <div className="flex flex-wrap gap-1">
                                {embeddedType.synonyms.map((s) => (
                                    <Badge key={s} variant="outline" className="text-xs">{s}</Badge>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Applies to */}
                    {embeddedType.applies_to.length > 0 && (
                        <div>
                            <h4 className="text-xs font-medium text-muted-foreground mb-1">Applies to</h4>
                            <div className="flex flex-wrap gap-1">
                                {embeddedType.applies_to.map((a) => (
                                    <Badge key={a} variant="secondary" className="text-xs font-mono">{a}</Badge>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Properties table */}
                    {embeddedType.properties.length > 0 && (
                        <div>
                            <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                                <BookOpen className="size-3.5" />
                                Properties
                            </h3>
                            <div className="rounded-lg border overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b bg-muted/40">
                                            <th className="text-left px-3 py-2 font-medium text-xs">Name</th>
                                            <th className="text-left px-3 py-2 font-medium text-xs">Type</th>
                                            <th className="text-left px-3 py-2 font-medium text-xs">Required</th>
                                            <th className="text-left px-3 py-2 font-medium text-xs">Description</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {embeddedType.properties.map((p) => (
                                            <tr key={p.name} className="border-b last:border-0">
                                                <td className="px-3 py-2 font-mono text-xs">{p.name}</td>
                                                <td className="px-3 py-2 text-xs">
                                                    {p.type}
                                                    {p.values.length > 0 && (
                                                        <div className="flex flex-wrap gap-0.5 mt-1">
                                                            {p.values.map((v) => (
                                                                <code
                                                                    key={v}
                                                                    className="text-[10px] bg-muted px-1 py-px rounded"
                                                                >
                                                                    {v}
                                                                </code>
                                                            ))}
                                                        </div>
                                                    )}
                                                </td>
                                                <td className="px-3 py-2 text-xs">
                                                    {p.required ? (
                                                        <span className="text-primary font-medium">Yes</span>
                                                    ) : (
                                                        <span className="text-muted-foreground">No</span>
                                                    )}
                                                </td>
                                                <td className="px-3 py-2 text-xs text-muted-foreground">
                                                    {p.description}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </ScrollArea>
        </div>
    );
}


/* ────────────────────────────────────────────────────────────────────
   STATS BAR
   ──────────────────────────────────────────────────────────────────── */

function StatsBar({ stats }: { stats: OntologyStats }) {
    return (
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{stats.total_concepts} concepts</span>
            <Separator orientation="vertical" className="h-4" />
            {Object.entries(stats.by_layer)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([layer, count]) => (
                    <span key={layer} className="flex items-center gap-1">
                        <LayerBadge layer={layer} size="xs" />
                        {count}
                    </span>
                ))}
            <Separator orientation="vertical" className="h-4" />
            <span>{stats.classifiable_count} classifiable</span>
        </div>
    );
}


/* ────────────────────────────────────────────────────────────────────
   MAIN PAGE
   ──────────────────────────────────────────────────────────────────── */

export function OntologyPage() {
    const [tree, setTree] = useState<ConceptTreeNode[]>([]);
    const [stats, setStats] = useState<OntologyStats | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [selectedDetail, setSelectedDetail] = useState<ConceptDetail | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [loading, setLoading] = useState(true);
    const [createOpen, setCreateOpen] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedEmbeddedType, setSelectedEmbeddedType] = useState<EmbeddedType | null>(null);

    // ── Data fetching ───────────────────────────────────────────────

    const fetchData = useCallback(async () => {
        try {
            setLoading(true);
            const [treeData, statsData] = await Promise.all([
                ontologyApi.getTree(),
                ontologyApi.getStats(),
            ]);
            setTree(treeData);
            setStats(statsData);
            setError(null);
        } catch {
            setError('Failed to load ontology data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Fetch detail when concept is selected
    useEffect(() => {
        if (!selectedId) {
            setSelectedDetail(null);
            return;
        }
        let cancelled = false;
        ontologyApi.getConcept(selectedId).then((detail) => {
            if (!cancelled) setSelectedDetail(detail);
        });
        return () => { cancelled = true; };
    }, [selectedId]);

    // ── Handlers ────────────────────────────────────────────────────

    const handleCreated = useCallback((createdId?: string) => {
        setCreateOpen(false);
        fetchData();
        if (createdId) setSelectedId(createdId);
    }, [fetchData]);

    const handleDelete = useCallback(async (id: string) => {
        if (!confirm(`Are you sure you want to delete concept "${id}"?`)) return;
        try {
            setIsDeleting(true);
            await ontologyApi.deleteConcept(id);
            setSelectedId(null);
            setSelectedDetail(null);
            await fetchData();
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Delete failed';
            alert(message);
        } finally {
            setIsDeleting(false);
        }
    }, [fetchData]);

    const handleUpdated = useCallback(async () => {
        await fetchData();
        if (selectedId) {
            const detail = await ontologyApi.getConcept(selectedId);
            setSelectedDetail(detail);
        }
    }, [fetchData, selectedId]);

    // ── Render ──────────────────────────────────────────────────────

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-muted-foreground animate-pulse">Loading ontology…</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-full">
                <Card className="p-6 text-center space-y-2">
                    <p className="text-destructive font-medium">{error}</p>
                    <Button variant="outline" size="sm" onClick={fetchData}>Retry</Button>
                </Card>
            </div>
        );
    }

    return (
        <TooltipProvider>
            <div className="absolute inset-0 flex flex-col overflow-hidden">
                {/* Top bar */}
                <div className="flex items-center justify-between border-b px-6 py-3">
                    <div className="flex items-center gap-3">
                        <Layers className="size-5 text-primary" />
                        <h1 className="text-lg font-semibold tracking-tight">Ontology</h1>
                        {stats && <StatsBar stats={stats} />}
                    </div>
                    <Button size="sm" onClick={() => setCreateOpen(true)}>
                        <Plus className="size-4 mr-1.5" />
                        New L3 Concept
                    </Button>
                </div>

                {/* Main content */}
                <div className="flex flex-1 overflow-hidden">
                    {/* Left — Tree */}
                    <div className="w-[340px] shrink-0 border-r flex flex-col overflow-hidden">
                        <div className="p-3 shrink-0">
                            <div className="relative">
                                <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                                <Input
                                    placeholder="Search concepts…"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-8 h-9 text-sm"
                                />
                            </div>
                        </div>
                        <ScrollArea className="flex-1 min-h-0">
                            <div className="px-2 pb-4">
                                {tree.map((node) => (
                                    <TreeNode
                                        key={node.id}
                                        node={node}
                                        selectedId={selectedId}
                                        onSelect={setSelectedId}
                                        searchQuery={searchQuery}
                                    />
                                ))}
                            </div>
                        </ScrollArea>
                    </div>

                    {/* Right — Detail + optional embedded type panel */}
                    <div className="flex-1 flex overflow-hidden min-w-0">
                        {selectedEmbeddedType ? (
                            <ResizablePanelGroup orientation="horizontal" className="h-full">
                                <ResizablePanel defaultSize={60} minSize={35}>
                                    <ScrollArea className="h-full">
                                        <div className="p-6 max-w-3xl">
                                            {selectedDetail ? (
                                                <DetailPanel
                                                    concept={selectedDetail}
                                                    onDelete={handleDelete}
                                                    onUpdated={handleUpdated}
                                                    isDeleting={isDeleting}
                                                    onEmbeddedTypeClick={setSelectedEmbeddedType}
                                                />
                                            ) : (
                                                <div className="flex flex-col items-center justify-center py-20 text-center">
                                                    <Network className="size-12 text-muted-foreground/30 mb-4" />
                                                    <p className="text-muted-foreground text-sm">
                                                        Select a concept from the tree to view its details
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    </ScrollArea>
                                </ResizablePanel>
                                <ResizableHandle withHandle />
                                <ResizablePanel defaultSize={40} minSize={25}>
                                    <EmbeddedTypeInlinePanel
                                        embeddedType={selectedEmbeddedType}
                                        onClose={() => setSelectedEmbeddedType(null)}
                                    />
                                </ResizablePanel>
                            </ResizablePanelGroup>
                        ) : (
                            <ScrollArea className="h-full w-full">
                                <div className="p-6 max-w-3xl">
                                    {selectedDetail ? (
                                        <DetailPanel
                                            concept={selectedDetail}
                                            onDelete={handleDelete}
                                            onUpdated={handleUpdated}
                                            isDeleting={isDeleting}
                                            onEmbeddedTypeClick={setSelectedEmbeddedType}
                                        />
                                    ) : (
                                        <div className="flex flex-col items-center justify-center py-20 text-center">
                                            <Network className="size-12 text-muted-foreground/30 mb-4" />
                                            <p className="text-muted-foreground text-sm">
                                                Select a concept from the tree to view its details
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </ScrollArea>
                        )}
                    </div>
                </div>

                {/* Create dialog */}
                <CreateConceptDialog
                    open={createOpen}
                    onOpenChange={setCreateOpen}
                    onCreated={handleCreated}
                />
            </div>
        </TooltipProvider>
    );
}
