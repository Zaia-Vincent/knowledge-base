import { useReducer, useMemo, useCallback } from 'react';
import type {
    ConceptDetail,
    ConceptSummary,
    CreateConceptPayload,
    CreateConceptPropertyPayload,
    CreateConceptRelationshipPayload,
    SuggestOntologyTypeResponse,
} from '@/types/ontology';
import { toKebabCase, dedupeStrings, mergeProperties, mergeRelationships } from '../utils/wizard-helpers';

// ── Constants ─────────────────────────────────────────────────────────

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

// ── State Shape ───────────────────────────────────────────────────────

export interface WizardState {
    step: number;

    /* Form fields */
    label: string;
    id: string;
    idManuallyEdited: boolean;
    inherits: string;
    description: string;
    synonymInput: string;
    synonyms: string[];
    properties: CreateConceptPropertyPayload[];
    relationships: CreateConceptRelationshipPayload[];
    hintInput: string;
    hints: string[];
    filePatternInput: string;
    filePatterns: string[];

    /* Parent search */
    parentSearch: string;
    parentSearchLoading: boolean;
    parentResults: ConceptSummary[];
    showParentDropdown: boolean;
    parentDetail: ConceptDetail | null;
    loadingParentDetail: boolean;

    /* Source (blueprint) */
    sourceSearch: string;
    sourceSearchLoading: boolean;
    sourceResults: ConceptSummary[];
    showSourceDropdown: boolean;
    sourceConceptId: string;
    sourceDetail: ConceptDetail | null;
    loadingSourceDetail: boolean;
    lastImportMessage: string;

    /* AI Brief */
    aiConceptName: string;
    aiDomainContext: string;
    aiStylePreferencesInput: string;
    aiReferencesInput: string;
    aiReferenceUrls: string[];
    aiLoading: boolean;
    aiSuggestion: SuggestOntologyTypeResponse | null;
    showAiAdvanced: boolean;
    showAiSuggestionDetails: boolean;

    /* UI */
    submitting: boolean;
    error: string | null;
    conflictId: string | null;
}

const INITIAL_STATE: WizardState = {
    step: 0,
    label: '',
    id: '',
    idManuallyEdited: false,
    inherits: '',
    description: '',
    synonymInput: '',
    synonyms: [],
    properties: [],
    relationships: [],
    hintInput: '',
    hints: [],
    filePatternInput: '',
    filePatterns: [],
    parentSearch: '',
    parentSearchLoading: false,
    parentResults: [],
    showParentDropdown: false,
    parentDetail: null,
    loadingParentDetail: false,
    sourceSearch: '',
    sourceSearchLoading: false,
    sourceResults: [],
    showSourceDropdown: false,
    sourceConceptId: '',
    sourceDetail: null,
    loadingSourceDetail: false,
    lastImportMessage: '',
    aiConceptName: '',
    aiDomainContext: '',
    aiStylePreferencesInput: '',
    aiReferencesInput: '',
    aiReferenceUrls: [],
    aiLoading: false,
    aiSuggestion: null,
    showAiAdvanced: false,
    showAiSuggestionDetails: false,
    submitting: false,
    error: null,
    conflictId: null,
};

// ── Actions ───────────────────────────────────────────────────────────

export type WizardAction =
    | { type: 'RESET' }
    | { type: 'SET_FIELD'; field: keyof WizardState; value: unknown }
    | { type: 'SET_STEP'; step: number }
    | { type: 'GO_NEXT' }
    | { type: 'GO_BACK' }

    /* Tag-list actions */
    | { type: 'ADD_TAG'; list: 'synonyms' | 'hints' | 'filePatterns' | 'aiReferenceUrls'; value: string }
    | { type: 'REMOVE_TAG'; list: 'synonyms' | 'hints' | 'filePatterns' | 'aiReferenceUrls'; value: string }

    /* Property / Relationship CRUD */
    | { type: 'ADD_PROPERTY' }
    | { type: 'REMOVE_PROPERTY'; index: number }
    | { type: 'UPDATE_PROPERTY'; index: number; field: keyof CreateConceptPropertyPayload; value: string | boolean }
    | { type: 'ADD_RELATIONSHIP' }
    | { type: 'REMOVE_RELATIONSHIP'; index: number }
    | { type: 'UPDATE_RELATIONSHIP'; index: number; field: keyof CreateConceptRelationshipPayload; value: string }

    /* Bulk imports */
    | { type: 'APPLY_AI_SUGGESTION'; suggestion: SuggestOntologyTypeResponse }
    | { type: 'IMPORT_FROM_SOURCE'; sourceDetail: ConceptDetail }
    | { type: 'IMPORT_FROM_PARENT'; parentDetail: ConceptDetail }

    /* AI state */
    | { type: 'SET_AI_LOADING'; loading: boolean }
    | { type: 'SET_AI_SUGGESTION'; suggestion: SuggestOntologyTypeResponse | null }

    /* Async data */
    | { type: 'SET_PARENT_DETAIL'; detail: ConceptDetail | null; loading: boolean }
    | { type: 'SET_SOURCE_DETAIL'; detail: ConceptDetail | null; loading: boolean }
    ;

// ── Reducer ───────────────────────────────────────────────────────────

function wizardReducer(state: WizardState, action: WizardAction): WizardState {
    switch (action.type) {
        case 'RESET':
            return { ...INITIAL_STATE };

        case 'SET_FIELD':
            return { ...state, [action.field]: action.value };

        case 'SET_STEP':
            return { ...state, step: action.step, error: null };

        case 'GO_NEXT':
            return { ...state, step: Math.min(state.step + 1, STEPS.length - 1), error: null };

        case 'GO_BACK':
            return { ...state, step: Math.max(state.step - 1, 0), error: null };

        case 'ADD_TAG': {
            const trimmed = action.value.trim();
            if (!trimmed) return state;
            const list = state[action.list] as string[];
            if (list.includes(trimmed)) return state;
            return { ...state, [action.list]: [...list, trimmed] };
        }

        case 'REMOVE_TAG':
            return {
                ...state,
                [action.list]: (state[action.list] as string[]).filter((v) => v !== action.value),
            };

        case 'ADD_PROPERTY':
            return { ...state, properties: [...state.properties, { ...EMPTY_PROPERTY }] };

        case 'REMOVE_PROPERTY':
            return { ...state, properties: state.properties.filter((_, i) => i !== action.index) };

        case 'UPDATE_PROPERTY':
            return {
                ...state,
                properties: state.properties.map((p, i) =>
                    i === action.index ? { ...p, [action.field]: action.value } : p,
                ),
            };

        case 'ADD_RELATIONSHIP':
            return { ...state, relationships: [...state.relationships, { ...EMPTY_RELATIONSHIP }] };

        case 'REMOVE_RELATIONSHIP':
            return { ...state, relationships: state.relationships.filter((_, i) => i !== action.index) };

        case 'UPDATE_RELATIONSHIP':
            return {
                ...state,
                relationships: state.relationships.map((r, i) =>
                    i === action.index ? { ...r, [action.field]: action.value } : r,
                ),
            };

        case 'APPLY_AI_SUGGESTION': {
            const draft = action.suggestion.payload;
            const newLabel = draft.label || state.label;
            return {
                ...state,
                label: newLabel,
                id: draft.id || toKebabCase(newLabel || state.aiConceptName || 'new-concept'),
                idManuallyEdited: true,
                inherits: draft.inherits || state.inherits,
                parentSearch: draft.inherits || state.parentSearch,
                description: draft.description || state.description,
                synonyms: dedupeStrings([...state.synonyms, ...(draft.synonyms ?? [])]),
                properties: mergeProperties(state.properties, draft.properties ?? []),
                relationships: mergeRelationships(state.relationships, draft.relationships ?? []),
                hints: dedupeStrings([
                    ...state.hints,
                    ...(draft.extraction_template?.classification_hints ?? []),
                ]),
                filePatterns: dedupeStrings([
                    ...state.filePatterns,
                    ...(draft.extraction_template?.file_patterns ?? []),
                ]),
                lastImportMessage: 'Applied AI draft. You can now refine it in Details.',
                step: 1,
            };
        }

        case 'IMPORT_FROM_SOURCE': {
            const src = action.sourceDetail;
            const et = src.extraction_template;
            const incomingProps = src.properties.map((p) => ({
                name: p.name,
                type: p.type,
                required: p.required,
                description: p.description,
                default_value: p.default_value ?? undefined,
            }));
            const incomingRels = src.relationships.map((r) => ({
                name: r.name,
                target: r.target,
                cardinality: r.cardinality,
                description: r.description,
                inverse: r.inverse ?? undefined,
            }));
            return {
                ...state,
                synonyms: dedupeStrings([...state.synonyms, ...src.synonyms]),
                hints: dedupeStrings([...state.hints, ...(et?.classification_hints ?? [])]),
                filePatterns: dedupeStrings([...state.filePatterns, ...(et?.file_patterns ?? [])]),
                properties: mergeProperties(state.properties, incomingProps),
                relationships: mergeRelationships(state.relationships, incomingRels),
                lastImportMessage: `Imported defaults from ${src.id}.`,
            };
        }

        case 'IMPORT_FROM_PARENT': {
            const pet = action.parentDetail.extraction_template;
            if (!pet) {
                return { ...state, lastImportMessage: 'Parent has no extraction template to import.' };
            }
            return {
                ...state,
                hints: dedupeStrings([...state.hints, ...(pet.classification_hints ?? [])]),
                filePatterns: dedupeStrings([...state.filePatterns, ...(pet.file_patterns ?? [])]),
                lastImportMessage: `Imported ${pet.classification_hints.length} hints and ${pet.file_patterns.length} file patterns from ${action.parentDetail.id}.`,
            };
        }

        case 'SET_AI_LOADING':
            return { ...state, aiLoading: action.loading };

        case 'SET_AI_SUGGESTION':
            return { ...state, aiSuggestion: action.suggestion };

        case 'SET_PARENT_DETAIL':
            return { ...state, parentDetail: action.detail, loadingParentDetail: action.loading };

        case 'SET_SOURCE_DETAIL':
            return { ...state, sourceDetail: action.detail, loadingSourceDetail: action.loading };

        default:
            return state;
    }
}

// ── Hook ──────────────────────────────────────────────────────────────

export function useWizardFormState() {
    const [state, dispatch] = useReducer(wizardReducer, INITIAL_STATE);

    const parentInheritedPropertyNames = useMemo(() => {
        const names = new Set<string>();
        if (!state.parentDetail) return names;
        for (const prop of state.parentDetail.properties) {
            names.add(prop.name.toLowerCase());
        }
        for (const group of state.parentDetail.inherited_properties ?? []) {
            for (const prop of group.properties) {
                names.add(prop.name.toLowerCase());
            }
        }
        return names;
    }, [state.parentDetail]);

    const duplicateOwnProperties = useMemo(() => {
        return state.properties
            .map((p) => p.name.trim())
            .filter((name) => name && parentInheritedPropertyNames.has(name.toLowerCase()));
    }, [state.properties, parentInheritedPropertyNames]);

    const payload = useMemo<CreateConceptPayload>(() => {
        const cleanedProperties = state.properties
            .map((p) => ({
                ...p,
                name: p.name.trim(),
                type: (p.type || 'string').trim(),
                description: p.description.trim(),
            }))
            .filter((p) => p.name);
        const cleanedRelationships = state.relationships
            .map((r) => ({
                ...r,
                name: r.name.trim(),
                target: r.target.trim(),
                cardinality: (r.cardinality || '0..*').trim(),
                description: r.description.trim(),
                inverse: r.inverse?.trim() || undefined,
            }))
            .filter((r) => r.name && r.target);
        const cleanedHints = dedupeStrings(state.hints);
        const cleanedFilePatterns = dedupeStrings(state.filePatterns);

        return {
            id: state.id.trim(),
            label: state.label.trim(),
            inherits: state.inherits.trim(),
            description: state.description.trim(),
            abstract: false,
            synonyms: dedupeStrings(state.synonyms),
            mixins: [],
            properties: cleanedProperties,
            relationships: cleanedRelationships,
            extraction_template:
                cleanedHints.length > 0 || cleanedFilePatterns.length > 0
                    ? { classification_hints: cleanedHints, file_patterns: cleanedFilePatterns }
                    : undefined,
        };
    }, [state.id, state.label, state.inherits, state.description, state.synonyms, state.properties, state.relationships, state.hints, state.filePatterns]);

    const validateStepZero = useCallback(() => {
        if (!state.label.trim()) {
            dispatch({ type: 'SET_FIELD', field: 'error', value: 'Label is required' });
            return false;
        }
        if (!state.id.trim()) {
            dispatch({ type: 'SET_FIELD', field: 'error', value: 'ID is required' });
            return false;
        }
        if (!state.inherits.trim()) {
            dispatch({ type: 'SET_FIELD', field: 'error', value: 'Parent concept is required' });
            return false;
        }
        dispatch({ type: 'SET_FIELD', field: 'error', value: null });
        return true;
    }, [state.label, state.id, state.inherits]);

    return {
        state,
        dispatch,
        payload,
        validateStepZero,
        parentInheritedPropertyNames,
        duplicateOwnProperties,
        STEPS,
    };
}
