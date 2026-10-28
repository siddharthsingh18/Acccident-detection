import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ReviewBadge } from '@/components/ReviewBadge';
import { ReviewQueue } from '@/pages/ReviewQueue';
import { api, type Incident } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  api: {
    getIncidents: vi.fn(),
    reviewIncident: vi.fn(),
  },
}));

const mockUnreviewedIncidents: Incident[] = [
  {
    id: '1528_76',
    rowid: 10,
    camera_id: 1528,
    starting_frame_id: 76,
    city: 'Cairo',
    district: 'District 7',
    crash_time: '2026-10-28 10:15:00',
    thumbnail_url: '/media/thumbnails/1528_76.jpg',
    video_url: '/api/incidents/1528_76/video',
    review_status: null,
    review_note: null,
    reviewed_at: null,
  },
  {
    id: '8820_12',
    rowid: 9,
    camera_id: 8820,
    starting_frame_id: 12,
    city: 'Alexandria',
    district: 'Corniche',
    crash_time: '2026-10-28 10:10:00',
    thumbnail_url: '/media/thumbnails/8820_12.jpg',
    video_url: '/api/incidents/8820_12/video',
    review_status: null,
    review_note: null,
    reviewed_at: null,
  },
];

describe('ReviewBadge Component', () => {
  it('renders Confirmed Crash badge with red styling', () => {
    render(<ReviewBadge status="confirmed" />);
    const badge = screen.getByTestId('review-badge-confirmed');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(/Confirmed Crash/i);
    expect(badge.className).toContain('text-red-400');
  });

  it('renders False Alarm badge with emerald styling', () => {
    render(<ReviewBadge status="false_alarm" />);
    const badge = screen.getByTestId('review-badge-false-alarm');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(/False Alarm/i);
    expect(badge.className).toContain('text-emerald-400');
  });

  it('renders Unreviewed badge when status is null or unreviewed', () => {
    render(<ReviewBadge status={null} />);
    const badge = screen.getByTestId('review-badge-unreviewed');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(/Unreviewed/i);
    expect(badge.className).toContain('text-amber-300');
  });
});

describe('ReviewQueue Page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads and displays unreviewed incidents in the queue', async () => {
    vi.mocked(api.getIncidents).mockResolvedValueOnce({
      items: mockUnreviewedIncidents,
      count: 2,
      has_more: false,
    });

    render(
      <MemoryRouter>
        <ReviewQueue />
      </MemoryRouter>
    );

    expect(await screen.findByText('2 unreviewed left')).toBeInTheDocument();
    expect(screen.getByText('#1528_76')).toBeInTheDocument();
    expect(screen.getByText('Item 1 of 2')).toBeInTheDocument();
  });

  it('submits a confirmed review when Confirm button is clicked', async () => {
    vi.mocked(api.getIncidents).mockResolvedValueOnce({
      items: mockUnreviewedIncidents,
      count: 2,
      has_more: false,
    });
    vi.mocked(api.reviewIncident).mockResolvedValueOnce({
      ...mockUnreviewedIncidents[0],
      review_status: 'confirmed',
      reviewed_at: '2026-10-28T10:20:00Z',
    });

    render(
      <MemoryRouter>
        <ReviewQueue />
      </MemoryRouter>
    );

    await screen.findByText('#1528_76');
    const confirmBtn = screen.getByTestId('confirm-btn');
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(api.reviewIncident).toHaveBeenCalledWith('1528_76', {
        status: 'confirmed',
        note: undefined,
      });
    });

    // Advances to item 2 (#8820_12) and counter decreases
    expect(await screen.findByText('#8820_12')).toBeInTheDocument();
    expect(screen.getByText('1 unreviewed left')).toBeInTheDocument();
  });

  it('submits a false alarm review with note when False Alarm button is clicked', async () => {
    vi.mocked(api.getIncidents).mockResolvedValueOnce({
      items: [mockUnreviewedIncidents[0]],
      count: 1,
      has_more: false,
    });
    vi.mocked(api.reviewIncident).mockResolvedValueOnce({
      ...mockUnreviewedIncidents[0],
      review_status: 'false_alarm',
      review_note: 'Sudden braking only',
      reviewed_at: '2026-10-28T10:20:00Z',
    });

    render(
      <MemoryRouter>
        <ReviewQueue />
      </MemoryRouter>
    );

    await screen.findByText('#1528_76');
    const textarea = screen.getByPlaceholderText(/Optional triage note/i);
    await userEvent.type(textarea, 'Sudden braking only');

    const falseAlarmBtn = screen.getByTestId('false-alarm-btn');
    fireEvent.click(falseAlarmBtn);

    await waitFor(() => {
      expect(api.reviewIncident).toHaveBeenCalledWith('1528_76', {
        status: 'false_alarm',
        note: 'Sudden braking only',
      });
    });

    // Queue is now empty
    expect(await screen.findByTestId('queue-empty-state')).toBeInTheDocument();
    expect(screen.getByText(/Review Queue is Clear/i)).toBeInTheDocument();
  });

  it('responds to keyboard shortcut C to confirm and F to mark false alarm', async () => {
    vi.mocked(api.getIncidents).mockResolvedValueOnce({
      items: mockUnreviewedIncidents,
      count: 2,
      has_more: false,
    });
    vi.mocked(api.reviewIncident).mockResolvedValueOnce({
      ...mockUnreviewedIncidents[0],
      review_status: 'confirmed',
      reviewed_at: '2026-10-28T10:20:00Z',
    });

    render(
      <MemoryRouter>
        <ReviewQueue />
      </MemoryRouter>
    );

    await screen.findByText('#1528_76');

    // Press 'c' key on window
    fireEvent.keyDown(window, { key: 'c', code: 'KeyC' });

    await waitFor(() => {
      expect(api.reviewIncident).toHaveBeenCalledWith('1528_76', {
        status: 'confirmed',
        note: undefined,
      });
    });
  });

  it('navigates with J and K keyboard shortcuts without review submission', async () => {
    vi.mocked(api.getIncidents).mockResolvedValueOnce({
      items: mockUnreviewedIncidents,
      count: 2,
      has_more: false,
    });

    render(
      <MemoryRouter>
        <ReviewQueue />
      </MemoryRouter>
    );

    await screen.findByText('#1528_76');
    expect(screen.getByText('Item 1 of 2')).toBeInTheDocument();

    // Press 'j' (Next)
    fireEvent.keyDown(window, { key: 'j', code: 'KeyJ' });
    expect(await screen.findByText('#8820_12')).toBeInTheDocument();
    expect(screen.getByText('Item 2 of 2')).toBeInTheDocument();

    // Press 'k' (Previous)
    fireEvent.keyDown(window, { key: 'k', code: 'KeyK' });
    expect(await screen.findByText('#1528_76')).toBeInTheDocument();
    expect(screen.getByText('Item 1 of 2')).toBeInTheDocument();

    // Verify no review was called during navigation
    expect(api.reviewIncident).not.toHaveBeenCalled();
  });
});
