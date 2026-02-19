import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Search,
    Loader2,
    AlertCircle,
    Brain,
    FileText,
    Tag,
    Languages,
    Sparkles,
    Filter,
    ArrowRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { queryApi } from '@/lib/query-api';
import type { QueryResult, QueryMatch } from '@/types/query';

/* ── Page ────────────────────────────────────────────────────────── */

export function QueryPage() {
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<QueryResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const navigate = useNavigate();

    const submitQuery = useCallback(async () => {
        const question = input.trim();
        if (!question || isLoading) return;

        setError(null);
        setIsLoading(true);

        try {
            const data = await queryApi.submit({ question, max_results: 20 });
            setResult(data);
        } catch (err) {
            setError((err as Error).message || 'Query failed');
        } finally {
            setIsLoading(false);
        }
    }, [input, isLoading]);

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitQuery();
            }
        },
        [submitQuery],
    );

    const suggestions = [
        'Show me all invoices',
        'Welke contracten zijn er?',
        'Find documents from Acme',
    ];

    const isEmpty = !result && !error;

    return (
        <div className="flex h-full flex-col max-w-5xl mx-auto">
            {/* Header */}
            <div className="pb-6">
                <div className="flex items-center gap-2 mb-1">
                    <Search className="size-5 text-muted-foreground" />
                    <h1 className="text-2xl font-bold tracking-tight">Knowledge Query</h1>
                </div>
                <p className="text-muted-foreground text-sm">
                    Ask questions in natural language — the AI translates them into ontology search terms.
                </p>
            </div>

            {/* Search input */}
            <div className="mb-6">
                <div className="flex items-center gap-2 rounded-xl border bg-background p-2 shadow-sm transition-shadow focus-within:shadow-md focus-within:ring-1 focus-within:ring-ring/30">
                    <Search className="size-4 text-muted-foreground ml-2 shrink-0" />
                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask a question about your knowledge base…"
                        className="flex-1 bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
                        disabled={isLoading}
                    />
                    <Button
                        size="sm"
                        onClick={submitQuery}
                        disabled={!input.trim() || isLoading}
                        className="shrink-0"
                    >
                        {isLoading ? (
                            <Loader2 className="size-4 animate-spin" />
                        ) : (
                            <>
                                <Sparkles className="size-4" />
                                Search
                            </>
                        )}
                    </Button>
                </div>

                {/* Suggestions (only when empty) */}
                {isEmpty && (
                    <div className="flex flex-wrap gap-2 mt-3">
                        {suggestions.map((s) => (
                            <button
                                key={s}
                                onClick={() => {
                                    setInput(s);
                                    inputRef.current?.focus();
                                }}
                                className="rounded-full border bg-background px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* Error */}
            {error && (
                <Card className="mb-4 border-destructive/50 bg-destructive/5">
                    <CardContent className="flex items-center gap-2 py-3 text-sm text-destructive">
                        <AlertCircle className="size-4 shrink-0" />
                        {error}
                    </CardContent>
                </Card>
            )}

            {/* Empty state */}
            {isEmpty && !isLoading && (
                <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center">
                    <div className="flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5">
                        <Brain className="size-8 text-primary" />
                    </div>
                    <div className="space-y-1.5">
                        <h3 className="text-lg font-semibold">Ask anything</h3>
                        <p className="text-sm text-muted-foreground max-w-sm">
                            Your question will be translated into ontology terms to find relevant documents
                            in the knowledge base.
                        </p>
                    </div>
                </div>
            )}

            {/* Loading state */}
            {isLoading && (
                <div className="flex-1 flex flex-col items-center justify-center gap-3">
                    <Loader2 className="size-8 animate-spin text-primary" />
                    <p className="text-sm text-muted-foreground">Analyzing your question…</p>
                </div>
            )}

            {/* Results */}
            {result && !isLoading && (
                <div className="flex-1 overflow-y-auto space-y-4">
                    {/* Intent card */}
                    <IntentCard result={result} />

                    {/* Matches */}
                    <div className="space-y-2">
                        <h2 className="text-sm font-semibold text-muted-foreground flex items-center gap-1.5">
                            <FileText className="size-3.5" />
                            Results ({result.total_matches})
                        </h2>

                        {result.matches.length === 0 ? (
                            <Card>
                                <CardContent className="py-8 text-center text-sm text-muted-foreground">
                                    No matching documents found. Try rephrasing your question.
                                </CardContent>
                            </Card>
                        ) : (
                            result.matches.map((match) => (
                                <MatchCard
                                    key={match.file_id}
                                    match={match}
                                    onClick={() => navigate('/data-sources')}
                                />
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

/* ── Intent Card ─────────────────────────────────────────────────── */

function IntentCard({ result }: { result: QueryResult }) {
    const { intent } = result;

    return (
        <Card className="bg-gradient-to-r from-primary/5 via-background to-background border-primary/20">
            <CardContent className="py-4 space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                    <Brain className="size-4 text-primary" />
                    AI Interpretation
                </div>

                {/* Reasoning */}
                {intent.reasoning && (
                    <p className="text-sm text-muted-foreground">
                        {intent.reasoning}
                    </p>
                )}

                <div className="flex flex-wrap gap-4 text-xs">
                    {/* Concepts */}
                    {intent.concept_ids.length > 0 && (
                        <div className="flex items-center gap-1.5">
                            <Tag className="size-3 text-muted-foreground" />
                            <span className="text-muted-foreground">Concepts:</span>
                            {intent.concept_ids.map((id) => (
                                <Badge key={id} variant="secondary" className="text-xs">
                                    {id}
                                </Badge>
                            ))}
                        </div>
                    )}

                    {/* Keywords */}
                    {intent.keywords.length > 0 && (
                        <div className="flex items-center gap-1.5">
                            <Search className="size-3 text-muted-foreground" />
                            <span className="text-muted-foreground">Keywords:</span>
                            {intent.keywords.map((kw) => (
                                <Badge key={kw} variant="outline" className="text-xs">
                                    {kw}
                                </Badge>
                            ))}
                        </div>
                    )}

                    {/* Filters */}
                    {intent.metadata_filters.length > 0 && (
                        <div className="flex items-center gap-1.5">
                            <Filter className="size-3 text-muted-foreground" />
                            <span className="text-muted-foreground">Filters:</span>
                            {intent.metadata_filters.map((f, i) => (
                                <Badge key={i} variant="outline" className="text-xs">
                                    {f.field_name} {f.operator} "{f.value}"
                                </Badge>
                            ))}
                        </div>
                    )}

                    {/* Language */}
                    <div className="flex items-center gap-1.5">
                        <Languages className="size-3 text-muted-foreground" />
                        <span className="text-muted-foreground">Language:</span>
                        <span className="font-mono">{intent.resolved_language}</span>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

/* ── Match Card ──────────────────────────────────────────────────── */

function MatchCard({ match, onClick }: { match: QueryMatch; onClick: () => void }) {
    const confidencePct = Math.round(match.confidence * 100);

    return (
        <Card
            className="cursor-pointer transition-all hover:shadow-md hover:border-primary/30 group"
            onClick={onClick}
        >
            <CardContent className="py-3 flex items-center gap-4">
                {/* File icon */}
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted/60">
                    <FileText className="size-5 text-muted-foreground" />
                </div>

                {/* Main info */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                        <span className="font-medium text-sm truncate">
                            {match.filename}
                        </span>
                        {match.concept_id && (
                            <Badge variant="secondary" className="text-[10px] shrink-0">
                                {match.concept_id}
                            </Badge>
                        )}
                    </div>
                    {match.summary && (
                        <p className="text-xs text-muted-foreground line-clamp-2">
                            {match.summary}
                        </p>
                    )}
                </div>

                {/* Confidence + nav */}
                <div className="flex items-center gap-3 shrink-0">
                    {match.confidence > 0 && (
                        <div className="text-right">
                            <div className="text-xs font-mono font-medium">{confidencePct}%</div>
                            <div className="text-[10px] text-muted-foreground">confidence</div>
                        </div>
                    )}
                    <ArrowRight className="size-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
            </CardContent>
        </Card>
    );
}
