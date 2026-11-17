import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { CameraFeeder } from '@/pages/CameraFeeder';
import { api, type SampleItem, type FeedResponse } from '@/lib/api';
import { generateBatchResultsCsv } from '@/lib/batchRunner';

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
    getIncident: vi.fn(),
    getRunTrace: vi.fn(),
    getActiveConfig: vi.fn(),
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
    id: 'sample-box',
    name: 'sample_with_box.mp4',
    relative_path: 'videos/sample_with_box.mp4',
    size_bytes: 3000000,
    duration_s: 10.0,
    resolution: '640x360',
    fps: 30,
    thumbnail_url: '/thumbs/1.jpg',
    video_url: '/videos/1.mp4',
    expected_label: 'normal',
    camera_id: 1528,
    has_box_file: true,
    detection_quality: 'reference',
  },
  {
    id: 'sample-nobox',
    name: 'sample_no_box.mp4',
    relative_path: 'videos/sample_no_box.mp4',
    size_bytes: 3000000,
    duration_s: 10.0,
    resolution: '640x360',
    fps: 30,
    thumbnail_url: '/thumbs/2.jpg',
    video_url: '/videos/2.mp4',
    expected_label: 'normal',
    camera_id: 10,
    has_box_file: false,
    detection_quality: 'motion_fallback',
  },
];

describe('Phase 1: Detection Quality Outcome Presentation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.getSamples as any).mockResolvedValue(mockSamples);
    (api.getActiveConfig as any).mockResolvedValue({
      detector: 'legacy',
      trace_enabled: false,
    });
    (api.getIncidents as any).mockResolvedValue({ items: [], total: 0 });
    (api.getRunTrace as any).mockResolvedValue({ has_trace: false, summary: null });
  });

  it('renders amber warning for motion_fallback and never displays plain Normal or 0 anomalies', async () => {
    const user = userEvent.setup();
    const mockFeed: FeedResponse = {
      id: 'feed-degraded-1',
      camera_id: 10,
      city: 'Cairo',
      district: 'District 1',
      status: 'done',
      thumbnail_url: '/thumb.jpg',
      created_at: '2026-11-01T10:00:00Z',
      progress: { frames_sent: 50, total_frames: 50, percent: 100 },
      anomalies_detected: 0,
      detection_quality: 'motion_fallback',
      detector_name: 'MotionFallbackDetector',
      vehicles_detected_count: 2,
    };

    (api.startFeedFromSample as any).mockResolvedValue(mockFeed);
    (api.getFeed as any).mockResolvedValue(mockFeed);

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    // Select sample without box file
    await screen.findByTestId('sample-card-sample-nobox');
    await user.click(screen.getByTestId('sample-card-sample-nobox'));

    // Start pipeline
    const runBtn = screen.getByTestId('start-pipeline-btn');
    await user.click(runBtn);

    // Verify warning rendered with amber styling & exact required text
    await waitFor(() => {
      const warning = screen.getByTestId('outcome-low-quality-warning');
      expect(warning).toBeInTheDocument();
      expect(warning).toHaveTextContent('No alert, but detection was low quality. This result is not reliable.');
    });

    // Verify clean emerald Normal is NOT displayed
    expect(screen.queryByTestId('outcome-clean-normal')).not.toBeInTheDocument();
    expect(screen.queryByText('Normal Traffic - No Accident')).not.toBeInTheDocument();

    // Verify top status badge shows low quality indicator
    expect(screen.getByText('LOW QUALITY (UNRELIABLE)')).toBeInTheDocument();
  });

  it('renders amber warning for unavailable quality', async () => {
    const user = userEvent.setup();
    const mockFeed: FeedResponse = {
      id: 'feed-unavail-1',
      camera_id: 10,
      city: 'Cairo',
      district: 'District 1',
      status: 'done',
      thumbnail_url: '/thumb.jpg',
      created_at: '2026-11-01T10:00:00Z',
      progress: { frames_sent: 50, total_frames: 50, percent: 100 },
      anomalies_detected: 0,
      detection_quality: 'unavailable',
      vehicles_detected_count: 3,
    };

    (api.startFeedFromSample as any).mockResolvedValue(mockFeed);
    (api.getFeed as any).mockResolvedValue(mockFeed);

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-sample-nobox');
    await user.click(screen.getByTestId('sample-card-sample-nobox'));
    await user.click(screen.getByTestId('start-pipeline-btn'));

    await waitFor(() => {
      const warning = screen.getByTestId('outcome-low-quality-warning');
      expect(warning).toBeInTheDocument();
      expect(warning).toHaveTextContent('No alert, but detection was low quality. This result is not reliable.');
    });
    expect(screen.queryByTestId('outcome-clean-normal')).not.toBeInTheDocument();
  });

  it('renders zero-vehicle state when zero vehicles were ever detected', async () => {
    const user = userEvent.setup();
    const mockFeed: FeedResponse = {
      id: 'feed-zero-1',
      camera_id: 10,
      city: 'Cairo',
      district: 'District 1',
      status: 'done',
      thumbnail_url: '/thumb.jpg',
      created_at: '2026-11-01T10:00:00Z',
      progress: { frames_sent: 50, total_frames: 50, percent: 100 },
      anomalies_detected: 0,
      detection_quality: 'motion_fallback',
      vehicles_detected_count: 0,
    };

    (api.startFeedFromSample as any).mockResolvedValue(mockFeed);
    (api.getFeed as any).mockResolvedValue(mockFeed);

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-sample-nobox');
    await user.click(screen.getByTestId('sample-card-sample-nobox'));
    await user.click(screen.getByTestId('start-pipeline-btn'));

    await waitFor(() => {
      const zeroCard = screen.getByTestId('outcome-zero-vehicles');
      expect(zeroCard).toBeInTheDocument();
      expect(zeroCard).toHaveTextContent('No vehicles were detected in this video');
    });

    expect(screen.queryByTestId('outcome-clean-normal')).not.toBeInTheDocument();
    expect(screen.getByText('NO VEHICLES DETECTED')).toBeInTheDocument();
  });

  it('renders emerald Normal ONLY for reference or neural with anomalies=0 and vehicles_detected>0', async () => {
    const user = userEvent.setup();
    const mockFeed: FeedResponse = {
      id: 'feed-clean-1',
      camera_id: 1528,
      city: 'Shibin El Kom',
      district: 'District 13',
      status: 'done',
      thumbnail_url: '/thumb.jpg',
      created_at: '2026-11-01T10:00:00Z',
      progress: { frames_sent: 50, total_frames: 50, percent: 100 },
      anomalies_detected: 0,
      detection_quality: 'reference',
      vehicles_detected_count: 4,
    };

    (api.startFeedFromSample as any).mockResolvedValue(mockFeed);
    (api.getFeed as any).mockResolvedValue(mockFeed);

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-sample-box');
    await user.click(screen.getByTestId('sample-card-sample-box'));
    await user.click(screen.getByTestId('start-pipeline-btn'));

    await waitFor(() => {
      const cleanNormal = screen.getByTestId('outcome-clean-normal');
      expect(cleanNormal).toBeInTheDocument();
      expect(cleanNormal).toHaveTextContent('Normal Traffic - No Accident');
    });

    expect(screen.queryByTestId('outcome-low-quality-warning')).not.toBeInTheDocument();
    expect(screen.queryByTestId('outcome-zero-vehicles')).not.toBeInTheDocument();
    expect(screen.getByText('NORMAL')).toBeInTheDocument();
  });

  it('displays pre-run fallback warning when sample without box file is selected and opens detector help modal', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    // Sample without box file
    await screen.findByTestId('sample-card-sample-nobox');
    await user.click(screen.getByTestId('sample-card-sample-nobox'));

    // Pre-run warning should be visible
    const preRunWarning = screen.getByTestId('prerun-fallback-warning');
    expect(preRunWarning).toBeInTheDocument();
    expect(preRunWarning).toHaveTextContent('No detector is available for this video; results will be unreliable');

    // Click "How to enable the detector"
    const helpBtn = screen.getByRole('button', { name: /How to enable the detector/i });
    await user.click(helpBtn);

    // Help modal should be visible
    const modal = screen.getByTestId('detector-help-modal');
    expect(modal).toBeInTheDocument();
    expect(modal).toHaveTextContent('Vehicle Detector Configuration');
    expect(modal).toHaveTextContent('MotionFallbackDetector');

    // Close modal
    await user.click(screen.getByTestId('detector-help-close-btn'));
    expect(screen.queryByTestId('detector-help-modal')).not.toBeInTheDocument();
  });

  it('safely handles missing detection_quality as "unknown quality" in CSV and never assumes reference or neural', () => {
    const csv = generateBatchResultsCsv([
      {
        id: 'no-qual',
        name: 'test.mp4',
        relative_path: 'videos/test.mp4',
        expected_label: 'normal',
        // detection_quality is undefined/missing
        alert_raised: false,
        time_to_first_alert_s: null,
        processing_time_s: 1.0,
        status: 'completed',
        outcome: 'No alert on normal clip',
      },
    ]);

    expect(csv).toContain('unknown quality');
    expect(csv).not.toContain(',reference,');
    expect(csv).not.toContain(',neural,');
  });
});
