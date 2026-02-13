/** Standard health check response from the backend */
export interface HealthResponse {
    status: string;
    version: string;
    environment: string;
}

/** Standard API error response shape */
export interface ApiErrorResponse {
    detail: string;
}
