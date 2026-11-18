import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CameraFeeder } from '@/pages/CameraFeeder';
import { api, type SampleItem, type FeedResponse } from '@/lib/api';

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
    rerunFeed: vi.fn(),
    compareRuns: vi.fn(),
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

const mockSample: SampleItem = {
  id: 'videos--1528.mp4',
  name: '1528.mp4',
  relative_path: 'videos/1528.mp4',
  size_bytes: 4718592,
  duration_s: 14.5,
  resolution: '640x360',
  fps: 30,
  thumbnail_url: '/api/samples/videos--1528.mp4/thumbnail',
  video_url: '/api/samples/videos--1528.mp4/video',
  expected_label: 'accident',
  camera_id: 1528,
  city: 'Shibin El Kom',
  district: 'District 13',
};

const mockFeedResponse: FeedResponse = {
  id: 'feed-run-123',
  camera_id: 1528,
  city: 'Shibin El Kom',
  district: 'District 13',
  status: 'done',
  degraded: false,
  active_scorers: ['vif_svm'],
  progress: { frames_sent: 90, total_frames: 90, percent: 100 },
  thumbnail_url: '/thumbnails/1528.jpg',
  created_at: '2026-11-19T00:00:00Z',
  detected_incidents: [],
  anomalies_detected: 0,
  detection_quality: 'neural',
  detector_name: 'SSDLite320',
  detector_config: { detector_confidence: 0.35, distance_factor: 0.25 },
  vehicles_detected_count: 3,
  batches_processed: 3,
};

describe('Phase 3: Advanced Settings Panel and Side-by-side Run Comparison', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getSamples).mockResolvedValue([mockSample]);
    vi.mocked(api.getActiveConfig).mockResolvedValue({
      detector: 'yolo',
      trace_enabled: false,
      adaptive_box_filter: false,
      distance_factor: 0.25,
      single_vehicle: false,
      classifier_threshold: 0.5,
      ensemble_enabled: false,
      crash_policy: 'vif_svm_only',
    });
  });

  it('renders advanced settings toggle and expands panel with controls', async () => {
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    const toggleBtn = await screen.findByTestId('advanced-settings-toggle');
    expect(toggleBtn).toBeInTheDocument();
    expect(screen.queryByTestId('advanced-settings-panel')).not.toBeInTheDocument();

    // Expand
    fireEvent.click(toggleBtn);
    expect(screen.getByTestId('advanced-settings-panel')).toBeInTheDocument();

    // Verify inputs exist
    expect(screen.getByTestId('setting-confidence-slider')).toBeInTheDocument();
    expect(screen.getByTestId('setting-adaptive-box-toggle')).toBeInTheDocument();
    expect(screen.getByTestId('setting-distance-factor-slider')).toBeInTheDocument();
    expect(screen.getByTestId('setting-single-vehicle-toggle')).toBeInTheDocument();
    expect(screen.getByTestId('setting-frame-stride-select')).toBeInTheDocument();
  });

  it('marks modified settings and updates badge when parameters change', async () => {
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    const toggleBtn = await screen.findByTestId('advanced-settings-toggle');
    fireEvent.click(toggleBtn);

    // Change confidence from 0.35 to 0.20
    const confSlider = screen.getByTestId('setting-confidence-slider');
    fireEvent.change(confSlider, { target: { value: '0.20' } });

    // Toggle adaptive box
    const adaptiveToggle = screen.getByTestId('setting-adaptive-box-toggle');
    fireEvent.click(adaptiveToggle);

    // Verify MODIFIED badge appears
    const badge = await screen.findByTestId('modified-settings-badge');
    expect(badge).toHaveTextContent('2 MODIFIED');

    // Reset settings
    const resetBtn = screen.getByTestId('reset-settings-btn');
    fireEvent.click(resetBtn);

    expect(screen.queryByTestId('modified-settings-badge')).not.toBeInTheDocument();
  });

  it('supports side-by-side run comparison when rerun finishes', async () => {
    vi.mocked(api.startFeedFromSample).mockResolvedValue(mockFeedResponse);
    vi.mocked(api.getFeed).mockResolvedValue(mockFeedResponse);
    vi.mocked(api.rerunFeed).mockResolvedValue({
      ...mockFeedResponse,
      id: 'feed-run-456',
      vehicles_detected_count: 5,
    });
    vi.mocked(api.compareRuns).mockResolvedValue({
      run_a_id: 'feed-run-123',
      run_b_id: 'feed-run-456',
      run_a: { id: 'feed-run-123', detector_name: 'SSDLite320', vehicles_detected_count: 3, anomalies_detected: 0 },
      run_b: { id: 'feed-run-456', detector_name: 'SSDLite320', vehicles_detected_count: 5, anomalies_detected: 1 },
      differences: {
        detector_changed: false,
        vehicles_diff: 2,
        alerts_diff: 1,
        config_diff: {
          detector_confidence: { run_a: 0.35, run_b: 0.20 },
        },
      },
    });

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    // Select sample and run initial analysis
    const sampleCard = await screen.findByTestId('sample-card-videos--1528.mp4');
    fireEvent.click(sampleCard);

    const startBtn = screen.getByTestId('start-pipeline-btn');
    fireEvent.click(startBtn);

    await waitFor(() => {
      expect(screen.getByTestId('rerun-feed-btn')).toBeInTheDocument();
    });

    // Click rerun
    const rerunBtn = screen.getByTestId('rerun-feed-btn');
    fireEvent.click(rerunBtn);

    await waitFor(() => {
      expect(screen.getByTestId('view-comparison-btn')).toBeInTheDocument();
    });

    // Open comparison modal
    fireEvent.click(screen.getByTestId('view-comparison-btn'));
    expect(screen.getByTestId('run-comparison-modal')).toBeInTheDocument();
    expect(screen.getByText('Side-by-Side Run Comparison')).toBeInTheDocument();
    expect(screen.getByText('+2')).toBeInTheDocument(); // vehicles diff
  });
});
