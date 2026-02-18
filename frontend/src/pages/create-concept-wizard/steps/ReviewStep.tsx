import { Label } from '@/components/ui/label';
import type { CreateConceptPayload } from '@/types/ontology';

interface ReviewStepProps {
    payload: CreateConceptPayload;
}

/**
 * Step 3 — review summary grid and JSON request preview.
 */
export function ReviewStep({ payload }: ReviewStepProps) {
    return (
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
}
