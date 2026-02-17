/**
 * TypeScript types for the Query module — mirrors backend Pydantic schemas.
 */

export interface MetadataFilter {
    field_name: string;
    value: string;
    operator: string;
}

export interface QueryIntent {
    original_question: string;
    resolved_language: string;
    concept_ids: string[];
    concept_labels: string[];
    metadata_filters: MetadataFilter[];
    keywords: string[];
    text_query: string | null;
    reasoning: string;
}

export interface QueryMatch {
    file_id: string;
    filename: string;
    concept_id: string | null;
    concept_label: string | null;
    confidence: number;
    summary: string | null;
    metadata: Record<string, unknown>;
    relevance_score: number;
}

export interface QueryResult {
    intent: QueryIntent;
    matches: QueryMatch[];
    total_matches: number;
}

export interface QueryRequest {
    question: string;
    max_results?: number;
}
