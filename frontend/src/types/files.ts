/**
 * TypeScript types for the file processing module.
 * Mirrors the backend Pydantic schemas (JSONB version).
 */

export interface ClassificationSignal {
    method: string;
    concept_id: string;
    score: number;
    details: string;
}

export interface ClassificationResult {
    primary_concept_id: string;
    confidence: number;
    signals: ClassificationSignal[];
}

export interface MetadataField {
    value: string | number | null;
    confidence: number;
    raw_text?: string | null;
    source_quote?: string | null;
}

export interface ExtraField {
    field_name: string;
    value: string | number | null;
    confidence: number;
    source_quote?: string | null;
}

export interface ProcessedFileSummary {
    id: string;
    filename: string;
    original_path: string;
    file_size: number;
    mime_type: string;
    status: string;
    classification_concept_id: string | null;
    classification_confidence: number | null;
    concept_label: string | null;
    origin_file_id: string | null;
    page_range: string | null;
    uploaded_at: string;
    processed_at: string | null;
    error_message: string | null;
}

export interface ProcessedFileDetail {
    id: string;
    filename: string;
    original_path: string;
    file_size: number;
    mime_type: string;
    status: string;
    extracted_text_preview: string | null;
    classification: ClassificationResult | null;
    metadata: Record<string, MetadataField>;
    extra_fields: ExtraField[];
    summary: string | null;
    language: string | null;
    processing_time_ms: number | null;
    uploaded_at: string;
    processed_at: string | null;
    error_message: string | null;
}

export interface UploadResult {
    files: ProcessedFileSummary[];
    total_count: number;
    message: string;
}

export type ProcessingStatus =
    | 'pending'
    | 'extracting_text'
    | 'classifying'
    | 'extracting_metadata'
    | 'done'
    | 'error';
