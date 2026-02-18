import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Plus, X } from 'lucide-react';
import type { CreateConceptRelationshipPayload } from '@/types/ontology';
import type { WizardAction } from '../hooks/useWizardFormState';

interface RelationshipEditorProps {
    relationships: CreateConceptRelationshipPayload[];
    dispatch: React.Dispatch<WizardAction>;
}

/**
 * Grid-based relationship CRUD editor, extracted from DetailsStep.
 */
export function RelationshipEditor({ relationships, dispatch }: RelationshipEditorProps) {
    return (
        <div className="space-y-1.5">
            <div className="flex items-center justify-between">
                <Label>Relationships</Label>
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => dispatch({ type: 'ADD_RELATIONSHIP' })}
                >
                    <Plus className="size-3 mr-1" /> Add
                </Button>
            </div>
            {relationships.map((rel, i) => (
                <div key={`${rel.name}-${rel.target}-${i}`} className="grid grid-cols-[1fr_1fr_110px_auto] gap-2 rounded-lg border p-2">
                    <Input
                        value={rel.name}
                        onChange={(e) => dispatch({ type: 'UPDATE_RELATIONSHIP', index: i, field: 'name', value: e.target.value })}
                        placeholder="Name"
                        className="h-8 text-sm"
                    />
                    <Input
                        value={rel.target}
                        onChange={(e) => dispatch({ type: 'UPDATE_RELATIONSHIP', index: i, field: 'target', value: e.target.value })}
                        placeholder="Target concept ID"
                        className="h-8 text-sm font-mono"
                    />
                    <Input
                        value={rel.cardinality}
                        onChange={(e) => dispatch({ type: 'UPDATE_RELATIONSHIP', index: i, field: 'cardinality', value: e.target.value })}
                        placeholder="0..*"
                        className="h-8 text-sm font-mono"
                    />
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => dispatch({ type: 'REMOVE_RELATIONSHIP', index: i })}
                        className="px-1.5"
                    >
                        <X className="size-3.5" />
                    </Button>
                    <div className="col-span-4">
                        <Input
                            value={rel.description}
                            onChange={(e) => dispatch({ type: 'UPDATE_RELATIONSHIP', index: i, field: 'description', value: e.target.value })}
                            placeholder="Description"
                            className="h-8 text-xs"
                        />
                    </div>
                </div>
            ))}
        </div>
    );
}
