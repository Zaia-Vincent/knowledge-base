/**
 * Chat Completion API client with SSE streaming support.
 */

import { apiClient } from '@/lib/api-client';

// ── Types ──

export interface ChatMessage {
    role: 'system' | 'user' | 'assistant';
    content: string;
}

export interface ChatCompletionRequest {
    model: string;
    messages: ChatMessage[];
    temperature?: number;
    max_tokens?: number;
    stream?: boolean;
}

export interface TokenUsage {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost: number | null;
}

export interface ChatCompletionResponse {
    model: string;
    content: string;
    finish_reason: string;
    usage: TokenUsage;
    provider: string;
    images: Record<string, string>[];
}

// ── Non-streaming ──

export async function chatCompletion(
    request: ChatCompletionRequest,
): Promise<ChatCompletionResponse> {
    return apiClient.post<ChatCompletionResponse>('/chat/completions', {
        ...request,
        stream: false,
    });
}

// ── Streaming (SSE) ──

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

/**
 * Stream a chat completion via Server-Sent Events.
 * Calls `onChunk` for each content delta received.
 * Returns the full accumulated text when the stream ends.
 */
export async function chatCompletionStream(
    request: ChatCompletionRequest,
    {
        onChunk,
        onError,
        signal,
    }: {
        onChunk: (delta: string) => void;
        onError?: (error: string) => void;
        signal?: AbortSignal;
    },
): Promise<string> {
    const response = await fetch(`${API_BASE_URL}/chat/completions/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...request, stream: true }),
        signal,
    });

    if (!response.ok) {
        const text = await response.text();
        throw new Error(`Chat stream failed (${response.status}): ${text}`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let accumulated = '';
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE lines
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? ''; // keep incomplete line in buffer

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith('data:')) continue;

            const jsonStr = trimmed.slice(5).trim();
            if (jsonStr === '[DONE]') continue;

            try {
                const data = JSON.parse(jsonStr);

                // Check for error events
                if (data.error) {
                    onError?.(data.error.message ?? 'Unknown error');
                    continue;
                }

                // OpenAI-compatible delta format
                const delta =
                    data.choices?.[0]?.delta?.content ??
                    data.choices?.[0]?.text ??
                    '';

                if (delta) {
                    accumulated += delta;
                    onChunk(delta);
                }
            } catch {
                // Skip non-JSON lines
            }
        }
    }

    return accumulated;
}
