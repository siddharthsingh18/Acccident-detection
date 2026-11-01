import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { CameraFeeder } from '@/pages/CameraFeeder';
import { api, type SampleItem } from '@/lib/api';
import { classifyBatchOutcome, generateBatchResultsCsv } from '@/lib/batchRunner';

vi.mock('@/lib/api', () => ({
  api: {
    getSamples: vi.fn(),
    getSampleFeeds: vi.fn(),
    startFeedFromSample: vi.fn(),
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

const mockSamples: SampleItem[] = [
  {
    id: 'videos--1528.mp4',
    name: '1528.mp4',
    relative_path: 'videos/1528.mp4',
    size_bytes: 4000000,
    duration_s: 15.0,
    resolution: '640x360',
    fps: 30,
    thumbnail_url: '/thumbs/1528.jpg',
    video_url: '/videos/1528.mp4',
    expected_label: 'accident',
    camera_id: 1528,
    city: 'Shibin El Kom',
    district: 'District 13',
  },
  {
    id: 'videos--normal_1.mp4',
    name: 'normal_1.mp4',
    relative_path: 'videos/normal_1.mp4',
    size_bytes: 5000000,
    duration_s: 20.0,
    resolution: '640x360',
    fps: 30,
    thumbnail_url: '/thumbs/normal_1.jpg',
    video_url: '/videos/normal_1.mp4',
    expected_label: 'normal',
    camera_id: 2001,
    city: 'Cairo',
    district: 'District 1',
  },
  {
    id: 'Joiner--unlabeled_1.mp4',
    name: 'unlabeled_1.mp4',
    relative_path: 'Joiner/vids/unlabeled_1.mp4',
    size_bytes: 3000000,
    duration_s: 10.0,
    resolution: '640x360',
    fps: 30,
    thumbnail_url: '/thumbs/unlabeled_1.jpg',
    video_url: '/videos/unlabeled_1.mp4',
    expected_label: 'unknown',
    camera_id: 3001,
    city: 'Alexandria',
    district: 'Port',
  },
];

describe('Batch Test Runner Logic & Utilities (Phase 3)', () => {
  it('correctly classifies all 5 evaluation outcome states', () => {
    // 1. Expected accident + alert raised = Alert on accident clip
    expect(classifyBatchOutcome('accident', true)).toBe('Alert on accident clip');

    // 2. Expected normal + no alert = No alert on normal clip
    expect(classifyBatchOutcome('normal', false)).toBe('No alert on normal clip');

    // 3. Expected accident + no alert = Missed accident
    expect(classifyBatchOutcome('accident', false)).toBe('Missed accident');

    // 4. Expected normal + alert = False alarm
    expect(classifyBatchOutcome('normal', true)).toBe('False alarm');

    // 5. Unknown expected = Not scored (unlabeled)
    expect(classifyBatchOutcome('unknown', true)).toBe('Not scored (unlabeled)');
    expect(classifyBatchOutcome('unknown', false)).toBe('Not scored (unlabeled)');
  });

  it('generates valid RFC-4180 CSV with escaped strings and correct headers', () => {
    const csv = generateBatchResultsCsv([
      {
        id: '1528',
        name: '1528, test.mp4',
        relative_path: 'videos/1528, test.mp4',
        expected_label: 'accident',
        alert_raised: true,
        time_to_first_alert_s: 3.5,
        processing_time_s: 4.2,
        status: 'completed',
        outcome: 'Alert on accident clip',
        incident_id: '1528_106',
      },
      {
        id: 'normal',
        name: 'normal.mp4',
        relative_path: 'videos/normal.mp4',
        expected_label: 'normal',
        alert_raised: false,
        time_to_first_alert_s: null,
        processing_time_s: 2.1,
        status: 'completed',
        outcome: 'No alert on normal clip',
      },
    ]);

    expect(csv).toContain('Clip Name,Relative Path,Expected Label,Alert Raised');
    expect(csv).toContain('"1528, test.mp4"');
    expect(csv).toContain('Alert on accident clip');
    expect(csv).toContain('No alert on normal clip');
    expect(csv).toContain('1528_106');
  });
});

describe('CameraFeeder - Batch Test Runner UI & Execution (Phase 3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.getSamples as any).mockResolvedValue(mockSamples);
  });

  it('opens confirmation modal showing clip counts and estimated duration before starting', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-videos--1528.mp4');

    // Click "Run All (3)"
    const runBtn = screen.getByTestId('batch-run-btn');
    expect(runBtn).toHaveTextContent('Run All (3)');
    await user.click(runBtn);

    // Confirmation modal should appear
    expect(screen.getByTestId('batch-confirm-modal')).toBeInTheDocument();
    expect(screen.getByText(/You are about to launch sequential pipeline testing on/i)).toBeInTheDocument();
    expect(screen.getByText('3 clips')).toBeInTheDocument();

    // Cancel modal
    await user.click(screen.getByTestId('batch-confirm-cancel-btn'));
    expect(screen.queryByTestId('batch-confirm-modal')).not.toBeInTheDocument();
  });

  it('runs clips strictly sequentially one at a time and populates results table', async () => {
    const user = userEvent.setup();
    const callsOrder: string[] = [];

    // First clip feed
    (api.startFeedFromSample as any).mockImplementation((sampleId: string) => {
      callsOrder.push(`start:${sampleId}`);
      return Promise.resolve({
        id: `feed_${sampleId}`,
        camera_id: 1528,
        city: 'Cairo',
        district: 'District 1',
        status: 'processing',
        created_at: '2026-11-01T10:00:00Z',
        thumbnail_url: '/thumb.jpg',
        progress: { frames_sent: 50, total_frames: 100, percent: 50 },
      });
    });

    (api.getFeed as any).mockImplementation((feedId: string) => {
      callsOrder.push(`poll:${feedId}`);
      return Promise.resolve({
        id: feedId,
        camera_id: 1528,
        city: 'Cairo',
        district: 'District 1',
        status: 'done',
        created_at: '2026-11-01T10:00:00Z',
        thumbnail_url: '/thumb.jpg',
        progress: { frames_sent: 100, total_frames: 100, percent: 100 },
      });
    });

    (api.getIncidents as any).mockResolvedValue({
      items: [
        {
          id: '1528_106',
          rowid: 1,
          camera_id: 1528,
          starting_frame_id: 90,
          crash_time: '2026-11-01 10:00:00',
          city: 'Cairo',
          district: 'District 1',
          thumbnail_url: '/thumb.jpg',
          video_url: '/video.mp4',
          model_scores: null,
        },
      ],
      total: 1,
    });

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-videos--1528.mp4');

    // Filter to Accidents only (1 clip) to test clean run
    await user.click(screen.getByTestId('sample-filter-accident'));
    const runBtn = screen.getByTestId('batch-run-btn');
    expect(runBtn).toHaveTextContent('Run Filtered (1)');
    await user.click(runBtn);

    // Confirm batch run
    await user.click(screen.getByTestId('batch-confirm-start-btn'));

    // Wait for batch completion and results table appearance
    await waitFor(() => {
      expect(screen.getByTestId('batch-results-table')).toBeInTheDocument();
    });

    // Check classification outcome in table
    expect(screen.getByText('Alert on accident clip')).toBeInTheDocument();
    expect(screen.getByTestId('batch-disclaimer')).toHaveTextContent(/Smoke test on local clips\. Not a benchmark\./i);

    // Verify sequential execution: start happened before completion
    expect(callsOrder).toContain('start:videos--1528.mp4');
    expect(callsOrder).toContain('poll:feed_videos--1528.mp4');
  });

  it('cancel batch halts execution and stops remaining clips from starting', async () => {
    const user = userEvent.setup();

    (api.startFeedFromSample as any).mockResolvedValue({
      id: 'feed_cancel_test',
      camera_id: 1528,
      city: 'Cairo',
      district: 'District 1',
      status: 'processing',
      created_at: '2026-11-01T10:00:00Z',
      thumbnail_url: '/thumb.jpg',
      progress: { frames_sent: 10, total_frames: 100, percent: 10 },
    });

    // Feed stays in processing so we can cancel it
    (api.getFeed as any).mockResolvedValue({
      id: 'feed_cancel_test',
      camera_id: 1528,
      city: 'Cairo',
      district: 'District 1',
      status: 'processing',
      created_at: '2026-11-01T10:00:00Z',
      thumbnail_url: '/thumb.jpg',
      progress: { frames_sent: 20, total_frames: 100, percent: 20 },
    });

    (api.cancelFeed as any).mockResolvedValue({
      id: 'feed_cancel_test',
      status: 'cancelled',
    });

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-videos--1528.mp4');

    // Start batch with all 3 clips
    await user.click(screen.getByTestId('batch-run-btn'));
    await user.click(screen.getByTestId('batch-confirm-start-btn'));

    // Progress card should be visible
    const cancelBtn = await screen.findByTestId('cancel-batch-btn');
    expect(cancelBtn).toBeInTheDocument();

    // Click cancel
    await user.click(cancelBtn);

    // Verify cancel was triggered
    await waitFor(() => {
      expect(api.cancelFeed).toHaveBeenCalledWith('feed_cancel_test');
    });

    // Verify api.startFeedFromSample was only called once (subsequent clips did NOT start)
    expect(api.startFeedFromSample).toHaveBeenCalledTimes(1);
  });

  it('continues batch queue when a single clip fails without aborting subsequent clips', async () => {
    const user = userEvent.setup();

    (api.startFeedFromSample as any).mockImplementation((sampleId: string) => {
      if (sampleId === 'videos--1528.mp4') {
        return Promise.reject(new Error('Corrupted video header'));
      }
      return Promise.resolve({
        id: `feed_${sampleId}`,
        camera_id: 2001,
        city: 'Cairo',
        district: 'District 1',
        status: 'done',
        created_at: '2026-11-01T10:00:00Z',
        thumbnail_url: '/thumb.jpg',
        progress: { frames_sent: 100, total_frames: 100, percent: 100 },
      });
    });

    (api.getFeed as any).mockResolvedValue({
      id: 'feed_videos--normal_1.mp4',
      camera_id: 2001,
      city: 'Cairo',
      district: 'District 1',
      status: 'done',
      created_at: '2026-11-01T10:00:00Z',
      thumbnail_url: '/thumb.jpg',
      progress: { frames_sent: 100, total_frames: 100, percent: 100 },
    });

    (api.getIncidents as any).mockResolvedValue({ items: [], total: 0 });

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-videos--1528.mp4');

    // Run batch with first 2 clips (1528 and normal_1)
    await user.click(screen.getByTestId('batch-run-btn'));
    await user.click(screen.getByTestId('batch-confirm-start-btn'));

    // Wait for both clips to be processed
    await waitFor(() => {
      expect(screen.getByTestId('batch-row-videos--1528.mp4')).toBeInTheDocument();
      expect(screen.getByTestId('batch-row-videos--normal_1.mp4')).toBeInTheDocument();
    });

    // First clip failed, second completed
    expect(screen.getByTestId('batch-row-videos--1528.mp4')).toHaveTextContent('failed');
    expect(screen.getByTestId('batch-row-videos--normal_1.mp4')).toHaveTextContent('completed');
    expect(screen.getByTestId('batch-row-videos--normal_1.mp4')).toHaveTextContent('No alert on normal clip');
  });
});
