/**
 * ModelSettingsPage — Configure LLM models per processing type.
 *
 * Features:
 *   • Searchable dropdown (combobox) for each processing type
 *   • Live fetch of available models from OpenRouter
 *   • Immediate save with feedback
 */

import { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import {
    Loader2,
    Save,
    CheckCircle2,
    AlertCircle,
    Search,
    ChevronDown,
    Cpu,
    ArrowLeft,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { settingsApi, type AvailableModel } from '@/lib/settings-api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

/* ── Page ─────────────────────────────────────────────────────────── */

export function ModelSettingsPage() {
    const [models, setModels] = useState<Record<string, string>>({});
    const [labels, setLabels] = useState<Record<string, string>>({});
    const [available, setAvailable] = useState<AvailableModel[]>([]);
    const [loadingSettings, setLoadingSettings] = useState(true);
    const [loadingModels, setLoadingModels] = useState(true);
    const [saving, setSaving] = useState(false);
    const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
    const [dirty, setDirty] = useState(false);

    // Fetch current settings
    useEffect(() => {
        (async () => {
            try {
                const data = await settingsApi.getModelSettings();
                setModels(data.models);
                setLabels(data.labels);
            } catch (err) {
                setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Failed to load settings' });
            } finally {
                setLoadingSettings(false);
            }
        })();
    }, []);

    // Fetch available models
    useEffect(() => {
        (async () => {
            try {
                const data = await settingsApi.getAvailableModels();
                setAvailable(data);
            } catch (err) {
                console.error('Failed to load available models:', err);
            } finally {
                setLoadingModels(false);
            }
        })();
    }, []);

    const handleModelChange = useCallback((key: string, value: string) => {
        setModels((prev) => ({ ...prev, [key]: value }));
        setDirty(true);
        setFeedback(null);
    }, []);

    const handleSave = useCallback(async () => {
        setSaving(true);
        setFeedback(null);
        try {
            const data = await settingsApi.updateModelSettings(models);
            setModels(data.models);
            setDirty(false);
            setFeedback({ type: 'success', message: 'Settings saved successfully' });
        } catch (err) {
            setFeedback({ type: 'error', message: err instanceof Error ? err.message : 'Save failed' });
        } finally {
            setSaving(false);
        }
    }, [models]);

    const isLoading = loadingSettings || loadingModels;

    return (
        <div className="space-y-6 max-w-3xl">
            {/* Header */}
            <div className="space-y-1">
                <div className="flex items-center gap-2">
                    <Link to="/setup" className="p-1 rounded-md hover:bg-accent transition-colors">
                        <ArrowLeft className="size-4 text-muted-foreground" />
                    </Link>
                    <Cpu className="size-5 text-muted-foreground" />
                    <h1 className="text-2xl font-bold tracking-tight">LLM Models</h1>
                </div>
                <p className="text-muted-foreground text-sm ml-8">
                    Configure which OpenRouter model to use for each processing type.
                </p>
            </div>

            {/* Loading */}
            {isLoading && (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="size-8 animate-spin text-primary" />
                </div>
            )}

            {/* Model selectors */}
            {!isLoading && (
                <div className="space-y-4">
                    {Object.entries(labels).map(([key, label]) => (
                        <ModelSelector
                            key={key}
                            settingKey={key}
                            label={label}
                            value={models[key] ?? ''}
                            available={available}
                            onChange={(v) => handleModelChange(key, v)}
                        />
                    ))}
                </div>
            )}

            {/* Feedback */}
            {feedback && (
                <div
                    className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm ${feedback.type === 'success'
                        ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-600'
                        : 'border-destructive/30 bg-destructive/5 text-destructive'
                        }`}
                >
                    {feedback.type === 'success' ? (
                        <CheckCircle2 className="size-4 shrink-0" />
                    ) : (
                        <AlertCircle className="size-4 shrink-0" />
                    )}
                    {feedback.message}
                </div>
            )}

            {/* Save */}
            {!isLoading && (
                <div className="flex justify-end">
                    <Button onClick={handleSave} disabled={!dirty || saving} className="gap-2">
                        {saving ? (
                            <Loader2 className="size-4 animate-spin" />
                        ) : (
                            <Save className="size-4" />
                        )}
                        Save changes
                    </Button>
                </div>
            )}
        </div>
    );
}

/* ── Model Selector (searchable combobox) ────────────────────────── */

function ModelSelector({
    settingKey,
    label,
    value,
    available,
    onChange,
}: {
    settingKey: string;
    label: string;
    value: string;
    available: AvailableModel[];
    onChange: (value: string) => void;
}) {
    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState('');
    const containerRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Close on outside click
    useEffect(() => {
        if (!open) return;
        const handler = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [open]);

    const filtered = useMemo(() => {
        if (!search) return available;
        const q = search.toLowerCase();
        return available.filter(
            (m) => m.id.toLowerCase().includes(q) || m.name.toLowerCase().includes(q)
        );
    }, [available, search]);

    const selectedModel = available.find((m) => m.id === value);
    const displayName = selectedModel?.name ?? value;

    return (
        <Card>
            <CardHeader className="py-3 px-4">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-semibold">{label}</CardTitle>
                    <Badge variant="outline" className="text-[10px] font-mono">
                        {settingKey}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="px-4 pb-4">
                <div ref={containerRef} className="relative">
                    {/* Trigger */}
                    <button
                        type="button"
                        className="flex w-full items-center justify-between rounded-lg border bg-background px-3 py-2 text-sm hover:bg-accent/50 transition-colors"
                        onClick={() => {
                            setOpen(!open);
                            if (!open) {
                                setSearch('');
                                setTimeout(() => inputRef.current?.focus(), 50);
                            }
                        }}
                    >
                        <span className="truncate text-left">{displayName || 'Select a model…'}</span>
                        <ChevronDown className={`size-4 shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
                    </button>

                    {/* Dropdown */}
                    {open && (
                        <div className="absolute z-50 mt-1 w-full rounded-lg border bg-popover shadow-lg">
                            {/* Search input */}
                            <div className="relative p-2 border-b">
                                <Search className="absolute left-4 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
                                <input
                                    ref={inputRef}
                                    type="text"
                                    value={search}
                                    onChange={(e) => setSearch(e.target.value)}
                                    placeholder="Search models…"
                                    className="w-full rounded-md border bg-background pl-7 pr-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring/30"
                                />
                            </div>

                            {/* Options */}
                            <div className="max-h-60 overflow-y-auto p-1">
                                {filtered.length === 0 && (
                                    <div className="px-3 py-2 text-sm text-muted-foreground">No models found</div>
                                )}
                                {filtered.map((m) => (
                                    <button
                                        key={m.id}
                                        type="button"
                                        className={`flex w-full items-start gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent/60 ${m.id === value ? 'bg-accent/40 font-medium' : ''
                                            }`}
                                        onClick={() => {
                                            onChange(m.id);
                                            setOpen(false);
                                        }}
                                    >
                                        <div className="flex-1 min-w-0">
                                            <div className="truncate">{m.name}</div>
                                            <div className="text-[11px] text-muted-foreground truncate font-mono">{m.id}</div>
                                        </div>
                                        {m.id === value && (
                                            <CheckCircle2 className="size-4 text-primary shrink-0 mt-0.5" />
                                        )}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
