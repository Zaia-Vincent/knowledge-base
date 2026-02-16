import { useState, useCallback, useEffect } from 'react';
import { ontologyApi } from '@/lib/ontology-api';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Plus, X, Search } from 'lucide-react';
import type { ConceptSummary, CreateConceptPayload, CreateConceptPropertyPayload } from '@/types/ontology';


interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onCreated: () => void;
}

const EMPTY_PROPERTY: CreateConceptPropertyPayload = {
    name: '',
    type: 'string',
    required: false,
    description: '',
};

function toKebabCase(s: string): string {
    return s
        .replace(/([a-z])([A-Z])/g, '$1-$2')
        .replace(/[\s_]+/g, '-')
        .toLowerCase()
        .replace(/[^a-z0-9-]/g, '');
}

export function CreateConceptDialog({ open, onOpenChange, onCreated }: Props) {
    // Form state
    const [label, setLabel] = useState('');
    const [id, setId] = useState('');
    const [idManuallyEdited, setIdManuallyEdited] = useState(false);
    const [inherits, setInherits] = useState('');
    const [description, setDescription] = useState('');
    const [synonymInput, setSynonymInput] = useState('');
    const [synonyms, setSynonyms] = useState<string[]>([]);
    const [properties, setProperties] = useState<CreateConceptPropertyPayload[]>([]);
    const [hintInput, setHintInput] = useState('');
    const [hints, setHints] = useState<string[]>([]);

    // Parent search
    const [parentSearch, setParentSearch] = useState('');
    const [parentResults, setParentResults] = useState<ConceptSummary[]>([]);
    const [showParentDropdown, setShowParentDropdown] = useState(false);

    // UI state
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Auto-generate ID from label
    useEffect(() => {
        if (!idManuallyEdited && label) {
            setId(toKebabCase(label));
        }
    }, [label, idManuallyEdited]);

    // Search parents
    useEffect(() => {
        if (parentSearch.length < 2) {
            setParentResults([]);
            return;
        }
        const timer = setTimeout(async () => {
            try {
                const results = await ontologyApi.search(parentSearch);
                setParentResults(results.slice(0, 10));
            } catch {
                setParentResults([]);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [parentSearch]);

    // Reset form when dialog opens
    useEffect(() => {
        if (open) {
            setLabel('');
            setId('');
            setIdManuallyEdited(false);
            setInherits('');
            setDescription('');
            setSynonymInput('');
            setSynonyms([]);
            setProperties([]);
            setHintInput('');
            setHints([]);
            setParentSearch('');
            setParentResults([]);
            setError(null);
        }
    }, [open]);

    // ── Handlers ────────────────────────────────────────────────────

    const addSynonym = useCallback(() => {
        const trimmed = synonymInput.trim();
        if (trimmed && !synonyms.includes(trimmed)) {
            setSynonyms((prev) => [...prev, trimmed]);
            setSynonymInput('');
        }
    }, [synonymInput, synonyms]);

    const removeSynonym = useCallback((s: string) => {
        setSynonyms((prev) => prev.filter((x) => x !== s));
    }, []);

    const addHint = useCallback(() => {
        const trimmed = hintInput.trim();
        if (trimmed && !hints.includes(trimmed)) {
            setHints((prev) => [...prev, trimmed]);
            setHintInput('');
        }
    }, [hintInput, hints]);

    const removeHint = useCallback((h: string) => {
        setHints((prev) => prev.filter((x) => x !== h));
    }, []);

    const addProperty = useCallback(() => {
        setProperties((prev) => [...prev, { ...EMPTY_PROPERTY }]);
    }, []);

    const removeProperty = useCallback((index: number) => {
        setProperties((prev) => prev.filter((_, i) => i !== index));
    }, []);

    const updateProperty = useCallback(
        (index: number, field: keyof CreateConceptPropertyPayload, value: string | boolean) => {
            setProperties((prev) =>
                prev.map((p, i) => (i === index ? { ...p, [field]: value } : p)),
            );
        },
        [],
    );

    const selectParent = useCallback((concept: ConceptSummary) => {
        setInherits(concept.id);
        setParentSearch(concept.label);
        setShowParentDropdown(false);
    }, []);

    const handleSubmit = useCallback(async () => {
        setError(null);

        if (!label.trim()) {
            setError('Label is required');
            return;
        }
        if (!id.trim()) {
            setError('ID is required');
            return;
        }
        if (!inherits.trim()) {
            setError('Parent concept is required');
            return;
        }

        const payload: CreateConceptPayload = {
            id: id.trim(),
            label: label.trim(),
            inherits: inherits.trim(),
            description: description.trim(),
            abstract: false,
            synonyms,
            mixins: [],
            properties: properties.filter((p) => p.name.trim()),
            relationships: [],
            extraction_template:
                hints.length > 0 ? { classification_hints: hints, file_patterns: [] } : undefined,
        };

        try {
            setSubmitting(true);
            await ontologyApi.createConcept(payload);
            onCreated();
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Failed to create concept';
            setError(message);
        } finally {
            setSubmitting(false);
        }
    }, [label, id, inherits, description, synonyms, properties, hints, onCreated]);

    // ── Render ──────────────────────────────────────────────────────

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle>Create L3 Concept</DialogTitle>
                    <DialogDescription>
                        Define a new industry-specific concept that extends the existing ontology.
                    </DialogDescription>
                </DialogHeader>

                <ScrollArea className="flex-1 -mx-6 px-6">
                    <div className="space-y-5 py-2">
                        {/* Label + ID */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="label">Label *</Label>
                                <Input
                                    id="label"
                                    value={label}
                                    onChange={(e) => setLabel(e.target.value)}
                                    placeholder="e.g. Purchase Order"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="concept-id">ID *</Label>
                                <Input
                                    id="concept-id"
                                    value={id}
                                    onChange={(e) => {
                                        setId(e.target.value);
                                        setIdManuallyEdited(true);
                                    }}
                                    placeholder="auto-generated"
                                    className="font-mono text-sm"
                                />
                            </div>
                        </div>

                        {/* Parent concept */}
                        <div className="space-y-1.5 relative">
                            <Label>Parent Concept *</Label>
                            <div className="relative">
                                <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                                <Input
                                    value={parentSearch}
                                    onChange={(e) => {
                                        setParentSearch(e.target.value);
                                        setShowParentDropdown(true);
                                        if (!e.target.value) setInherits('');
                                    }}
                                    onFocus={() => setShowParentDropdown(true)}
                                    placeholder="Search for a parent concept…"
                                    className="pl-8"
                                />
                            </div>
                            {inherits && (
                                <p className="text-xs text-muted-foreground">
                                    Inherits from: <code className="bg-muted px-1 rounded">{inherits}</code>
                                </p>
                            )}
                            {showParentDropdown && parentResults.length > 0 && (
                                <div className="absolute z-50 w-full mt-1 border rounded-lg bg-popover shadow-lg max-h-48 overflow-y-auto">
                                    {parentResults.map((c) => (
                                        <button
                                            key={c.id}
                                            onClick={() => selectParent(c)}
                                            className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-accent text-left"
                                        >
                                            <span className="font-mono text-xs text-muted-foreground">
                                                {c.layer}
                                            </span>
                                            <span>{c.label}</span>
                                            <span className="ml-auto text-xs text-muted-foreground font-mono">
                                                {c.id}
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Description */}
                        <div className="space-y-1.5">
                            <Label htmlFor="description">Description</Label>
                            <Textarea
                                id="description"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Describe what this concept represents…"
                                rows={3}
                            />
                        </div>

                        {/* Synonyms */}
                        <div className="space-y-1.5">
                            <Label>Synonyms</Label>
                            <div className="flex gap-2">
                                <Input
                                    value={synonymInput}
                                    onChange={(e) => setSynonymInput(e.target.value)}
                                    placeholder="Add synonym…"
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            e.preventDefault();
                                            addSynonym();
                                        }
                                    }}
                                />
                                <Button type="button" variant="outline" size="sm" onClick={addSynonym}>
                                    <Plus className="size-3.5" />
                                </Button>
                            </div>
                            {synonyms.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                    {synonyms.map((s) => (
                                        <Badge key={s} variant="secondary" className="gap-1">
                                            {s}
                                            <button onClick={() => removeSynonym(s)}>
                                                <X className="size-3" />
                                            </button>
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Properties */}
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between">
                                <Label>Properties</Label>
                                <Button type="button" variant="ghost" size="sm" onClick={addProperty}>
                                    <Plus className="size-3 mr-1" /> Add
                                </Button>
                            </div>
                            {properties.map((prop, i) => (
                                <div key={i} className="flex items-center gap-2 rounded-lg border p-2">
                                    <Input
                                        value={prop.name}
                                        onChange={(e) => updateProperty(i, 'name', e.target.value)}
                                        placeholder="Name"
                                        className="flex-1 h-8 text-sm"
                                    />
                                    <select
                                        value={prop.type}
                                        onChange={(e) => updateProperty(i, 'type', e.target.value)}
                                        className="h-8 rounded-md border bg-background px-2 text-sm"
                                    >
                                        {['string', 'integer', 'decimal', 'boolean', 'date', 'datetime', 'enum', 'text'].map(
                                            (t) => (
                                                <option key={t} value={t}>{t}</option>
                                            ),
                                        )}
                                    </select>
                                    <label className="flex items-center gap-1 text-xs whitespace-nowrap">
                                        <input
                                            type="checkbox"
                                            checked={prop.required}
                                            onChange={(e) => updateProperty(i, 'required', e.target.checked)}
                                            className="size-3.5"
                                        />
                                        Req
                                    </label>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => removeProperty(i)}
                                        className="px-1.5"
                                    >
                                        <X className="size-3.5" />
                                    </Button>
                                </div>
                            ))}
                        </div>

                        {/* Classification Hints */}
                        <div className="space-y-1.5">
                            <Label>Classification Hints</Label>
                            <div className="flex gap-2">
                                <Input
                                    value={hintInput}
                                    onChange={(e) => setHintInput(e.target.value)}
                                    placeholder="e.g. purchase order, PO, bestelling"
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            e.preventDefault();
                                            addHint();
                                        }
                                    }}
                                />
                                <Button type="button" variant="outline" size="sm" onClick={addHint}>
                                    <Plus className="size-3.5" />
                                </Button>
                            </div>
                            {hints.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                    {hints.map((h) => (
                                        <Badge key={h} variant="secondary" className="gap-1">
                                            {h}
                                            <button onClick={() => removeHint(h)}>
                                                <X className="size-3" />
                                            </button>
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Error */}
                        {error && (
                            <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
                                {error}
                            </div>
                        )}
                    </div>
                </ScrollArea>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
                        Cancel
                    </Button>
                    <Button onClick={handleSubmit} disabled={submitting}>
                        {submitting ? 'Creating…' : 'Create Concept'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
