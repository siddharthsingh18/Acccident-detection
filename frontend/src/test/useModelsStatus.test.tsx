import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useModelsStatus } from '@/hooks/useModelsStatus';
import { api } from '@/lib/api';
import type { ModelsStatusResponse } from '@/lib/modelsContract';

vi.mock('@/lib/api', () => ({
  api: {
    getModelsStatus: vi.fn(),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useModelsStatus hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches and returns models status successfully', async () => {
    const mockStatus: ModelsStatusResponse = {
      policy: 'majority',
      degraded: false,
      scorers: [
        {
          name: 'vif_svm',
          available: true,
          version: '1.0.0',
          trained_on: 'Argus dataset',
          calibration_date: '2021-03-01',
          reason_unavailable: null,
        },
        {
          name: 'convae',
          available: true,
          version: '0.2.0-dota',
          trained_on: 'DoTA',
          calibration_date: null,
          reason_unavailable: null,
        },
      ],
    };

    vi.mocked(api.getModelsStatus).mockResolvedValueOnce(mockStatus);

    const { result } = renderHook(() => useModelsStatus(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isDegraded).toBe(false);
    expect(result.current.policy).toBe('majority');
    expect(result.current.scorers).toHaveLength(2);
    expect(result.current.modelsStatus).toEqual(mockStatus);
  });

  it('handles backend-unreachable / error state gracefully', async () => {
    vi.mocked(api.getModelsStatus).mockRejectedValueOnce(
      new Error('Failed to connect to backend')
    );

    const { result } = renderHook(() => useModelsStatus({ retry: false }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.modelsStatus).toBeNull();
    expect(result.current.isDegraded).toBe(false);
    expect(result.current.scorers).toEqual([]);
    expect(result.current.error?.message).toContain('Failed to connect');
  });
});
