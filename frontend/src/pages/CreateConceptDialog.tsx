import { useState, useCallback, useEffect, useMemo } from 'react';
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
import { Plus, X, Search, ChevronLeft, ChevronRight, Copy, Sparkles, AlertTriangle, Wand2, Loader2, ExternalLink } from 'lucide-react';
import type {
    ConceptDetail,
    ConceptSummary,
    CreateConceptPayload,
    CreateConceptPropertyPayload,
    CreateConceptRelationshipPayload,
    SuggestOntologyTypeResponse,
} from '@/types/ontology';


interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onCreated: () => void;
}

const STEPS = [
    { id: 'basics', title: 'AI Brief', description: 'Generate a starting draft' },
    { id: 'details', title: 'Details', description: 'Adapt fields and extraction signals' },
    { id: 'review', title: 'Review', description: 'Validate and create the new L3 type' },
] as const;

const EMPTY_PROPERTY: CreateConceptPropertyPayload = {
    name: '',
    type: 'string',
    required: false,
    description: '',
};

const EMPTY_RELATIONSHIP: CreateConceptRelationshipPayload = {
    name: '',
    target: '',
    cardinality: '0..*',
    description: '',
};

function toKebabCase(s: string): string {
    return s
        .replace(/([a-z])([A-Z])/g, '$1-$2')
        .replace(/[\s_]+/g, '-')
        .toLowerCase()
        .replace(/[^a-z0-9-]/g, '');
}

function dedupeStrings(values: string[]): string[] {
    const out: string[] = [];
    const seen = new Set<string>();
    for (const value of values) {
        const trimmed = value.trim();
        if (!trimmed) continue;
        const key = trimmed.toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(trimmed);
    }
    return out;
}

function mergeProperties(
    current: CreateConceptPropertyPayload[],
    incoming: CreateConceptPropertyPayload[],
): CreateConceptPropertyPayload[] {
    const byName = new Map<string, CreateConceptPropertyPayload>();
    for (const prop of current) {
        if (prop.name.trim()) byName.set(prop.name.trim().toLowerCase(), prop);
    }
    for (const prop of incoming) {
        const name = prop.name.trim();
        if (!name) continue;
        const key = name.toLowerCase();
        if (!byName.has(key)) {
            byName.set(key, {
                name,
                type: prop.type || 'string',
                required: Boolean(prop.required),
                description: prop.description ?? '',
                default_value: prop.default_value,
            });
        }
    }
    return Array.from(byName.values());
}

function mergeRelationships(
    current: CreateConceptRelationshipPayload[],
    incoming: CreateConceptRelationshipPayload[],
): CreateConceptRelationshipPayload[] {
    const keyFor = (rel: CreateConceptRelationshipPayload) =>
        `${rel.name.trim().toLowerCase()}::${rel.target.trim().toLowerCase()}`;
    const seen = new Set<string>();
    const out: CreateConceptRelationshipPayload[] = [];

    for (const rel of [...current, ...incoming]) {
        const name = rel.name.trim();
        const target = rel.target.trim();
        if (!name || !target) continue;
        const normalized: CreateConceptRelationshipPayload = {
            name,
            target,
            cardinality: rel.cardinality || '0..*',
            description: rel.description ?? '',
            inverse: rel.inverse,
        };
        const key = keyFor(normalized);
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(normalized);
    }
    return out;
}

export function CreateConceptDialog({ open, onOpenChange, onCreated }: Props) {
    const [step, setStep] = useState(0);

    // Form state
    const [label, setLabel] = useState('');
    const [id, setId] = useState('');
    const [idManuallyEdited, setIdManuallyEdited] = useState(false);
    const [inherits, setInherits] = useState('');
    const [description, setDescription] = useState('');
    const [synonymInput, setSynonymInput] = useState('');
    const [synonyms, setSynonyms] = useState<string[]>([]);
    const [properties, setProperties] = useState<CreateConceptPropertyPayload[]>([]);
    const [relationships, setRelationships] = useState<CreateConceptRelationshipPayload[]>([]);
    const [hintInput, setHintInput] = useState('');
    const [hints, setHints] = useState<string[]>([]);
    const [filePatternInput, setFilePatternInput] = useState('');
    const [filePatterns, setFilePatterns] = useState<string[]>([]);

    // Parent search
    const [parentSearch, setParentSearch] = useState('');
    const [parentResults, setParentResults] = useState<ConceptSummary[]>([]);
    const [showParentDropdown, setShowParentDropdown] = useState(false);
    const [parentDetail, setParentDetail] = useState<ConceptDetail | null>(null);
    const [loadingParentDetail, setLoadingParentDetail] = useState(false);

    // Blueprint source search
    const [sourceSearch, setSourceSearch] = useState('');
    const [sourceResults, setSourceResults] = useState<ConceptSummary[]>([]);
    const [showSourceDropdown, setShowSourceDropdown] = useState(false);
    const [sourceConceptId, setSourceConceptId] = useState('');
    const [sourceDetail, setSourceDetail] = useState<ConceptDetail | null>(null);
    const [loadingSourceDetail, setLoadingSourceDetail] = useState(false);
    const [lastImportMessage, setLastImportMessage] = useState('');

    // AI-first suggestion state
    const [aiConceptName, setAiConceptName] = useState('');
    const [aiDomainContext, setAiDomainContext] = useState('');
    const [aiStylePreferencesInput, setAiStylePreferencesInput] = useState('');
    const [aiReferencesInput, setAiReferencesInput] = useState('');
    const [aiReferenceUrls, setAiReferenceUrls] = useState<string[]>([]);
    const [aiLoading, setAiLoading] = useState(false);
    const [aiSuggestion, setAiSuggestion] = useState<SuggestOntologyTypeResponse | null>(null);
    const [showAiAdvanced, setShowAiAdvanced] = useState(false);
    const [showAiSuggestionDetails, setShowAiSuggestionDetails] = useState(false);

    // UI state
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Auto-generate ID from label
    useEffect(() => {
        if (!idManuallyEdited && label) {
            setId(toKebabCase(label));
        }
    }, [label, idManuallyEdited]);

    useEffect(() => {
        if (label.trim() && !aiConceptName.trim()) {
            setAiConceptName(label);
        }
    }, [label, aiConceptName]);

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

    // Fetch parent details
    useEffect(() => {
        if (!inherits.trim()) {
            setParentDetail(null);
            return;
        }
        let cancelled = false;
        setLoadingParentDetail(true);
        ontologyApi.getConcept(inherits.trim())
            .then((detail) => {
                if (!cancelled) setParentDetail(detail);
            })
            .catch(() => {
                if (!cancelled) setParentDetail(null);
            })
            .finally(() => {
                if (!cancelled) setLoadingParentDetail(false);
            });
        return () => { cancelled = true; };
    }, [inherits]);

    // Search concepts as blueprint sources
    useEffect(() => {
        if (sourceSearch.length < 2) {
            setSourceResults([]);
            return;
        }
        const timer = setTimeout(async () => {
            try {
                const results = await ontologyApi.search(sourceSearch);
                setSourceResults(results.filter((c) => c.id !== inherits).slice(0, 10));
            } catch {
                setSourceResults([]);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [sourceSearch, inherits]);

    // Fetch selected source concept details
    useEffect(() => {
        if (!sourceConceptId.trim()) {
            setSourceDetail(null);
            return;
        }
        let cancelled = false;
        setLoadingSourceDetail(true);
        ontologyApi.getConcept(sourceConceptId.trim())
            .then((detail) => {
                if (!cancelled) setSourceDetail(detail);
            })
            .catch(() => {
                if (!cancelled) setSourceDetail(null);
            })
            .finally(() => {
                if (!cancelled) setLoadingSourceDetail(false);
            });
        return () => { cancelled = true; };
    }, [sourceConceptId]);

    // Reset form when dialog opens
    useEffect(() => {
        if (open) {
            setStep(0);
            setLabel('');
            setId('');
            setIdManuallyEdited(false);
            setInherits('');
            setDescription('');
            setSynonymInput('');
            setSynonyms([]);
            setProperties([]);
            setRelationships([]);
            setHintInput('');
            setHints([]);
            setFilePatternInput('');
            setFilePatterns([]);
            setParentSearch('');
            setParentResults([]);
            setShowParentDropdown(false);
            setParentDetail(null);
            setLoadingParentDetail(false);
            setSourceSearch('');
            setSourceResults([]);
            setShowSourceDropdown(false);
            setSourceConceptId('');
            setSourceDetail(null);
            setLoadingSourceDetail(false);
            setLastImportMessage('');
            setAiConceptName('');
            setAiDomainContext('');
            setAiStylePreferencesInput('');
            setAiReferencesInput('');
            setAiReferenceUrls([]);
            setAiLoading(false);
            setAiSuggestion(null);
            setShowAiAdvanced(false);
            setShowAiSuggestionDetails(false);
            setError(null);
        }
    }, [open]);

    const parentInheritedPropertyNames = useMemo(() => {
        const names = new Set<string>();
        if (!parentDetail) return names;
        for (const prop of parentDetail.properties) {
            names.add(prop.name.toLowerCase());
        }
        for (const group of parentDetail.inherited_properties ?? []) {
            for (const prop of group.properties) {
                names.add(prop.name.toLowerCase());
            }
        }
        return names;
    }, [parentDetail]);

    const duplicateOwnProperties = useMemo(() => {
        return properties
            .map((p) => p.name.trim())
            .filter((name) => name && parentInheritedPropertyNames.has(name.toLowerCase()));
    }, [properties, parentInheritedPropertyNames]);

    const payload = useMemo<CreateConceptPayload>(() => {
        const cleanedProperties = properties
            .map((p) => ({
                ...p,
                name: p.name.trim(),
                type: (p.type || 'string').trim(),
                description: p.description.trim(),
            }))
            .filter((p) => p.name);
        const cleanedRelationships = relationships
            .map((r) => ({
                ...r,
                name: r.name.trim(),
                target: r.target.trim(),
                cardinality: (r.cardinality || '0..*').trim(),
                description: r.description.trim(),
                inverse: r.inverse?.trim() || undefined,
            }))
            .filter((r) => r.name && r.target);
        const cleanedHints = dedupeStrings(hints);
        const cleanedFilePatterns = dedupeStrings(filePatterns);

        return {
            id: id.trim(),
            label: label.trim(),
            inherits: inherits.trim(),
            description: description.trim(),
            abstract: false,
            synonyms: dedupeStrings(synonyms),
            mixins: [],
            properties: cleanedProperties,
            relationships: cleanedRelationships,
            extraction_template:
                cleanedHints.length > 0 || cleanedFilePatterns.length > 0
                    ? { classification_hints: cleanedHints, file_patterns: cleanedFilePatterns }
                    : undefined,
        };
    }, [id, label, inherits, description, synonyms, properties, relationships, hints, filePatterns]);

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

    const addFilePattern = useCallback(() => {
        const trimmed = filePatternInput.trim();
        if (trimmed && !filePatterns.includes(trimmed)) {
            setFilePatterns((prev) => [...prev, trimmed]);
            setFilePatternInput('');
        }
    }, [filePatternInput, filePatterns]);

    const removeFilePattern = useCallback((pattern: string) => {
        setFilePatterns((prev) => prev.filter((x) => x !== pattern));
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

    const addRelationship = useCallback(() => {
        setRelationships((prev) => [...prev, { ...EMPTY_RELATIONSHIP }]);
    }, []);

    const removeRelationship = useCallback((index: number) => {
        setRelationships((prev) => prev.filter((_, i) => i !== index));
    }, []);

    const updateRelationship = useCallback(
        (index: number, field: keyof CreateConceptRelationshipPayload, value: string) => {
            setRelationships((prev) =>
                prev.map((rel, i) => (i === index ? { ...rel, [field]: value } : rel)),
            );
        },
        [],
    );

    const selectParent = useCallback((concept: ConceptSummary) => {
        setInherits(concept.id);
        setParentSearch(concept.label);
        setShowParentDropdown(false);
    }, []);

    const selectSourceConcept = useCallback((concept: ConceptSummary) => {
        setSourceConceptId(concept.id);
        setSourceSearch(concept.label);
        setShowSourceDropdown(false);
    }, []);

    const importFromParentTemplate = useCallback(() => {
        if (!parentDetail?.extraction_template) {
            setLastImportMessage('Parent has no extraction template to import.');
            return;
        }

        const hintsToImport = parentDetail.extraction_template.classification_hints ?? [];
        const patternsToImport = parentDetail.extraction_template.file_patterns ?? [];

        setHints((prev) => dedupeStrings([...prev, ...hintsToImport]));
        setFilePatterns((prev) => dedupeStrings([...prev, ...patternsToImport]));
        setLastImportMessage(
            `Imported ${hintsToImport.length} hints and ${patternsToImport.length} file patterns from ${parentDetail.id}.`,
        );
    }, [parentDetail]);

    const importFromSource = useCallback(() => {
        if (!sourceDetail) {
            setLastImportMessage('Select an existing source concept first.');
            return;
        }

        setSynonyms((prev) => dedupeStrings([...prev, ...sourceDetail.synonyms]));
        const et = sourceDetail.extraction_template;
        if (et) {
            setHints((prev) =>
                dedupeStrings([
                    ...prev,
                    ...et.classification_hints,
                ]));
            setFilePatterns((prev) =>
                dedupeStrings([
                    ...prev,
                    ...et.file_patterns,
                ]));
        }
        const incomingProps = sourceDetail.properties.map((p) => ({
            name: p.name,
            type: p.type,
            required: p.required,
            description: p.description,
            default_value: p.default_value ?? undefined,
        }));
        setProperties((prev) => mergeProperties(prev, incomingProps));

        const incomingRels = sourceDetail.relationships.map((r) => ({
            name: r.name,
            target: r.target,
            cardinality: r.cardinality,
            description: r.description,
            inverse: r.inverse ?? undefined,
        }));
        setRelationships((prev) => mergeRelationships(prev, incomingRels));

        setLastImportMessage(`Imported defaults from ${sourceDetail.id}.`);
    }, [sourceDetail]);

    const addAiReference = useCallback(() => {
        const trimmed = aiReferencesInput.trim();
        if (!trimmed) return;
        if (!aiReferenceUrls.includes(trimmed)) {
            setAiReferenceUrls((prev) => [...prev, trimmed]);
        }
        setAiReferencesInput('');
    }, [aiReferencesInput, aiReferenceUrls]);

    const removeAiReference = useCallback((url: string) => {
        setAiReferenceUrls((prev) => prev.filter((u) => u !== url));
    }, []);

    const applySuggestion = useCallback((suggestion: SuggestOntologyTypeResponse) => {
        const draft = suggestion.payload;
        setLabel(draft.label || label);
        setId(draft.id || toKebabCase(draft.label || label || aiConceptName || 'new-concept'));
        setIdManuallyEdited(true);
        if (draft.inherits) {
            setInherits(draft.inherits);
            setParentSearch(draft.inherits);
        }
        if (draft.description) setDescription(draft.description);
        setSynonyms((prev) => dedupeStrings([...prev, ...(draft.synonyms ?? [])]));
        setProperties((prev) => mergeProperties(prev, draft.properties ?? []));
        setRelationships((prev) => mergeRelationships(prev, draft.relationships ?? []));
        if (draft.extraction_template) {
            setHints((prev) =>
                dedupeStrings([
                    ...prev,
                    ...(draft.extraction_template?.classification_hints ?? []),
                ]));
            setFilePatterns((prev) =>
                dedupeStrings([
                    ...prev,
                    ...(draft.extraction_template?.file_patterns ?? []),
                ]));
        }
        setLastImportMessage('Applied AI draft. You can now refine it in Details.');
        setStep(1);
    }, [label, aiConceptName]);

    const generateAiSuggestion = useCallback(async () => {
        const idea = aiConceptName.trim() || label.trim();
        if (!idea) {
            setError('Provide a concept name or idea before generating an AI draft.');
            return;
        }

        try {
            setError(null);
            setAiLoading(true);
            const stylePreferences = dedupeStrings(
                aiStylePreferencesInput
                    .split(',')
                    .map((s) => s.trim())
                    .filter(Boolean),
            );

            const suggestion = await ontologyApi.suggestType({
                name: idea,
                description: description.trim(),
                inherits: inherits.trim() || undefined,
                domain_context: aiDomainContext.trim(),
                style_preferences: stylePreferences,
                reference_urls: aiReferenceUrls,
                include_internet_research: true,
            });

            setAiSuggestion(suggestion);
            setLastImportMessage('AI suggestion generated. Review and apply it when ready.');
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Failed to generate AI suggestion';
            setError(message);
        } finally {
            setAiLoading(false);
        }
    }, [
        aiConceptName,
        label,
        description,
        inherits,
        aiDomainContext,
        aiStylePreferencesInput,
        aiReferenceUrls,
    ]);

    const validateStepZero = useCallback(() => {
        if (!label.trim()) {
            setError('Label is required');
            return false;
        }
        if (!id.trim()) {
            setError('ID is required');
            return false;
        }
        if (!inherits.trim()) {
            setError('Parent concept is required');
            return false;
        }
        setError(null);
        return true;
    }, [label, id, inherits]);

    const goNext = useCallback(() => {
        if (step === 0 && !validateStepZero()) return;
        setError(null);
        setStep((prev) => Math.min(prev + 1, STEPS.length - 1));
    }, [step, validateStepZero]);

    const goBack = useCallback(() => {
        setError(null);
        setStep((prev) => Math.max(prev - 1, 0));
    }, []);

    const handleSubmit = useCallback(async () => {
        setError(null);

        if (!validateStepZero()) {
            return;
        }

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
    }, [validateStepZero, payload, onCreated]);

    const renderBasicsStep = () => (
        <div className="space-y-5">
            <div className="rounded-lg border p-3 space-y-3">
                <div className="flex items-center justify-between gap-2">
                    <div>
                        <p className="text-sm font-medium">AI Type Designer</p>
                        <p className="text-xs text-muted-foreground">
                            Generate a draft from ontology context + internet best-practice references.
                        </p>
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={generateAiSuggestion}
                        disabled={aiLoading}
                    >
                        {aiLoading ? (
                            <>
                                <Loader2 className="size-3.5 mr-1 animate-spin" />
                                Generating…
                            </>
                        ) : (
                            <>
                                <Wand2 className="size-3.5 mr-1" />
                                Generate AI Draft
                            </>
                        )}
                    </Button>
                </div>

                <div className="grid grid-cols-1 gap-2">
                    <div className="space-y-1">
                        <Label>Concept Idea</Label>
                        <Input
                            value={aiConceptName}
                            onChange={(e) => setAiConceptName(e.target.value)}
                            placeholder="e.g. Blog Post, Technical Note, Incident Digest"
                        />
                    </div>
                    <div className="space-y-1">
                        <Label>Domain Context</Label>
                        <Textarea
                            value={aiDomainContext}
                            onChange={(e) => setAiDomainContext(e.target.value)}
                            placeholder="Optional context (industry, audience, internal standards, constraints)"
                            rows={2}
                        />
                    </div>

                    <div className="flex justify-start">
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowAiAdvanced((prev) => !prev)}
                        >
                            {showAiAdvanced ? 'Hide' : 'Show'} Advanced AI Options
                        </Button>
                    </div>

                    {showAiAdvanced && (
                        <div className="space-y-2 rounded-md border bg-muted/20 p-2.5">
                            <div className="space-y-1">
                                <Label>Style Preferences (comma separated)</Label>
                                <Input
                                    value={aiStylePreferencesInput}
                                    onChange={(e) => setAiStylePreferencesInput(e.target.value)}
                                    placeholder="e.g. schema.org compatible, minimal properties"
                                />
                            </div>
                            <div className="space-y-1">
                                <Label>Additional Reference URLs</Label>
                                <div className="flex gap-2">
                                    <Input
                                        value={aiReferencesInput}
                                        onChange={(e) => setAiReferencesInput(e.target.value)}
                                        placeholder="https://..."
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter') {
                                                e.preventDefault();
                                                addAiReference();
                                            }
                                        }}
                                    />
                                    <Button type="button" variant="outline" size="sm" onClick={addAiReference}>
                                        <Plus className="size-3.5" />
                                    </Button>
                                </div>
                                {aiReferenceUrls.length > 0 && (
                                    <div className="flex flex-wrap gap-1">
                                        {aiReferenceUrls.map((url) => (
                                            <Badge key={url} variant="outline" className="gap-1">
                                                {url}
                                                <button onClick={() => removeAiReference(url)}>
                                                    <X className="size-3" />
                                                </button>
                                            </Badge>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {aiSuggestion && (
                    <div className="rounded-md border bg-muted/20 p-3 space-y-2">
                        <div className="flex items-center justify-between gap-2">
                            <p className="text-xs font-medium">AI Suggestion</p>
                            <div className="flex items-center gap-1.5">
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setShowAiSuggestionDetails((prev) => !prev)}
                                >
                                    {showAiSuggestionDetails ? 'Hide' : 'Show'} Details
                                </Button>
                                <Button
                                    type="button"
                                    size="sm"
                                    onClick={() => applySuggestion(aiSuggestion)}
                                >
                                    <Sparkles className="size-3.5 mr-1" />
                                    Apply
                                </Button>
                            </div>
                        </div>
                        {aiSuggestion.rationale && (
                            <p className="text-xs text-muted-foreground break-words">
                                {aiSuggestion.rationale.length > 320
                                    ? `${aiSuggestion.rationale.slice(0, 320)}...`
                                    : aiSuggestion.rationale}
                            </p>
                        )}
                        <div className="flex flex-wrap gap-1">
                            <Badge variant="secondary" className="text-xs">
                                Parent: {aiSuggestion.payload.inherits}
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                                {aiSuggestion.payload.properties.length} properties
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                                {aiSuggestion.payload.relationships.length} relationships
                            </Badge>
                        </div>
                        {showAiSuggestionDetails && (
                            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                                {aiSuggestion.parent_reasoning && (
                                    <p className="text-xs text-muted-foreground break-words">
                                        Parent reasoning: {aiSuggestion.parent_reasoning}
                                    </p>
                                )}
                                {aiSuggestion.adaptation_tips.length > 0 && (
                                    <div className="space-y-1">
                                        <p className="text-[11px] font-medium">Adaptation Tips</p>
                                        <div className="flex flex-wrap gap-1">
                                            {aiSuggestion.adaptation_tips.map((tip) => (
                                                <Badge key={tip} variant="outline" className="text-[11px]">{tip}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                                {aiSuggestion.warnings.length > 0 && (
                                    <div className="rounded-md border border-amber-300/60 bg-amber-50/60 p-2 text-xs text-amber-900 break-words">
                                        {aiSuggestion.warnings.join(' ')}
                                    </div>
                                )}
                                {aiSuggestion.references.length > 0 && (
                                    <div className="space-y-1">
                                        <p className="text-[11px] font-medium">References Used</p>
                                        <div className="space-y-1">
                                            {aiSuggestion.references.slice(0, 6).map((ref) => (
                                                <a
                                                    key={ref.url}
                                                    href={ref.url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="block rounded border p-1.5 hover:bg-accent/40"
                                                >
                                                    <div className="flex items-center gap-1 text-[11px] font-medium">
                                                        <ExternalLink className="size-3" />
                                                        <span className="truncate">{ref.title || ref.url}</span>
                                                    </div>
                                                </a>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                    <Label htmlFor="label">Label *</Label>
                    <Input
                        id="label"
                        value={label}
                        onChange={(e) => setLabel(e.target.value)}
                        placeholder="e.g. Blog Post"
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
                        placeholder="Search a base concept (e.g. Document, Report, Contract)..."
                        className="pl-8"
                    />
                </div>
                {inherits && (
                    <p className="text-xs text-muted-foreground">
                        Selected parent: <code className="bg-muted px-1 rounded">{inherits}</code>
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

            <div className="space-y-1.5">
                <Label htmlFor="description">Description</Label>
                <Textarea
                    id="description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe what this concept represents and how it differs from existing ones."
                    rows={4}
                />
            </div>

            <div className="rounded-lg border bg-muted/20 p-3 space-y-1.5">
                <p className="text-xs font-medium">Parent context</p>
                {loadingParentDetail && (
                    <p className="text-xs text-muted-foreground">Loading parent details…</p>
                )}
                {!loadingParentDetail && !parentDetail && (
                    <p className="text-xs text-muted-foreground">
                        Pick a parent to inspect inherited fields and templates.
                    </p>
                )}
                {!loadingParentDetail && parentDetail && (
                    <>
                        <p className="text-xs text-muted-foreground">
                            `{parentDetail.label}` contributes inherited fields and extraction behavior.
                        </p>
                        <div className="flex flex-wrap gap-1">
                            <Badge variant="secondary" className="text-xs">
                                {parentDetail.properties.length} own properties
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                                {(parentDetail.inherited_properties ?? []).length} ancestor groups
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                                {(parentDetail.extraction_template?.classification_hints ?? []).length} hints
                            </Badge>
                        </div>
                    </>
                )}
            </div>
        </div>
    );

    const renderDetailsStep = () => (
        <div className="space-y-5">
            <div className="rounded-lg border p-3 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                        <p className="text-sm font-medium">Reuse Existing Sources (Optional)</p>
                        <p className="text-xs text-muted-foreground">
                            Import defaults from parent template or from one existing concept.
                        </p>
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={importFromParentTemplate}
                        disabled={!parentDetail?.extraction_template}
                    >
                        <Sparkles className="size-3.5 mr-1" />
                        Import Parent Template
                    </Button>
                </div>

                <div className="space-y-1.5 relative">
                    <Label>Import From Concept</Label>
                    <div className="flex gap-2">
                        <div className="relative flex-1">
                            <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                            <Input
                                value={sourceSearch}
                                onChange={(e) => {
                                    setSourceSearch(e.target.value);
                                    setShowSourceDropdown(true);
                                    if (!e.target.value) setSourceConceptId('');
                                }}
                                onFocus={() => setShowSourceDropdown(true)}
                                placeholder="Find an existing concept to copy defaults from..."
                                className="pl-8"
                            />
                        </div>
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={importFromSource}
                            disabled={!sourceDetail || loadingSourceDetail}
                        >
                            <Copy className="size-3.5 mr-1" />
                            Import
                        </Button>
                    </div>
                    {showSourceDropdown && sourceResults.length > 0 && (
                        <div className="absolute z-50 w-full mt-1 border rounded-lg bg-popover shadow-lg max-h-48 overflow-y-auto">
                            {sourceResults.map((c) => (
                                <button
                                    key={c.id}
                                    onClick={() => selectSourceConcept(c)}
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
                    {loadingSourceDetail && (
                        <p className="text-xs text-muted-foreground">Loading source concept details…</p>
                    )}
                    {!loadingSourceDetail && sourceDetail && (
                        <p className="text-xs text-muted-foreground">
                            Ready to import from `{sourceDetail.id}`.
                        </p>
                    )}
                </div>

                {lastImportMessage && (
                    <div className="rounded-lg border border-emerald-300/60 bg-emerald-50/60 p-2 text-xs text-emerald-800 break-words">
                        {lastImportMessage}
                    </div>
                )}
            </div>

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

            <div className="space-y-1.5">
                <Label>Classification Hints</Label>
                <div className="flex gap-2">
                    <Input
                        value={hintInput}
                        onChange={(e) => setHintInput(e.target.value)}
                        placeholder="e.g. blog post, article, published on"
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

            <div className="space-y-1.5">
                <Label>File Patterns</Label>
                <div className="flex gap-2">
                    <Input
                        value={filePatternInput}
                        onChange={(e) => setFilePatternInput(e.target.value)}
                        placeholder="e.g. **/blog/** or /articles/"
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                                e.preventDefault();
                                addFilePattern();
                            }
                        }}
                    />
                    <Button type="button" variant="outline" size="sm" onClick={addFilePattern}>
                        <Plus className="size-3.5" />
                    </Button>
                </div>
                {filePatterns.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                        {filePatterns.map((pattern) => (
                            <Badge key={pattern} variant="outline" className="gap-1 font-mono">
                                {pattern}
                                <button onClick={() => removeFilePattern(pattern)}>
                                    <X className="size-3" />
                                </button>
                            </Badge>
                        ))}
                    </div>
                )}
            </div>

            <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                    <Label>Own Properties</Label>
                    <Button type="button" variant="ghost" size="sm" onClick={addProperty}>
                        <Plus className="size-3 mr-1" /> Add
                    </Button>
                </div>
                {properties.map((prop, i) => (
                    <div key={`${prop.name}-${i}`} className="grid grid-cols-[1.4fr_1fr_auto_auto] gap-2 rounded-lg border p-2">
                        <Input
                            value={prop.name}
                            onChange={(e) => updateProperty(i, 'name', e.target.value)}
                            placeholder="Name"
                            className="h-8 text-sm"
                        />
                        <Input
                            value={prop.type}
                            onChange={(e) => updateProperty(i, 'type', e.target.value)}
                            placeholder="Type (string, date, ref:Person, ...)"
                            className="h-8 text-sm font-mono"
                        />
                        <label className="flex items-center gap-1 text-xs whitespace-nowrap px-1">
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
                        <div className="col-span-4">
                            <Input
                                value={prop.description}
                                onChange={(e) => updateProperty(i, 'description', e.target.value)}
                                placeholder="Description"
                                className="h-8 text-xs"
                            />
                        </div>
                    </div>
                ))}
                {duplicateOwnProperties.length > 0 && (
                    <div className="rounded-md border border-amber-300/70 bg-amber-50/70 p-2 text-xs text-amber-900 flex items-start gap-2">
                        <AlertTriangle className="size-3.5 mt-0.5 shrink-0" />
                        <span>
                            You redefine inherited property name(s): {duplicateOwnProperties.join(', ')}.
                            This overrides parent definitions.
                        </span>
                    </div>
                )}
            </div>

            <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                    <Label>Relationships</Label>
                    <Button type="button" variant="ghost" size="sm" onClick={addRelationship}>
                        <Plus className="size-3 mr-1" /> Add
                    </Button>
                </div>
                {relationships.map((rel, i) => (
                    <div key={`${rel.name}-${rel.target}-${i}`} className="grid grid-cols-[1fr_1fr_110px_auto] gap-2 rounded-lg border p-2">
                        <Input
                            value={rel.name}
                            onChange={(e) => updateRelationship(i, 'name', e.target.value)}
                            placeholder="Name"
                            className="h-8 text-sm"
                        />
                        <Input
                            value={rel.target}
                            onChange={(e) => updateRelationship(i, 'target', e.target.value)}
                            placeholder="Target concept ID"
                            className="h-8 text-sm font-mono"
                        />
                        <Input
                            value={rel.cardinality}
                            onChange={(e) => updateRelationship(i, 'cardinality', e.target.value)}
                            placeholder="0..*"
                            className="h-8 text-sm font-mono"
                        />
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => removeRelationship(i)}
                            className="px-1.5"
                        >
                            <X className="size-3.5" />
                        </Button>
                        <div className="col-span-4">
                            <Input
                                value={rel.description}
                                onChange={(e) => updateRelationship(i, 'description', e.target.value)}
                                placeholder="Description"
                                className="h-8 text-xs"
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );

    const renderReviewStep = () => (
        <div className="space-y-4">
            <div className="rounded-lg border bg-muted/20 p-3">
                <p className="text-sm font-medium mb-2">Concept summary</p>
                <div className="grid grid-cols-2 gap-y-1 text-xs">
                    <span className="text-muted-foreground">ID</span>
                    <code>{payload.id || '-'}</code>
                    <span className="text-muted-foreground">Label</span>
                    <span>{payload.label || '-'}</span>
                    <span className="text-muted-foreground">Parent</span>
                    <code>{payload.inherits || '-'}</code>
                    <span className="text-muted-foreground">Synonyms</span>
                    <span>{payload.synonyms.length}</span>
                    <span className="text-muted-foreground">Properties</span>
                    <span>{payload.properties.length}</span>
                    <span className="text-muted-foreground">Relationships</span>
                    <span>{payload.relationships.length}</span>
                    <span className="text-muted-foreground">Classification hints</span>
                    <span>{payload.extraction_template?.classification_hints.length ?? 0}</span>
                    <span className="text-muted-foreground">File patterns</span>
                    <span>{payload.extraction_template?.file_patterns.length ?? 0}</span>
                </div>
            </div>

            <div className="space-y-1.5">
                <Label>Request Preview</Label>
                <pre className="rounded-lg border bg-muted/20 p-3 text-xs overflow-x-auto">
{JSON.stringify(payload, null, 2)}
                </pre>
            </div>
        </div>
    );

    // ── Render ──────────────────────────────────────────────────────

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="w-[min(96vw,980px)] h-[min(92vh,860px)] !flex !flex-col overflow-hidden">
                <DialogHeader>
                    <DialogTitle>Create L3 Concept Wizard</DialogTitle>
                    <DialogDescription>
                        Reuse existing ontology concepts, templates, and fields before creating a new type.
                    </DialogDescription>
                </DialogHeader>

                <div className="grid shrink-0 grid-cols-3 gap-2">
                    {STEPS.map((s, index) => (
                        <button
                            key={s.id}
                            onClick={() => {
                                if (index <= step) setStep(index);
                            }}
                            className={`rounded-md border px-2 py-1.5 text-left transition-colors ${
                                index === step
                                    ? 'border-primary bg-primary/5'
                                    : index < step
                                        ? 'border-emerald-300 bg-emerald-50/50'
                                        : 'border-border'
                            }`}
                            type="button"
                        >
                            <p className="text-[10px] text-muted-foreground">Step {index + 1}</p>
                            <p className="text-xs font-medium">{s.title}</p>
                        </button>
                    ))}
                </div>

                <ScrollArea className="min-h-0 flex-1 -mx-6 px-6">
                    <div className="space-y-5 py-2">
                        <div className="space-y-1">
                            <p className="text-sm font-medium">{STEPS[step].title}</p>
                            <p className="text-xs text-muted-foreground">{STEPS[step].description}</p>
                        </div>

                        {step === 0 && renderBasicsStep()}
                        {step === 1 && renderDetailsStep()}
                        {step === 2 && renderReviewStep()}

                        {error && (
                            <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
                                {error}
                            </div>
                        )}
                    </div>
                </ScrollArea>

                <DialogFooter>
                    <div className="flex w-full items-center justify-between gap-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
                            Cancel
                        </Button>
                        <div className="flex items-center gap-2">
                            {step > 0 && (
                                <Button type="button" variant="outline" onClick={goBack} disabled={submitting}>
                                    <ChevronLeft className="size-4 mr-1" />
                                    Back
                                </Button>
                            )}
                            {step < STEPS.length - 1 ? (
                                <Button type="button" onClick={goNext} disabled={submitting}>
                                    Next
                                    <ChevronRight className="size-4 ml-1" />
                                </Button>
                            ) : (
                                <Button onClick={handleSubmit} disabled={submitting}>
                                    {submitting ? 'Creating…' : 'Create Concept'}
                                </Button>
                            )}
                        </div>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
