import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { IncidentSearch } from '@/pages/IncidentSearch';
import { api } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  api: {
    getIncidents: vi.fn(),
    getRecentIncidents: vi.fn(),
    getExportUrl: vi.fn(),
    reviewIncident: vi.fn(),
  },
}));

describe('IncidentSearch - Test Run Isolation & Filter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.getIncidents as any).mockResolvedValue({
      items: [],
      count: 0,
      next_cursor: null,
      has_more: false,
    });
  });

  it('renders include_test checkbox defaulting to unchecked', async () => {
    render(
      <MemoryRouter>
        <IncidentSearch />
      </MemoryRouter>
    );

    const checkbox = screen.getByTestId('include-test-checkbox');
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).not.toBeChecked();

    // Default query called with include_test=false
    expect(api.getIncidents).toHaveBeenCalledWith(
      expect.objectContaining({
        include_test: false,
      })
    );
  });

  it('toggles include_test checkbox and passes include_test: true to search', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <IncidentSearch />
      </MemoryRouter>
    );

    const checkbox = screen.getByTestId('include-test-checkbox');
    await user.click(checkbox);
    expect(checkbox).toBeChecked();

    const searchBtn = screen.getByRole('button', { name: /Search Archive/i });
    await user.click(searchBtn);

    await waitFor(() => {
      expect(api.getIncidents).toHaveBeenCalledWith(
        expect.objectContaining({
          include_test: true,
        })
      );
    });
  });
});
