import { useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Search, Copy, Sparkles, Loader2 } from 'lucide-react';
import { useClickOutside } from '@/hooks/useClickOutside';
import { TagListInput } from '../components/TagListInput';
import { PropertyEditor } from '../components/PropertyEditor';
import { RelationshipEditor } from '../components/RelationshipEditor';
import type { WizardState, WizardAction } from '../hooks/useWizardFormState';

interface DetailsStepProps {
    state: WizardState;
    dispatch: React.Dispatch<WizardAction>;
    duplicateOwnProperties: string[];
}

/**
 * Step 2 — source import, synonyms, hints, file patterns, properties, relationships.
 */
export function DetailsStep({ state, dispatch, duplicateOwnProperties }: DetailsStepProps) {
    const {
        sourceSearch, sourceSearchLoading, sourceResults, showSourceDropdown,
        sourceDetail, loadingSourceDetail,
        parentDetail, lastImportMessage,
        synonyms, hints, filePatterns, properties, relationships,
    } = state;

    const field = (f: keyof WizardState, value: unknown) =>
        dispatch({ type: 'SET_FIELD', field: f, value });

    // Click-outside for source dropdown
    const sourceDropdownRef = useRef<HTMLDivElement>(null);
    useClickOutside(sourceDropdownRef, useCallback(() => {
        field('showSourceDropdown', false);
    }, [dispatch])); // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <div className="space-y-5">
            {/* Source Import Panel */}
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
                        onClick={() => {
                            if (parentDetail) {
                                dispatch({ type: 'IMPORT_FROM_PARENT', parentDetail });
                            }
                        }}
                        disabled={!parentDetail?.extraction_template}
                    >
                        <Sparkles className="size-3.5 mr-1" />
                        Import Parent Template
                    </Button>
                </div>

                <div className="space-y-1.5 relative" ref={sourceDropdownRef}>
                    <Label>Import From Concept</Label>
                    <div className="flex gap-2">
                        <div className="relative flex-1">
                            <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
                            <Input
                                value={sourceSearch}
                                onChange={(e) => {
                                    field('sourceSearch', e.target.value);
                                    field('showSourceDropdown', true);
                                    if (!e.target.value) field('sourceConceptId', '');
                                }}
                                onFocus={() => field('showSourceDropdown', true)}
                                placeholder="Find an existing concept to copy defaults from..."
                                className="pl-8"
                                aria-autocomplete="list"
                                aria-expanded={showSourceDropdown && sourceResults.length > 0}
                                aria-controls="source-search-listbox"
                            />
                            {sourceSearchLoading && (
                                <Loader2 className="absolute right-2.5 top-2.5 size-3.5 text-muted-foreground animate-spin" />
                            )}
                        </div>
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => {
                                if (sourceDetail) {
                                    dispatch({ type: 'IMPORT_FROM_SOURCE', sourceDetail });
                                }
                            }}
                            disabled={!sourceDetail || loadingSourceDetail}
                        >
                            <Copy className="size-3.5 mr-1" />
                            Import
                        </Button>
                    </div>
                    {showSourceDropdown && sourceResults.length > 0 && (
                        <div
                            id="source-search-listbox"
                            role="listbox"
                            aria-label="Source concept search results"
                            className="absolute z-50 w-full mt-1 border rounded-lg bg-popover shadow-lg max-h-48 overflow-y-auto"
                        >
                            {sourceResults.map((c) => (
                                <button
                                    key={c.id}
                                    role="option"
                                    aria-selected={false}
                                    onClick={() => {
                                        field('sourceConceptId', c.id);
                                        field('sourceSearch', c.label);
                                        field('showSourceDropdown', false);
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
                    <div
                        aria-live="polite"
                        className="rounded-lg border border-emerald-300/60 bg-emerald-50/60 p-2 text-xs text-emerald-800 break-words"
                    >
                        {lastImportMessage}
                    </div>
                )}
            </div>

            {/* Tag Lists */}
            <TagListInput
                label="Synonyms"
                placeholder="Add synonym…"
                values={synonyms}
                onAdd={(v) => dispatch({ type: 'ADD_TAG', list: 'synonyms', value: v })}
                onRemove={(v) => dispatch({ type: 'REMOVE_TAG', list: 'synonyms', value: v })}
            />

            <TagListInput
                label="Classification Hints"
                placeholder="e.g. blog post, article, published on"
                values={hints}
                onAdd={(v) => dispatch({ type: 'ADD_TAG', list: 'hints', value: v })}
                onRemove={(v) => dispatch({ type: 'REMOVE_TAG', list: 'hints', value: v })}
            />

            <TagListInput
                label="File Patterns"
                placeholder="e.g. **/blog/** or /articles/"
                values={filePatterns}
                onAdd={(v) => dispatch({ type: 'ADD_TAG', list: 'filePatterns', value: v })}
                onRemove={(v) => dispatch({ type: 'REMOVE_TAG', list: 'filePatterns', value: v })}
                variant="outline"
                badgeClassName="font-mono"
            />

            {/* Property & Relationship Editors */}
            <PropertyEditor
                properties={properties}
                duplicateOwnProperties={duplicateOwnProperties}
                dispatch={dispatch}
            />

            <RelationshipEditor
                relationships={relationships}
                dispatch={dispatch}
            />
        </div>
    );
}
