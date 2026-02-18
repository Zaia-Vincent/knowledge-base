import { describe, it, expect } from 'vitest';
import {
    toKebabCase,
    dedupeStrings,
    mergeProperties,
    mergeRelationships,
} from './wizard-helpers';

/* ────────────────────────── toKebabCase ────────────────────────── */

describe('toKebabCase', () => {
    it('converts camelCase', () => {
        expect(toKebabCase('blogPost')).toBe('blog-post');
    });

    it('converts PascalCase', () => {
        expect(toKebabCase('BlogPost')).toBe('blog-post');
    });

    it('converts spaces', () => {
        expect(toKebabCase('Blog Post')).toBe('blog-post');
    });

    it('converts underscores', () => {
        expect(toKebabCase('blog_post')).toBe('blog-post');
    });

    it('handles special characters', () => {
        expect(toKebabCase('Blog Post (Draft #1)')).toBe('blog-post-draft-1');
    });

    it('handles empty string', () => {
        expect(toKebabCase('')).toBe('');
    });

    it('collapses multiple hyphens', () => {
        expect(toKebabCase('Blog---Post')).toBe('blog-post');
    });

    it('trims leading/trailing hyphens', () => {
        expect(toKebabCase('-Blog Post-')).toBe('blog-post');
    });

    it('handles already kebab-case', () => {
        expect(toKebabCase('blog-post')).toBe('blog-post');
    });

    it('handles single word', () => {
        expect(toKebabCase('Document')).toBe('document');
    });

    it('handles SCREAMING_SNAKE', () => {
        expect(toKebabCase('MY_BLOG_POST')).toBe('my-blog-post');
    });
});

/* ────────────────────────── dedupeStrings ────────────────────────── */

describe('dedupeStrings', () => {
    it('removes duplicates (case-insensitive)', () => {
        expect(dedupeStrings(['foo', 'FOO', 'bar'])).toEqual(['foo', 'bar']);
    });

    it('filters empty and whitespace-only entries', () => {
        expect(dedupeStrings(['', '  ', 'foo', '  '])).toEqual(['foo']);
    });

    it('returns empty array for empty input', () => {
        expect(dedupeStrings([])).toEqual([]);
    });

    it('preserves order of first occurrence', () => {
        expect(dedupeStrings(['c', 'a', 'b', 'a', 'c'])).toEqual(['c', 'a', 'b']);
    });

    it('trims entries', () => {
        expect(dedupeStrings(['  foo  ', 'foo'])).toEqual(['foo']);
    });
});

/* ────────────────────────── mergeProperties ────────────────────────── */

describe('mergeProperties', () => {
    it('merges non-overlapping properties', () => {
        const result = mergeProperties(
            [{ name: 'title', type: 'string', required: true, description: 'x' }],
            [{ name: 'author', type: 'string', required: false, description: 'y' }],
        );
        expect(result).toHaveLength(2);
        expect(result.map((p) => p.name)).toEqual(['title', 'author']);
    });

    it('skips duplicates by name', () => {
        const result = mergeProperties(
            [{ name: 'title', type: 'string', required: true, description: 'existing' }],
            [{ name: 'title', type: 'text', required: false, description: 'incoming' }],
        );
        expect(result).toHaveLength(1);
        expect(result[0].description).toBe('existing');
    });

    it('handles empty arrays', () => {
        expect(mergeProperties([], [])).toEqual([]);
    });

    it('handles empty base array', () => {
        const incoming = [{ name: 'a', type: 'string', required: false, description: '' }];
        expect(mergeProperties([], incoming)).toEqual(incoming);
    });
});

/* ────────────────────────── mergeRelationships ────────────────────────── */

describe('mergeRelationships', () => {
    it('merges non-overlapping relationships', () => {
        const result = mergeRelationships(
            [{ name: 'authored_by', target: 'Person', cardinality: '1..1', description: '' }],
            [{ name: 'tagged_with', target: 'Tag', cardinality: '0..*', description: '' }],
        );
        expect(result).toHaveLength(2);
    });

    it('skips duplicates by (name + target)', () => {
        const result = mergeRelationships(
            [{ name: 'authored_by', target: 'Person', cardinality: '1..1', description: 'a' }],
            [{ name: 'authored_by', target: 'Person', cardinality: '0..*', description: 'b' }],
        );
        expect(result).toHaveLength(1);
        expect(result[0].cardinality).toBe('1..1');
    });

    it('preserves cardinality of existing entries', () => {
        const result = mergeRelationships(
            [{ name: 'likes', target: 'Article', cardinality: '0..*', description: '' }],
            [{ name: 'likes', target: 'Article', cardinality: '1..*', description: '' }],
        );
        expect(result[0].cardinality).toBe('0..*');
    });

    it('allows same name with different targets', () => {
        const result = mergeRelationships(
            [{ name: 'related_to', target: 'Document', cardinality: '0..*', description: '' }],
            [{ name: 'related_to', target: 'Article', cardinality: '0..*', description: '' }],
        );
        expect(result).toHaveLength(2);
    });

    it('handles empty arrays', () => {
        expect(mergeRelationships([], [])).toEqual([]);
    });
});
