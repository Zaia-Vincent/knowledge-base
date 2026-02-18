import type {
    CreateConceptPropertyPayload,
    CreateConceptRelationshipPayload,
} from '@/types/ontology';

/** Convert a label string to a kebab-case identifier. */
export function toKebabCase(s: string): string {
    return s
        .replace(/([a-z])([A-Z])/g, '$1-$2')
        .replace(/[\s_]+/g, '-')
        .toLowerCase()
        .replace(/[^a-z0-9-]/g, '')
        .replace(/-{2,}/g, '-')
        .replace(/^-|-$/g, '');
}

/** De-duplicate an array of strings (case-insensitive, preserves first occurrence). */
export function dedupeStrings(values: string[]): string[] {
    const out: string[] = [];
    const seen = new Set<string>();
    for (const value of values) {
        const trimmed = value.trim();
        if (!trimmed) continue;
        const key = trimmed.toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(trimmed);
    }
    return out;
}

/** Merge property arrays by name (case-insensitive), keeping existing entries. */
export function mergeProperties(
    current: CreateConceptPropertyPayload[],
    incoming: CreateConceptPropertyPayload[],
): CreateConceptPropertyPayload[] {
    const byName = new Map<string, CreateConceptPropertyPayload>();
    for (const prop of current) {
        if (prop.name.trim()) byName.set(prop.name.trim().toLowerCase(), prop);
    }
    for (const prop of incoming) {
        const name = prop.name.trim();
        if (!name) continue;
        const key = name.toLowerCase();
        if (!byName.has(key)) {
            byName.set(key, {
                name,
                type: prop.type || 'string',
                required: Boolean(prop.required),
                description: prop.description ?? '',
                default_value: prop.default_value,
            });
        }
    }
    return Array.from(byName.values());
}

/** Merge relationship arrays by (name + target), keeping existing entries. */
export function mergeRelationships(
    current: CreateConceptRelationshipPayload[],
    incoming: CreateConceptRelationshipPayload[],
): CreateConceptRelationshipPayload[] {
    const keyFor = (rel: CreateConceptRelationshipPayload) =>
        `${rel.name.trim().toLowerCase()}::${rel.target.trim().toLowerCase()}`;
    const seen = new Set<string>();
    const out: CreateConceptRelationshipPayload[] = [];

    for (const rel of [...current, ...incoming]) {
        const name = rel.name.trim();
        const target = rel.target.trim();
        if (!name || !target) continue;
        const normalized: CreateConceptRelationshipPayload = {
            name,
            target,
            cardinality: rel.cardinality || '0..*',
            description: rel.description ?? '',
            inverse: rel.inverse,
        };
        const key = keyFor(normalized);
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(normalized);
    }
    return out;
}
