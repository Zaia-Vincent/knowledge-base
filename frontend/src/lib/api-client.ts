const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

interface ApiRequestOptions extends Omit<RequestInit, 'body'> {
    body?: unknown;
}

class ApiError extends Error {
    status: number;
    statusText: string;
    data?: unknown;

    constructor(status: number, statusText: string, data?: unknown) {
        super(`API Error ${status}: ${statusText}`);
        this.name = 'ApiError';
        this.status = status;
        this.statusText = statusText;
        this.data = data;
    }
}

async function request<T>(endpoint: string, options: ApiRequestOptions = {}): Promise<T> {
    const { body, headers, ...rest } = options;

    const config: RequestInit = {
        headers: {
            'Content-Type': 'application/json',
            ...headers,
        },
        ...rest,
    };

    if (body) {
        config.body = JSON.stringify(body);
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

    if (!response.ok) {
        const data = await response.json().catch(() => undefined);
        throw new ApiError(response.status, response.statusText, data);
    }

    if (response.status === 204) {
        return undefined as T;
    }

    return response.json();
}

export const apiClient = {
    get: <T>(endpoint: string, options?: ApiRequestOptions) =>
        request<T>(endpoint, { ...options, method: 'GET' }),

    post: <T>(endpoint: string, body?: unknown, options?: ApiRequestOptions) =>
        request<T>(endpoint, { ...options, method: 'POST', body }),

    put: <T>(endpoint: string, body?: unknown, options?: ApiRequestOptions) =>
        request<T>(endpoint, { ...options, method: 'PUT', body }),

    patch: <T>(endpoint: string, body?: unknown, options?: ApiRequestOptions) =>
        request<T>(endpoint, { ...options, method: 'PATCH', body }),

    delete: <T>(endpoint: string, options?: ApiRequestOptions) =>
        request<T>(endpoint, { ...options, method: 'DELETE' }),
};

export { ApiError };
