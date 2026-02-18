import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Plus, X } from 'lucide-react';
import type { CreateConceptPropertyPayload } from '@/types/ontology';
import { AlertTriangle } from 'lucide-react';
import type { WizardAction } from '../hooks/useWizardFormState';

interface PropertyEditorProps {
    properties: CreateConceptPropertyPayload[];
    duplicateOwnProperties: string[];
    dispatch: React.Dispatch<WizardAction>;
}

/**
 * Grid-based property CRUD editor, extracted from DetailsStep.
 */
export function PropertyEditor({ properties, duplicateOwnProperties, dispatch }: PropertyEditorProps) {
    return (
        <div className="space-y-1.5">
            <div className="flex items-center justify-between">
                <Label>Own Properties</Label>
                <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => dispatch({ type: 'ADD_PROPERTY' })}
                >
                    <Plus className="size-3 mr-1" /> Add
                </Button>
            </div>
            {properties.map((prop, i) => (
                <div key={`${prop.name}-${i}`} className="grid grid-cols-[1.4fr_1fr_auto_auto] gap-2 rounded-lg border p-2">
                    <Input
                        value={prop.name}
                        onChange={(e) => dispatch({ type: 'UPDATE_PROPERTY', index: i, field: 'name', value: e.target.value })}
                        placeholder="Name"
                        className="h-8 text-sm"
                    />
                    <Input
                        value={prop.type}
                        onChange={(e) => dispatch({ type: 'UPDATE_PROPERTY', index: i, field: 'type', value: e.target.value })}
                        placeholder="Type (string, date, ref:Person, ...)"
                        className="h-8 text-sm font-mono"
                    />
                    <label className="flex items-center gap-1 text-xs whitespace-nowrap px-1">
                        <input
                            type="checkbox"
                            checked={prop.required}
                            onChange={(e) => dispatch({ type: 'UPDATE_PROPERTY', index: i, field: 'required', value: e.target.checked })}
                            className="size-3.5"
                        />
                        Req
                    </label>
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => dispatch({ type: 'REMOVE_PROPERTY', index: i })}
                        className="px-1.5"
                    >
                        <X className="size-3.5" />
                    </Button>
                    <div className="col-span-4">
                        <Input
                            value={prop.description}
                            onChange={(e) => dispatch({ type: 'UPDATE_PROPERTY', index: i, field: 'description', value: e.target.value })}
                            placeholder="Description"
                            className="h-8 text-xs"
                        />
                    </div>
                </div>
            ))}
            {duplicateOwnProperties.length > 0 && (
                <div className="rounded-md border border-amber-300/70 bg-amber-50/70 p-2 text-xs text-amber-900 flex items-start gap-2">
                    <AlertTriangle className="size-3.5 mt-0.5 shrink-0" />
                    <span>
                        You redefine inherited property name(s): {duplicateOwnProperties.join(', ')}.
                        This overrides parent definitions.
                    </span>
                </div>
            )}
        </div>
    );
}
