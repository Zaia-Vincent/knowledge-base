import { useCallback } from 'react';
import { ontologyApi } from '@/lib/ontology-api';
import { ApiError } from '@/lib/api-client';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChevronLeft, ChevronRight } from 'lucide-react';

import { useWizardFormState } from './hooks/useWizardFormState';
import { useWizardEffects } from './hooks/useWizardEffects';
import { useAiSuggestion } from './hooks/useAiSuggestion';
import { AiBriefStep } from './steps/AiBriefStep';
import { DetailsStep } from './steps/DetailsStep';
import { ReviewStep } from './steps/ReviewStep';

interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onCreated: (createdId?: string) => void;
}

/**
 * Slim orchestrator for the L3 Concept Creation Wizard.
 *
 * Delegates state management to `useWizardFormState` (useReducer),
 * side-effects to `useWizardEffects`, and AI logic to `useAiSuggestion`.
 * Each wizard step is a separate component.
 */
export function CreateConceptDialog({ open, onOpenChange, onCreated }: Props) {
    const {
        state,
        dispatch,
        payload,
        validateStepZero,
        duplicateOwnProperties,
        STEPS,
    } = useWizardFormState();

    useWizardEffects(state, dispatch, open);
    const { generateAiSuggestion, applySuggestion } = useAiSuggestion(state, dispatch);

    // ── Navigation ────────────────────────────────────────────────

    const goNext = useCallback(() => {
        if (state.step === 0 && !validateStepZero()) return;
        dispatch({ type: 'GO_NEXT' });
    }, [state.step, validateStepZero, dispatch]);

    const goBack = useCallback(() => {
        dispatch({ type: 'GO_BACK' });
    }, [dispatch]);

    // ── Submit ────────────────────────────────────────────────────

    const handleSubmit = useCallback(async () => {
        dispatch({ type: 'SET_FIELD', field: 'error', value: null });
        if (!validateStepZero()) return;

        try {
            dispatch({ type: 'SET_FIELD', field: 'submitting', value: true });
            await ontologyApi.createConcept(payload);
            onCreated(payload.id);
        } catch (err: unknown) {
            if (err instanceof ApiError && err.status === 409) {
                dispatch({
                    type: 'SET_FIELD',
                    field: 'error',
                    value: `A concept with ID "${payload.id}" already exists. Delete it first from the manager or choose a different name.`,
                });
                dispatch({ type: 'SET_FIELD', field: 'conflictId', value: payload.id });
            } else {
                const message = err instanceof Error ? err.message : 'Failed to create concept';
                dispatch({ type: 'SET_FIELD', field: 'error', value: message });
            }
        } finally {
            dispatch({ type: 'SET_FIELD', field: 'submitting', value: false });
        }
    }, [validateStepZero, payload, onCreated, dispatch]);

    const handleReplaceExisting = useCallback(async () => {
        if (!state.conflictId) return;
        try {
            dispatch({ type: 'SET_FIELD', field: 'submitting', value: true });
            dispatch({ type: 'SET_FIELD', field: 'error', value: null });
            await ontologyApi.deleteConcept(state.conflictId);
            await ontologyApi.createConcept(payload);
            dispatch({ type: 'SET_FIELD', field: 'conflictId', value: null });
            onCreated(payload.id);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Failed to replace concept';
            dispatch({ type: 'SET_FIELD', field: 'error', value: message });
        } finally {
            dispatch({ type: 'SET_FIELD', field: 'submitting', value: false });
        }
    }, [state.conflictId, payload, onCreated, dispatch]);

    // ── Render ────────────────────────────────────────────────────

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="w-[min(96vw,980px)] h-[min(92vh,860px)] !flex !flex-col overflow-hidden">
                <DialogHeader>
                    <DialogTitle>Create L3 Concept Wizard</DialogTitle>
                    <DialogDescription>
                        Reuse existing ontology concepts, templates, and fields before creating a new type.
                    </DialogDescription>
                </DialogHeader>

                {/* Step indicator */}
                <div className="grid shrink-0 grid-cols-3 gap-2">
                    {STEPS.map((s, index) => (
                        <button
                            key={s.id}
                            onClick={() => {
                                if (index <= state.step) dispatch({ type: 'SET_STEP', step: index });
                            }}
                            className={`rounded-md border px-2 py-1.5 text-left transition-colors ${index === state.step
                                ? 'border-primary bg-primary/5'
                                : index < state.step
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

                {/* Active step content */}
                <ScrollArea className="min-h-0 flex-1 -mx-6 px-6">
                    <div className="space-y-5 py-2">
                        <div className="space-y-1">
                            <p className="text-sm font-medium">{STEPS[state.step].title}</p>
                            <p className="text-xs text-muted-foreground">{STEPS[state.step].description}</p>
                        </div>

                        {state.step === 0 && (
                            <AiBriefStep
                                state={state}
                                dispatch={dispatch}
                                generateAiSuggestion={generateAiSuggestion}
                                applySuggestion={applySuggestion}
                            />
                        )}

                        {state.step === 1 && (
                            <DetailsStep
                                state={state}
                                dispatch={dispatch}
                                duplicateOwnProperties={duplicateOwnProperties}
                            />
                        )}

                        {state.step === 2 && (
                            <ReviewStep payload={payload} />
                        )}

                        {state.error && (
                            <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive">
                                <p>{state.error}</p>
                                {state.conflictId && (
                                    <Button
                                        variant="destructive"
                                        size="sm"
                                        className="mt-2"
                                        onClick={handleReplaceExisting}
                                        disabled={state.submitting}
                                    >
                                        {state.submitting ? 'Replacing…' : `Replace existing "${state.conflictId}"`}
                                    </Button>
                                )}
                            </div>
                        )}
                    </div>
                </ScrollArea>

                {/* Footer */}
                <DialogFooter>
                    <div className="flex w-full items-center justify-between gap-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)} disabled={state.submitting}>
                            Cancel
                        </Button>
                        <div className="flex items-center gap-2">
                            {state.step > 0 && (
                                <Button type="button" variant="outline" onClick={goBack} disabled={state.submitting}>
                                    <ChevronLeft className="size-4 mr-1" />
                                    Back
                                </Button>
                            )}
                            {state.step < STEPS.length - 1 ? (
                                <Button type="button" onClick={goNext} disabled={state.submitting}>
                                    Next
                                    <ChevronRight className="size-4 ml-1" />
                                </Button>
                            ) : (
                                <Button onClick={handleSubmit} disabled={state.submitting}>
                                    {state.submitting ? 'Creating…' : 'Create Concept'}
                                </Button>
                            )}
                        </div>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
