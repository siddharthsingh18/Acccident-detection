import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Navbar } from '@/components/Navbar';
import { useModelsStatus } from '@/hooks/useModelsStatus';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('@/hooks/useModelsStatus');

vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => ({ theme: 'dark', toggleTheme: vi.fn() }),
}));

vi.mock('@/contexts/SoundContext', () => ({
  useSound: () => ({
    isSoundEnabled: true,
    volume: 0.8,
    toggleSound: vi.fn(),
    setVolume: vi.fn(),
  }),
}));

vi.mock('@/contexts/DemoContext', () => ({
  useDemo: () => ({
    isDemoMode: false,
    toggleDemoMode: vi.fn(),
  }),
}));

const mockUseModelsStatus = vi.mocked(useModelsStatus);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const renderNavbar = () => {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Navbar />
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('Navbar - Models Status Indicator and Popover', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "Models OK" state when all models are available and not degraded', () => {
    mockUseModelsStatus.mockReturnValue({
      modelsStatus: {
        policy: 'majority',
        degraded: false,
        scorers: [
          { name: 'vif_svm', available: true, version: '1.0.0', trained_on: 'legacy' },
          { name: 'convae', available: true, version: '0.9.0', trained_on: 'DoTA' },
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
      isDegraded: false,
      scorers: [
        { name: 'vif_svm', available: true, version: '1.0.0', trained_on: 'legacy' },
        { name: 'convae', available: true, version: '0.9.0', trained_on: 'DoTA' },
      ],
      policy: 'majority',
      refetch: vi.fn(),
    });

    renderNavbar();

    const button = screen.getByTestId('models-status-button');
    expect(button).toBeInTheDocument();
    expect(button).toHaveTextContent('Models OK');
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  it('renders "Degraded (legacy only)" when degraded: true', () => {
    mockUseModelsStatus.mockReturnValue({
      modelsStatus: {
        policy: 'majority',
        degraded: true,
        scorers: [
          { name: 'vif_svm', available: true, version: '1.0.0', trained_on: 'legacy' },
          { name: 'convae', available: false, version: '0.9.0', trained_on: 'DoTA', reason_unavailable: 'PyTorch not installed' },
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
      isDegraded: true,
      scorers: [
        { name: 'vif_svm', available: true, version: '1.0.0', trained_on: 'legacy' },
        { name: 'convae', available: false, version: '0.9.0', trained_on: 'DoTA', reason_unavailable: 'PyTorch not installed' },
      ],
      policy: 'majority',
      refetch: vi.fn(),
    });

    renderNavbar();

    const button = screen.getByTestId('models-status-button');
    expect(button).toHaveTextContent('Degraded (legacy only)');
  });

  it('renders "Models Offline" when status endpoint has error', () => {
    mockUseModelsStatus.mockReturnValue({
      modelsStatus: null,
      isLoading: false,
      isError: true,
      error: new Error('Network error'),
      isDegraded: false,
      scorers: [],
      policy: 'majority',
      refetch: vi.fn(),
    });

    renderNavbar();

    const button = screen.getByTestId('models-status-button');
    expect(button).toHaveTextContent('Models Offline');
  });

  it('toggles accessible popover with scorer details, policy explanation, and responds to keyboard escape', async () => {
    const user = userEvent.setup();
    mockUseModelsStatus.mockReturnValue({
      modelsStatus: {
        policy: 'majority',
        degraded: true,
        scorers: [
          { name: 'vif_svm', available: true, version: '1.0.0', trained_on: 'Argus baseline', calibration_date: '2026-10-15' },
          { name: 'convae', available: false, version: '0.9.0', trained_on: 'DoTA dataset', reason_unavailable: 'Torch extra not installed' },
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
      isDegraded: true,
      scorers: [
        { name: 'vif_svm', available: true, version: '1.0.0', trained_on: 'Argus baseline', calibration_date: '2026-10-15' },
        { name: 'convae', available: false, version: '0.9.0', trained_on: 'DoTA dataset', reason_unavailable: 'Torch extra not installed' },
      ],
      policy: 'majority',
      refetch: vi.fn(),
    });

    renderNavbar();

    const button = screen.getByTestId('models-status-button');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('models-status-popover')).not.toBeInTheDocument();

    // Click to open
    await user.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    const popover = screen.getByTestId('models-status-popover');
    expect(popover).toBeInTheDocument();

    // Contains policy explanation in plain language
    expect(screen.getByText('Majority of models flag -> alert')).toBeInTheDocument();

    // Lists scorers with details
    expect(screen.getByText('Violent Flows (VIF+SVM)')).toBeInTheDocument();
    expect(screen.getByText('ConvAE Spatio-Temporal')).toBeInTheDocument();
    expect(screen.getByText(/Torch extra not installed/i)).toBeInTheDocument();

    // Verification disclaimer present
    expect(screen.getByText(/Human verification required/i)).toBeInTheDocument();

    // Press Escape to close popover
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByTestId('models-status-popover')).not.toBeInTheDocument();
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });
  });
});
