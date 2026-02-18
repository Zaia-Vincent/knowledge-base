import { useCallback } from 'react';
import { ontologyApi } from '@/lib/ontology-api';
import type { SuggestOntologyTypeResponse } from '@/types/ontology';
import type { WizardAction, WizardState } from './useWizardFormState';
import { dedupeStrings } from '../utils/wizard-helpers';

/**
 * Encapsulates AI suggestion generation logic.
 */
export function useAiSuggestion(
    state: WizardState,
    dispatch: React.Dispatch<WizardAction>,
) {
    const generateAiSuggestion = useCallback(async () => {
        const idea = state.aiConceptName.trim() || state.label.trim();
        if (!idea) {
            dispatch({ type: 'SET_FIELD', field: 'error', value: 'Provide a concept name or idea before generating an AI draft.' });
            return;
        }

        try {
            dispatch({ type: 'SET_FIELD', field: 'error', value: null });
            dispatch({ type: 'SET_AI_LOADING', loading: true });
            const stylePreferences = dedupeStrings(
                state.aiStylePreferencesInput
                    .split(',')
                    .map((s) => s.trim())
                    .filter(Boolean),
            );

            const suggestion: SuggestOntologyTypeResponse = await ontologyApi.suggestType({
                name: idea,
                description: state.description.trim(),
                inherits: state.inherits.trim() || undefined,
                domain_context: state.aiDomainContext.trim(),
                style_preferences: stylePreferences,
                reference_urls: state.aiReferenceUrls,
                include_internet_research: true,
            });

            dispatch({ type: 'SET_AI_SUGGESTION', suggestion });
            dispatch({ type: 'SET_FIELD', field: 'lastImportMessage', value: 'AI suggestion generated. Review and apply it when ready.' });
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : 'Failed to generate AI suggestion';
            dispatch({ type: 'SET_FIELD', field: 'error', value: message });
        } finally {
            dispatch({ type: 'SET_AI_LOADING', loading: false });
        }
    }, [
        state.aiConceptName,
        state.label,
        state.description,
        state.inherits,
        state.aiDomainContext,
        state.aiStylePreferencesInput,
        state.aiReferenceUrls,
        dispatch,
    ]);

    const applySuggestion = useCallback((suggestion: SuggestOntologyTypeResponse) => {
        dispatch({ type: 'APPLY_AI_SUGGESTION', suggestion });
    }, [dispatch]);

    return { generateAiSuggestion, applySuggestion };
}
