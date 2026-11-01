import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { CameraFeeder } from '@/pages/CameraFeeder';
import { api, type FeedResponse, type Incident } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  api: {
    getSampleFeeds: vi.fn(),
    startSampleFeed: vi.fn(),
    createFeed: vi.fn(),
    getFeed: vi.fn(),
    cancelFeed: vi.fn(),
    getIncidents: vi.fn(),
  },
}));

vi.mock('@/contexts/SoundContext', () => ({
  useSound: () => ({
    playSiren: vi.fn(),
  }),
}));

vi.mock('@/hooks/useAlertSocket', () => ({
  useAlertSocket: () => ({
    latestAlert: null,
  }),
}));

describe('CameraFeeder - Detected Event Timeline & Model Comparison', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.getSampleFeeds as any).mockResolvedValue([
      {
        id: 'sample1',
        filename: 'sample1.mp4',
        camera_id: 1528,
        city: 'Cairo',
        district: 'District 1',
        label: 'Sample 1',
        description: 'Test',
        has_accident: true,
        incident_id: '1528_76',
        video_url: '/samples/sample1.mp4',
        output_video_url: '/samples/sample1_out.mp4',
      },
    ]);
  });

  it('renders event timeline with telemetry, model breakdown, compare toggle, and trajectory notice on accident', async () => {
    const user = userEvent.setup();

    const mockIncident: Incident = {
      id: '1528_76',
      rowid: 1,
      camera_id: 1528,
      starting_frame_id: 76,
      crash_time: '2026-11-01 10:15:00',
      city: 'Cairo',
      district: 'District 1',
      thumbnail_url: '/thumb.jpg',
      video_url: '/video.mp4',
      review_status: 'unreviewed',
      model_scores: {
        policy: 'majority',
        threshold: 0.5,
        decision: true,
        scorers: [
          { name: 'vif_svm', score: 0.88, fired: true, calibrated: true, available: true },
          { name: 'convae', score: 0.75, fired: true, calibrated: false, available: true },
        ],
      },
    };

    const feedDone: FeedResponse = {
      id: 'feed_1',
      camera_id: 1528,
      city: 'Cairo',
      district: 'District 1',
      status: 'done',
      thumbnail_url: '/thumb.jpg',
      progress: { frames_sent: 100, total_frames: 100, percent: 100 },
      created_at: '2026-11-01T10:00:00Z',
      degraded: false,
    };

    (api.startSampleFeed as any).mockResolvedValue(feedDone);
    (api.getFeed as any).mockResolvedValue(feedDone);
    (api.getIncidents as any).mockResolvedValue({
      items: [mockIncident],
      total: 1,
      has_more: false,
      next_cursor: null,
    });

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    const runBtn = await screen.findByRole('button', { name: /Start Accident Detection Pipeline/i });
    await user.click(runBtn);

    // Event timeline section renders
    const timeline = await screen.findByTestId('events-timeline-section');
    expect(timeline).toBeInTheDocument();
    expect(screen.getByText(/Detected Event Timeline \(1 Event\)/i)).toBeInTheDocument();

    // Event telemetry displayed
    expect(screen.getByText('#1528_76')).toBeInTheDocument();
    expect(screen.getByText('Frame 76')).toBeInTheDocument();

    // Trajectory notice displayed
    const notice = screen.getByTestId('trajectory-scores-notice');
    expect(notice).toHaveTextContent('Per-frame trajectory scores not available for legacy pipeline runs');

    // Compare models button toggle
    const compareBtn = screen.getByTestId('compare-models-toggle');
    expect(compareBtn).toBeInTheDocument();

    // Initially side-by-side is not shown
    expect(screen.queryByTestId('models-side-by-side')).not.toBeInTheDocument();

    // Toggle compare
    await user.click(compareBtn);
    expect(screen.getByTestId('models-side-by-side')).toBeInTheDocument();
    expect(screen.getByTestId('compare-card-vif_svm')).toBeInTheDocument();
    expect(screen.getByTestId('compare-card-convae')).toBeInTheDocument();
  });

  it('renders timeline empty state and trajectory notice when 0 collision events detected', async () => {
    const user = userEvent.setup();

    // Normal traffic sample
    (api.getSampleFeeds as any).mockResolvedValue([
      {
        id: 'sample_normal',
        filename: 'normal.mp4',
        camera_id: 2001,
        city: 'Alexandria',
        district: 'Corniche',
        label: 'Normal Flow',
        description: 'No accidents',
        has_accident: false,
        incident_id: null,
        video_url: '/samples/normal.mp4',
        output_video_url: null,
      },
    ]);

    const feedDone: FeedResponse = {
      id: 'feed_2',
      camera_id: 2001,
      city: 'Alexandria',
      district: 'Corniche',
      status: 'done',
      thumbnail_url: '/thumb.jpg',
      progress: { frames_sent: 100, total_frames: 100, percent: 100 },
      created_at: '2026-11-01T10:00:00Z',
      degraded: false,
    };

    (api.startSampleFeed as any).mockResolvedValue(feedDone);
    (api.getFeed as any).mockResolvedValue(feedDone);
    (api.getIncidents as any).mockResolvedValue({
      items: [],
      total: 0,
      has_more: false,
      next_cursor: null,
    });

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    const runBtn = await screen.findByRole('button', { name: /Start Accident Detection Pipeline/i });
    await user.click(runBtn);

    await waitFor(() => {
      expect(screen.getByTestId('timeline-empty')).toBeInTheDocument();
    });

    expect(screen.getByText(/0 Events/i)).toBeInTheDocument();
    expect(screen.getByTestId('trajectory-scores-notice')).toBeInTheDocument();
  });
});
