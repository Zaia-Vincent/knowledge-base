import { useEffect, useState } from 'react';
import { apiClient, ApiError } from '@/lib/api-client';
import type { HealthResponse } from '@/types/api.types';

interface UseHealthReturn {
    data: HealthResponse | null;
    isLoading: boolean;
    error: string | null;
    refetch: () => void;
}

export function useHealth(): UseHealthReturn {
    const [data, setData] = useState<HealthResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchHealth = async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await apiClient.get<HealthResponse>('/health');
            setData(response);
        } catch (err) {
            if (err instanceof ApiError) {
                setError(`Server error: ${err.status}`);
            } else {
                setError('Unable to connect to backend');
            }
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchHealth();
    }, []);

    return { data, isLoading, error, refetch: fetchHealth };
}
