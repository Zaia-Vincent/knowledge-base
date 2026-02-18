import { useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Search, Wand2, Loader2, Sparkles, ExternalLink } from 'lucide-react';
import { useClickOutside } from '@/hooks/useClickOutside';
import { TagListInput } from '../components/TagListInput';
import type { WizardState, WizardAction } from '../hooks/useWizardFormState';
import type { SuggestOntologyTypeResponse } from '@/types/ontology';

interface AiBriefStepProps {
    state: WizardState;
    dispatch: React.Dispatch<WizardAction>;
    generateAiSuggestion: () => Promise<void>;
    applySuggestion: (suggestion: SuggestOntologyTypeResponse) => void;
}

/**
 * Step 1 — AI brief panel + basic concept fields (label, id, parent, description).
 */
export function AiBriefStep({ state, dispatch, generateAiSuggestion, applySuggestion }: AiBriefStepProps) {
    const {
        aiConceptName, aiDomainContext, aiLoading,
        aiStylePreferencesInput, aiReferenceUrls,
        showAiAdvanced, aiSuggestion, showAiSuggestionDetails,
        label, id, inherits,
        parentSearch, parentSearchLoading, parentResults, showParentDropdown,
        description, parentDetail, loadingParentDetail,
    } = state;

    const field = (f: keyof WizardState, value: unknown) =>
        dispatch({ type: 'SET_FIELD', field: f, value });

    // Click-outside for parent dropdown
    const parentDropdownRef = useRef<HTMLDivElement>(null);
    useClickOutside(parentDropdownRef, useCallback(() => {
        field('showParentDropdown', false);
    }, [dispatch])); // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <div className="space-y-5">
            {/* AI Generator Panel */}
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
                            <><Loader2 className="size-3.5 mr-1 animate-spin" />Generating…</>
                        ) : (
                            <><Wand2 className="size-3.5 mr-1" />Generate AI Draft</>
                        )}
                    </Button>
                </div>

                <div className="grid grid-cols-1 gap-2">
                    <div className="space-y-1">
                        <Label>Concept Idea</Label>
                        <Input
                            value={aiConceptName}
                            onChange={(e) => field('aiConceptName', e.target.value)}
                            placeholder="e.g. Blog Post, Technical Note, Incident Digest"
                        />
                    </div>
                    <div className="space-y-1">
                        <Label>Domain Context</Label>
                        <Textarea
                            value={aiDomainContext}
                            onChange={(e) => field('aiDomainContext', e.target.value)}
                            placeholder="Optional context (industry, audience, internal standards, constraints)"
                            rows={2}
                        />
                    </div>

                    <div className="flex justify-start">
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => field('showAiAdvanced', !showAiAdvanced)}
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
                                    onChange={(e) => field('aiStylePreferencesInput', e.target.value)}
                                    placeholder="e.g. schema.org compatible, minimal properties"
                                />
                            </div>
                            <TagListInput
                                label="Additional Reference URLs"
                                placeholder="https://..."
                                values={aiReferenceUrls}
                                onAdd={(url) => dispatch({ type: 'ADD_TAG', list: 'aiReferenceUrls', value: url })}
                                onRemove={(url) => dispatch({ type: 'REMOVE_TAG', list: 'aiReferenceUrls', value: url })}
                                variant="outline"
                            />
                        </div>
                    )}
                </div>

                {/* AI Suggestion Display */}
                {aiSuggestion && (
                    <div className="rounded-md border bg-muted/20 p-3 space-y-2">
                        <div className="flex items-center justify-between gap-2">
                            <p className="text-xs font-medium">AI Suggestion</p>
                            <div className="flex items-center gap-1.5">
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => field('showAiSuggestionDetails', !showAiSuggestionDetails)}
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

            {/* Basic Form Fields */}
            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                    <Label htmlFor="label">Label *</Label>
                    <Input
                        id="label"
                        value={label}
                        onChange={(e) => field('label', e.target.value)}
                        placeholder="e.g. Blog Post"
                    />
                </div>
                <div className="space-y-1.5">
                    <Label htmlFor="concept-id">ID *</Label>
                    <Input
                        id="concept-id"
                        value={id}
                        onChange={(e) => {
                            field('id', e.target.value);
                            field('idManuallyEdited', true);
                        }}
                        placeholder="auto-generated"
                        className="font-mono text-sm"
                    />
                </div>
            </div>

            {/* Parent Search */}
            <div className="space-y-1.5 relative" ref={parentDropdownRef}>
                <Label>Parent Concept *</Label>
                <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                    <Input
                        value={parentSearch}
                        onChange={(e) => {
                            field('parentSearch', e.target.value);
                            field('showParentDropdown', true);
                            if (!e.target.value) field('inherits', '');
                        }}
                        onFocus={() => field('showParentDropdown', true)}
                        placeholder="Search a base concept (e.g. Document, Report, Contract)..."
                        className="pl-8"
                        aria-autocomplete="list"
                        aria-expanded={showParentDropdown && parentResults.length > 0}
                        aria-controls="parent-search-listbox"
                    />
                    {parentSearchLoading && (
                        <Loader2 className="absolute right-2.5 top-2.5 size-3.5 text-muted-foreground animate-spin" />
                    )}
                </div>
                {inherits && (
                    <p className="text-xs text-muted-foreground">
                        Selected parent: <code className="bg-muted px-1 rounded">{inherits}</code>
                    </p>
                )}
                {showParentDropdown && parentResults.length > 0 && (
                    <div
                        id="parent-search-listbox"
                        role="listbox"
                        aria-label="Parent concept search results"
                        className="absolute z-50 w-full mt-1 border rounded-lg bg-popover shadow-lg max-h-48 overflow-y-auto"
                    >
                        {parentResults.map((c) => (
                            <button
                                key={c.id}
                                role="option"
                                aria-selected={inherits === c.id}
                                onClick={() => {
                                    field('inherits', c.id);
                                    field('parentSearch', c.label);
                                    field('showParentDropdown', false);
                                }}
                                className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-accent text-left"
                            >
                                <span className="font-mono text-xs text-muted-foreground">{c.layer}</span>
                                <span>{c.label}</span>
                                <span className="ml-auto text-xs text-muted-foreground font-mono">{c.id}</span>
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
                    onChange={(e) => field('description', e.target.value)}
                    placeholder="Describe what this concept represents and how it differs from existing ones."
                    rows={4}
                />
            </div>

            {/* Parent Context Card */}
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
}
