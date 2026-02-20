/**
 * TypeScript types for ontology API responses and requests.
 */

// ── Response Types ──────────────────────────────────────────────────

export interface ConceptSummary {
    id: string;
    layer: string;
    label: string;
    inherits: string | null;
    abstract: boolean;
    pillar: string | null;
    synonym_count: number;
    property_count: number;
    has_extraction_template: boolean;
}

export interface ConceptProperty {
    name: string;
    type: string;
    required: boolean;
    default_value: string | null;
    description: string;
}

export interface ConceptRelationship {
    name: string;
    target: string;
    cardinality: string;
    inverse: string | null;
    description: string;
}

export interface ExtractionTemplate {
    classification_hints: string[];
    file_patterns: string[];
}

export interface InheritedPropertyGroup {
    source_id: string;
    source_label: string;
    source_layer: string;
    properties: ConceptProperty[];
    relationships: ConceptRelationship[];
    extraction_template: ExtractionTemplate | null;
}

export interface EmbeddedTypeProperty {
    name: string;
    type: string;
    required: boolean;
    description: string;
    values: string[];
}

export interface EmbeddedType {
    id: string;
    layer: string;
    description: string;
    applies_to: string[];
    synonyms: string[];
    properties: EmbeddedTypeProperty[];
}

export interface ConceptDetail {
    id: string;
    layer: string;
    label: string;
    inherits: string | null;
    abstract: boolean;
    description: string;
    pillar: string | null;
    synonyms: string[];
    mixins: string[];
    properties: ConceptProperty[];
    relationships: ConceptRelationship[];
    extraction_template: ExtractionTemplate | null;
    ancestors: ConceptSummary[] | null;
    inherited_properties: InheritedPropertyGroup[] | null;
    embedded_types: EmbeddedType[];
}

export interface ConceptTreeNode {
    id: string;
    label: string;
    layer: string;
    abstract: boolean;
    pillar: string | null;
    children: ConceptTreeNode[];
}

export interface OntologyStats {
    total_concepts: number;
    by_layer: Record<string, number>;
    by_pillar: Record<string, number>;
    abstract_count: number;
    classifiable_count: number;
}

// ── Request Types ───────────────────────────────────────────────────

export interface CreateConceptPropertyPayload {
    name: string;
    type: string;
    required: boolean;
    default_value?: string;
    description: string;
}

export interface CreateConceptRelationshipPayload {
    name: string;
    target: string;
    cardinality: string;
    inverse?: string;
    description: string;
}

export interface CreateExtractionTemplatePayload {
    classification_hints: string[];
    file_patterns: string[];
}

export interface CreateConceptPayload {
    id: string;
    label: string;
    inherits: string;
    description: string;
    pillar?: string;
    abstract: boolean;
    synonyms: string[];
    mixins: string[];
    properties: CreateConceptPropertyPayload[];
    relationships: CreateConceptRelationshipPayload[];
    extraction_template?: CreateExtractionTemplatePayload;
}

export interface UpdateConceptPayload {
    label?: string;
    description?: string;
    synonyms?: string[];
    properties?: CreateConceptPropertyPayload[];
    relationships?: CreateConceptRelationshipPayload[];
    extraction_template?: CreateExtractionTemplatePayload;
}

export interface SuggestOntologyTypePayload {
    name: string;
    description?: string;
    inherits?: string;
    domain_context?: string;
    style_preferences?: string[];
    reference_urls?: string[];
    include_internet_research?: boolean;
}

export interface SuggestionReference {
    url: string;
    title: string;
    summary: string;
    source_type: string;
}

export interface SuggestOntologyTypeResponse {
    payload: CreateConceptPayload;
    rationale: string;
    parent_reasoning: string;
    adaptation_tips: string[];
    warnings: string[];
    references: SuggestionReference[];
}
