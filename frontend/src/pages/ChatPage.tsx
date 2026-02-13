import { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, Send, Trash2, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
    chatCompletionStream,
    type ChatMessage,
} from '@/lib/chat-api';

const DEFAULT_MODEL = 'openai/gpt-4o-mini';

const SYSTEM_MESSAGE: ChatMessage = {
    role: 'system',
    content:
        'You are a helpful assistant for a Knowledge Base application. ' +
        'Answer clearly and concisely. Use markdown formatting when useful.',
};

interface DisplayMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    isStreaming?: boolean;
}

function generateId() {
    return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

// ── Markdown-lite renderer ──
// Supports **bold**, *italic*, `code`, ```code blocks```, and line breaks.
function MessageContent({ content }: { content: string }) {
    const parts = content.split(/(```[\s\S]*?```|`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);

    return (
        <div className="whitespace-pre-wrap break-words leading-relaxed">
            {parts.map((part, i) => {
                if (part.startsWith('```') && part.endsWith('```')) {
                    const code = part.slice(3, -3).replace(/^\w+\n/, '');
                    return (
                        <pre
                            key={i}
                            className="my-2 overflow-x-auto rounded-lg bg-muted/70 p-3 text-xs font-mono"
                        >
                            <code>{code}</code>
                        </pre>
                    );
                }
                if (part.startsWith('`') && part.endsWith('`')) {
                    return (
                        <code
                            key={i}
                            className="rounded bg-muted/70 px-1.5 py-0.5 text-xs font-mono"
                        >
                            {part.slice(1, -1)}
                        </code>
                    );
                }
                if (part.startsWith('**') && part.endsWith('**')) {
                    return <strong key={i}>{part.slice(2, -2)}</strong>;
                }
                if (part.startsWith('*') && part.endsWith('*')) {
                    return <em key={i}>{part.slice(1, -1)}</em>;
                }
                return <span key={i}>{part}</span>;
            })}
        </div>
    );
}

function ChatBubble({ message }: { message: DisplayMessage }) {
    const isUser = message.role === 'user';

    return (
        <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            <div
                className={`flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${isUser
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground'
                    }`}
            >
                {isUser ? 'U' : <Bot className="size-4" />}
            </div>

            {/* Bubble */}
            <div
                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${isUser
                        ? 'bg-primary text-primary-foreground rounded-br-md'
                        : 'bg-muted/60 text-foreground rounded-bl-md'
                    }`}
            >
                <MessageContent content={message.content} />
                {message.isStreaming && (
                    <span className="inline-block ml-1 size-2 animate-pulse rounded-full bg-current opacity-70" />
                )}
            </div>
        </div>
    );
}

export function ChatPage() {
    const [messages, setMessages] = useState<DisplayMessage[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const abortRef = useRef<AbortController | null>(null);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, []);

    useEffect(() => {
        scrollToBottom();
    }, [messages, scrollToBottom]);

    // Auto-resize textarea
    const handleInputChange = useCallback(
        (e: React.ChangeEvent<HTMLTextAreaElement>) => {
            setInput(e.target.value);
            e.target.style.height = 'auto';
            e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
        },
        [],
    );

    const sendMessage = useCallback(async () => {
        const trimmed = input.trim();
        if (!trimmed || isLoading) return;

        setError(null);
        setInput('');
        if (inputRef.current) inputRef.current.style.height = 'auto';

        // Add user message
        const userMsg: DisplayMessage = {
            id: generateId(),
            role: 'user',
            content: trimmed,
        };

        // Add placeholder for assistant
        const assistantMsg: DisplayMessage = {
            id: generateId(),
            role: 'assistant',
            content: '',
            isStreaming: true,
        };

        setMessages((prev) => [...prev, userMsg, assistantMsg]);
        setIsLoading(true);

        // Build API messages
        const apiMessages: ChatMessage[] = [
            SYSTEM_MESSAGE,
            ...messages.map((m) => ({
                role: m.role as 'user' | 'assistant',
                content: m.content,
            })),
            { role: 'user' as const, content: trimmed },
        ];

        const controller = new AbortController();
        abortRef.current = controller;

        try {
            await chatCompletionStream(
                {
                    model: DEFAULT_MODEL,
                    messages: apiMessages,
                    temperature: 0.7,
                },
                {
                    onChunk: (delta) => {
                        setMessages((prev) =>
                            prev.map((m) =>
                                m.id === assistantMsg.id
                                    ? { ...m, content: m.content + delta }
                                    : m,
                            ),
                        );
                    },
                    onError: (errMsg) => {
                        setError(errMsg);
                    },
                    signal: controller.signal,
                },
            );
        } catch (err) {
            if ((err as Error).name !== 'AbortError') {
                setError((err as Error).message);
            }
        } finally {
            // Mark streaming done
            setMessages((prev) =>
                prev.map((m) =>
                    m.id === assistantMsg.id
                        ? { ...m, isStreaming: false }
                        : m,
                ),
            );
            setIsLoading(false);
            abortRef.current = null;
        }
    }, [input, isLoading, messages]);

    const handleKeyDown = useCallback(
        (e: React.KeyboardEvent) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        },
        [sendMessage],
    );

    const clearChat = useCallback(() => {
        abortRef.current?.abort();
        setMessages([]);
        setError(null);
        setIsLoading(false);
    }, []);

    const isEmpty = messages.length === 0;

    return (
        <div className="flex h-full flex-col max-w-4xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between pb-4">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <Bot className="size-5 text-muted-foreground" />
                        <h1 className="text-2xl font-bold tracking-tight">Chat</h1>
                    </div>
                    <p className="text-muted-foreground text-sm">
                        Talk to an AI assistant powered by your configured model.
                    </p>
                </div>
                {!isEmpty && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={clearChat}
                    >
                        <Trash2 className="size-3.5" />
                        Clear
                    </Button>
                )}
            </div>

            {/* Messages area */}
            <div className="flex-1 overflow-y-auto rounded-xl border bg-card/50 p-4 space-y-4">
                {isEmpty && (
                    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
                        <div className="flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5">
                            <Bot className="size-8 text-primary" />
                        </div>
                        <div className="space-y-1.5">
                            <h3 className="text-lg font-semibold">How can I help you?</h3>
                            <p className="text-sm text-muted-foreground max-w-sm">
                                Ask anything — I can help with your knowledge base, answer questions,
                                or assist with tasks.
                            </p>
                        </div>
                        <div className="flex flex-wrap justify-center gap-2 mt-2">
                            {[
                                'Summarize a topic for me',
                                'Help me draft an article',
                                'Explain a concept',
                            ].map((suggestion) => (
                                <button
                                    key={suggestion}
                                    onClick={() => {
                                        setInput(suggestion);
                                        inputRef.current?.focus();
                                    }}
                                    className="rounded-full border bg-background px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                                >
                                    {suggestion}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg) => (
                    <ChatBubble key={msg.id} message={msg} />
                ))}

                {/* Error */}
                {error && (
                    <Card className="border-destructive/50 bg-destructive/5">
                        <CardContent className="flex items-center gap-2 py-3 text-sm text-destructive">
                            <AlertCircle className="size-4 shrink-0" />
                            {error}
                        </CardContent>
                    </Card>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className="pt-4">
                <div className="flex items-end gap-2 rounded-xl border bg-background p-2 shadow-sm transition-shadow focus-within:shadow-md focus-within:ring-1 focus-within:ring-ring/30">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={handleInputChange}
                        onKeyDown={handleKeyDown}
                        placeholder="Type a message… (Shift+Enter for new line)"
                        rows={1}
                        className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
                        disabled={isLoading}
                    />
                    <Button
                        size="sm"
                        onClick={sendMessage}
                        disabled={!input.trim() || isLoading}
                        className="shrink-0"
                    >
                        {isLoading ? (
                            <Loader2 className="size-4 animate-spin" />
                        ) : (
                            <Send className="size-4" />
                        )}
                    </Button>
                </div>
                <p className="mt-1.5 text-center text-xs text-muted-foreground">
                    Model: <span className="font-mono">{DEFAULT_MODEL}</span>
                </p>
            </div>
        </div>
    );
}
