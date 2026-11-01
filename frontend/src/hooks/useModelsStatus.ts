import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { ModelsStatusResponse } from '@/lib/modelsContract';

export interface UseModelsStatusOptions {
  retry?: boolean | number;
}

export function useModelsStatus(options?: UseModelsStatusOptions) {
  const query = useQuery<ModelsStatusResponse, Error>({
    queryKey: ['models', 'status'],
    queryFn: () => api.getModelsStatus(),
    refetchInterval: 30000,
    staleTime: 15000,
    ...(options?.retry !== undefined ? { retry: options.retry } : {}),
  });

  return {
    modelsStatus: query.data ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    isDegraded: query.data?.degraded ?? false,
    scorers: query.data?.scorers ?? [],
    policy: query.data?.policy ?? 'majority',
    refetch: query.refetch,
  };
}
