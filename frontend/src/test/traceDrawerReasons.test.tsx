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
    getRunTrace: vi.fn(),
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

const mockFeed: FeedResponse = {
  id: 'feed-trace-p5',
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
  detector_name: 'ssdlite320',
  effective_config: { detector_confidence: 0.20, distance_factor: 0.33 },
  vehicles_detected_count: 2,
  batches_processed: 3,
};

describe('Phase 5: UI Run Summary and Trace Drawer Diagnostics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getSamples).mockResolvedValue([mockSample]);
    vi.mocked(api.startFeedFromSample).mockResolvedValue(mockFeed);
    vi.mocked(api.getFeed).mockResolvedValue(mockFeed);
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

  it('renders confidence used in run summary line', async () => {
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    const sampleCard = await screen.findByTestId('sample-card-videos--1528.mp4');
    fireEvent.click(sampleCard);
    fireEvent.click(screen.getByTestId('start-pipeline-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('run-summary-line')).toBeInTheDocument();
    });

    expect(screen.getByTestId('run-summary-confidence')).toHaveTextContent('0.20');
    expect(screen.getByTestId('run-summary-detector')).toHaveTextContent('ssdlite320');
    expect(screen.getByTestId('run-summary-vehicles')).toHaveTextContent('2');
  });

  it('renders trace diagnostics drawer with remediation link and false alarm warning for NO_DETECTIONS', async () => {
    vi.mocked(api.getRunTrace).mockResolvedValue({
      run_id: 'feed-trace-p5',
      has_trace: true,
      summary: {
        total_batches: 3,
        batches_processed: 3,
        max_trackers: 0,
        pairs_evaluated: 0,
        filter_counts: {},
        dominant_filter: 'NONE',
        max_classifier_score: 0.0,
        alert_count: 0,
        detector_used: 'ssdlite320',
        detection_quality: 'neural',
        primary_cause: 'NO_DETECTIONS',
      },
      records_count: 3,
    });

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    const sampleCard = await screen.findByTestId('sample-card-videos--1528.mp4');
    fireEvent.click(sampleCard);
    fireEvent.click(screen.getByTestId('start-pipeline-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('toggle-active-trace-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('toggle-active-trace-btn'));

    expect(screen.getByTestId('active-trace-primary-cause')).toHaveTextContent('Cause: NO_DETECTIONS');
    expect(screen.getByTestId('active-trace-action-btn')).toHaveTextContent('Adjust Detector Confidence in Advanced Settings');
    expect(screen.getByTestId('active-trace-false-alarm-warning')).toHaveTextContent('False Alarm Warning: Lowering confidence threshold increases false detections');
  });

  it('renders trace diagnostics drawer with remediation link and false alarm warning for SINGLE_VEHICLE', async () => {
    vi.mocked(api.getRunTrace).mockResolvedValue({
      run_id: 'feed-trace-p5',
      has_trace: true,
      summary: {
        total_batches: 3,
        batches_processed: 3,
        max_trackers: 1,
        pairs_evaluated: 0,
        filter_counts: {},
        dominant_filter: 'NONE',
        max_classifier_score: 0.0,
        alert_count: 0,
        detector_used: 'ssdlite320',
        detection_quality: 'neural',
        primary_cause: 'SINGLE_VEHICLE',
      },
      records_count: 3,
    });

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    const sampleCard = await screen.findByTestId('sample-card-videos--1528.mp4');
    fireEvent.click(sampleCard);
    fireEvent.click(screen.getByTestId('start-pipeline-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('toggle-active-trace-btn')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('toggle-active-trace-btn'));

    expect(screen.getByTestId('active-trace-primary-cause')).toHaveTextContent('Cause: SINGLE_VEHICLE');
    expect(screen.getByTestId('active-trace-action-btn')).toHaveTextContent('Enable Single-Vehicle Mode in Advanced Settings');
    expect(screen.getByTestId('active-trace-false-alarm-warning')).toHaveTextContent('False Alarm Warning: Single-vehicle mode may flag aggressive braking');
  });
});
