import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Plus, X } from 'lucide-react';

interface TagListInputProps {
    label: string;
    placeholder?: string;
    values: string[];
    onAdd: (value: string) => void;
    onRemove: (value: string) => void;
    /** Badge variant, defaults to "secondary" */
    variant?: 'secondary' | 'outline';
    /** Extra className on badges (e.g. "font-mono") */
    badgeClassName?: string;
}

/**
 * Reusable input + badge list for synonyms, hints, file patterns, reference URLs.
 */
export function TagListInput({
    label,
    placeholder = 'Add item…',
    values,
    onAdd,
    onRemove,
    variant = 'secondary',
    badgeClassName,
}: TagListInputProps) {
    const [input, setInput] = useState('');

    const handleAdd = () => {
        const trimmed = input.trim();
        if (trimmed) {
            onAdd(trimmed);
            setInput('');
        }
    };

    return (
        <div className="space-y-1.5">
            <Label>{label}</Label>
            <div className="flex gap-2">
                <Input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={placeholder}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            handleAdd();
                        }
                    }}
                />
                <Button type="button" variant="outline" size="sm" onClick={handleAdd}>
                    <Plus className="size-3.5" />
                </Button>
            </div>
            {values.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                    {values.map((v) => (
                        <Badge key={v} variant={variant} className={`gap-1 ${badgeClassName ?? ''}`}>
                            {v}
                            <button onClick={() => onRemove(v)} aria-label={`Remove ${v}`}>
                                <X className="size-3" />
                            </button>
                        </Badge>
                    ))}
                </div>
            )}
        </div>
    );
}
