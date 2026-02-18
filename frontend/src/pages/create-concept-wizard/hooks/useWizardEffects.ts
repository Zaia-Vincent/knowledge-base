import { useEffect } from 'react';
import { ontologyApi } from '@/lib/ontology-api';
import type { WizardAction, WizardState } from './useWizardFormState';

/**
 * Side-effects for the wizard: auto-id from label, debounced concept search,
 * parent & source detail fetching, and dialog-open reset.
 */
export function useWizardEffects(
    state: WizardState,
    dispatch: React.Dispatch<WizardAction>,
    open: boolean,
) {
    // Auto-generate ID from label
    useEffect(() => {
        if (!state.idManuallyEdited && state.label) {
            const kebab = state.label
                .replace(/([a-z])([A-Z])/g, '$1-$2')
                .replace(/[\s_]+/g, '-')
                .toLowerCase()
                .replace(/[^a-z0-9-]/g, '');
            dispatch({ type: 'SET_FIELD', field: 'id', value: kebab });
        }
    }, [state.label, state.idManuallyEdited, dispatch]);

    // Sync AI concept name from label
    useEffect(() => {
        if (state.label.trim() && !state.aiConceptName.trim()) {
            dispatch({ type: 'SET_FIELD', field: 'aiConceptName', value: state.label });
        }
    }, [state.label, state.aiConceptName, dispatch]);

    // Debounced parent search
    useEffect(() => {
        if (state.parentSearch.length < 2) {
            dispatch({ type: 'SET_FIELD', field: 'parentSearchLoading', value: false } as WizardAction);
            return;
        }
        dispatch({ type: 'SET_FIELD', field: 'parentSearchLoading', value: true } as WizardAction);
        const timer = setTimeout(async () => {
            try {
                const results = await ontologyApi.search(state.parentSearch);
                dispatch({ type: 'SET_FIELD', field: 'parentResults', value: results.slice(0, 10) } as WizardAction);
            } catch {
                dispatch({ type: 'SET_FIELD', field: 'parentResults', value: [] } as WizardAction);
            } finally {
                dispatch({ type: 'SET_FIELD', field: 'parentSearchLoading', value: false } as WizardAction);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [state.parentSearch, dispatch]);

    // Fetch parent detail when inherits changes
    useEffect(() => {
        if (!state.inherits.trim()) {
            dispatch({ type: 'SET_PARENT_DETAIL', detail: null, loading: false });
            return;
        }
        let cancelled = false;
        dispatch({ type: 'SET_PARENT_DETAIL', detail: state.parentDetail, loading: true });
        ontologyApi.getConcept(state.inherits.trim())
            .then((detail) => {
                if (!cancelled) dispatch({ type: 'SET_PARENT_DETAIL', detail, loading: false });
            })
            .catch(() => {
                if (!cancelled) dispatch({ type: 'SET_PARENT_DETAIL', detail: null, loading: false });
            });
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [state.inherits, dispatch]);

    // Debounced source search
    useEffect(() => {
        if (state.sourceSearch.length < 2) {
            dispatch({ type: 'SET_FIELD', field: 'sourceSearchLoading', value: false } as WizardAction);
            return;
        }
        dispatch({ type: 'SET_FIELD', field: 'sourceSearchLoading', value: true } as WizardAction);
        const timer = setTimeout(async () => {
            try {
                const results = await ontologyApi.search(state.sourceSearch);
                dispatch({
                    type: 'SET_FIELD',
                    field: 'sourceResults',
                    value: results.filter((c) => c.id !== state.inherits).slice(0, 10),
                } as WizardAction);
            } catch {
                dispatch({ type: 'SET_FIELD', field: 'sourceResults', value: [] } as WizardAction);
            } finally {
                dispatch({ type: 'SET_FIELD', field: 'sourceSearchLoading', value: false } as WizardAction);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [state.sourceSearch, state.inherits, dispatch]);

    // Fetch source concept detail
    useEffect(() => {
        if (!state.sourceConceptId.trim()) {
            dispatch({ type: 'SET_SOURCE_DETAIL', detail: null, loading: false });
            return;
        }
        let cancelled = false;
        dispatch({ type: 'SET_SOURCE_DETAIL', detail: state.sourceDetail, loading: true });
        ontologyApi.getConcept(state.sourceConceptId.trim())
            .then((detail) => {
                if (!cancelled) dispatch({ type: 'SET_SOURCE_DETAIL', detail, loading: false });
            })
            .catch(() => {
                if (!cancelled) dispatch({ type: 'SET_SOURCE_DETAIL', detail: null, loading: false });
            });
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [state.sourceConceptId, dispatch]);

    // Reset form when dialog opens
    useEffect(() => {
        if (open) {
            dispatch({ type: 'RESET' });
        }
    }, [open, dispatch]);
}
