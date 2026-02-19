/**
 * API client for application settings.
 * Talks to the /api/v1/settings endpoint.
 */

import { apiClient } from './api-client';

const BASE = '/settings';

export interface ModelSettings {
    models: Record<string, string>;
    labels: Record<string, string>;
}

export interface AvailableModel {
    id: string;
    name: string;
}

export const settingsApi = {
    /** Get current model settings. */
    getModelSettings(): Promise<ModelSettings> {
        return apiClient.get<ModelSettings>(`${BASE}/models`);
    },

    /** Update model settings. */
    updateModelSettings(models: Record<string, string>): Promise<ModelSettings> {
        return apiClient.put<ModelSettings>(`${BASE}/models`, { models });
    },

    /** Fetch all available OpenRouter models. */
    getAvailableModels(): Promise<AvailableModel[]> {
        return apiClient.get<AvailableModel[]>(`${BASE}/available-models`);
    },
};
