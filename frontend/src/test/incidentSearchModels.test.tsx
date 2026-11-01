import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { IncidentSearch } from '@/pages/IncidentSearch';
import { api, type Incident } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  api: {
    getIncidents: vi.fn(),
    getRecentIncidents: vi.fn(),
    getExportUrl: vi.fn().mockReturnValue('/api/incidents/export'),
  },
}));

const mockIncidents: Incident[] = [
  {
    id: 'inc_all_flagged',
    rowid: 1,
    camera_id: 101,
    starting_frame_id: 10,
    city: 'Cairo',
    district: 'Nasr City',
    crash_time: '2026-11-01 10:00:00',
    thumbnail_url: '/t1.jpg',
    video_url: '/v1.mp4',
    review_status: 'unreviewed',
    model_scores: {
      policy: 'majority',
      threshold: 0.5,
      decision: true,
      scorers: [
        { name: 'vif_svm', score: 0.9, fired: true, calibrated: true, available: true },
        { name: 'convae', score: 0.85, fired: true, calibrated: false, available: true },
      ],
    },
  },
  {
    id: 'inc_one_flagged',
    rowid: 2,
    camera_id: 102,
    starting_frame_id: 20,
    city: 'Alexandria',
    district: 'Montaza',
    crash_time: '2026-11-01 11:00:00',
    thumbnail_url: '/t2.jpg',
    video_url: '/v2.mp4',
    review_status: 'unreviewed',
    model_scores: {
      policy: 'any',
      threshold: 0.5,
      decision: true,
      scorers: [
        { name: 'vif_svm', score: 0.8, fired: true, calibrated: true, available: true },
        { name: 'convae', score: 0.2, fired: false, calibrated: false, available: true },
      ],
    },
  },
  {
    id: 'inc_null_scores',
    rowid: 3,
    camera_id: 103,
    starting_frame_id: 30,
    city: 'Gizah',
    district: 'Dokki',
    crash_time: '2026-11-01 12:00:00',
    thumbnail_url: '/t3.jpg',
    video_url: '/v3.mp4',
    review_status: 'confirmed',
    model_scores: null,
  },
];

describe('IncidentSearch - Models Agree Column and Filter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.getIncidents as any).mockResolvedValue({
      items: mockIncidents,
      total: mockIncidents.length,
      has_more: false,
      next_cursor: null,
    });
  });

  it('renders table headers including Models Agree and displays agreement badges or dashes', async () => {
    render(
      <MemoryRouter initialEntries={['/search']}>
        <IncidentSearch />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Models Agree')).toBeInTheDocument();
    });

    // Badge for inc_all_flagged: 2/2, inc_one_flagged: 1/2 (sorted by crash_time desc)
    const badges = screen.getAllByTestId('models-agree-badge');
    expect(badges.length).toBe(2);
    const badgeTexts = badges.map((b) => b.textContent?.trim());
    expect(badgeTexts).toContain('2/2');
    expect(badgeTexts).toContain('1/2');

    // Dash for inc_null_scores
    expect(screen.getByLabelText('No model data recorded')).toBeInTheDocument();
  });

  it('filters results client-side when "all_flagged" is selected and shows client-side filter note', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/search']}>
        <IncidentSearch />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Models Agree')).toBeInTheDocument();
    });

    const select = screen.getByTestId('models-agree-select');
    await user.selectOptions(select, 'all_flagged');

    const searchBtn = screen.getByRole('button', { name: /Search Archive/i });
    await user.click(searchBtn);

    await waitFor(() => {
      expect(screen.getByTestId('models-agree-filter-note')).toBeInTheDocument();
      expect(screen.getByTestId('models-agree-filter-note')).toHaveTextContent(
        'Client-side filter applied to loaded search records'
      );
    });

    // Only inc_all_flagged should be displayed
    expect(screen.getByText('#inc_all_flagged')).toBeInTheDocument();
    expect(screen.queryByText('#inc_one_flagged')).not.toBeInTheDocument();
    expect(screen.queryByText('#inc_null_scores')).not.toBeInTheDocument();
  });

  it('filters results client-side when "one_flagged" is selected', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/search']}>
        <IncidentSearch />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Models Agree')).toBeInTheDocument();
    });

    const select = screen.getByTestId('models-agree-select');
    await user.selectOptions(select, 'one_flagged');

    const searchBtn = screen.getByRole('button', { name: /Search Archive/i });
    await user.click(searchBtn);

    await waitFor(() => {
      expect(screen.getByTestId('models-agree-filter-note')).toBeInTheDocument();
      expect(screen.getByText('#inc_one_flagged')).toBeInTheDocument();
      expect(screen.queryByText('#inc_all_flagged')).not.toBeInTheDocument();
    });

    expect(screen.queryByText('#inc_null_scores')).not.toBeInTheDocument();
  });
});
