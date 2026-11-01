import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
    size_bytes: 4718592, // 4.5 MB
    duration_s: 14.5,
    resolution: '640x360',
    fps: 30,
    thumbnail_url: '/api/samples/videos--1528.mp4/thumbnail',
    video_url: '/api/samples/videos--1528.mp4/video',
    expected_label: 'accident',
    camera_id: 1528,
    city: 'Shibin El Kom',
    district: 'District 13',
    notes: 'Multi-vehicle collision intersection',
  },
  {
    id: 'videos--normal_traffic.mp4',
    name: 'normal_traffic.mp4',
    relative_path: 'videos/normal_traffic.mp4',
    size_bytes: 8388608, // 8 MB
    duration_s: 32.0,
    resolution: '1280x720',
    fps: 25,
    thumbnail_url: '/api/samples/videos--normal_traffic.mp4/thumbnail',
    video_url: '/api/samples/videos--normal_traffic.mp4/video',
    expected_label: 'normal',
    camera_id: 2041,
    city: 'Cairo',
    district: 'District 2',
    notes: 'Clear highway flow',
  },
  {
    id: 'Joiner--clip99.mp4',
    name: 'clip99.mp4',
    relative_path: 'Joiner/vids/clip99.mp4',
    size_bytes: 1048576, // 1 MB
    duration_s: 8.0,
    resolution: '640x480',
    fps: 24,
    thumbnail_url: '/api/samples/Joiner--clip99.mp4/thumbnail',
    video_url: '/api/samples/Joiner--clip99.mp4/video',
    expected_label: 'unknown',
    camera_id: 99,
    city: 'Alexandria',
    district: 'Port Road',
    notes: null,
  },
];

describe('CameraFeeder - Sample Gallery & Preset Exploration (Phase 2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.getSamples as any).mockResolvedValue(mockSamples);
  });

  it('renders sample catalog items with thumbnail, metadata, and expected label chips', async () => {
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    // Verify catalog header counts
    expect(await screen.findByText(/Sample Footage Catalog \(3 Clips\)/i)).toBeInTheDocument();

    // Verify filter chips with accurate counts
    expect(screen.getByTestId('sample-filter-all')).toHaveTextContent('All (3)');
    expect(screen.getByTestId('sample-filter-accident')).toHaveTextContent('Accidents (1)');
    expect(screen.getByTestId('sample-filter-normal')).toHaveTextContent('Normal (1)');
    expect(screen.getByTestId('sample-filter-unknown')).toHaveTextContent('Unlabeled (1)');

    // Verify cards are rendered
    expect(screen.getByTestId('sample-card-videos--1528.mp4')).toBeInTheDocument();
    expect(screen.getByTestId('sample-card-videos--normal_traffic.mp4')).toBeInTheDocument();
    expect(screen.getByTestId('sample-card-Joiner--clip99.mp4')).toBeInTheDocument();

    // Verify metadata display on cards
    expect(screen.getByText('1528.mp4')).toBeInTheDocument();
    expect(screen.getByText('normal_traffic.mp4')).toBeInTheDocument();
    expect(screen.getByText('clip99.mp4')).toBeInTheDocument();
  });

  it('filters samples by expected label (Accident, Normal, Unlabeled)', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-videos--1528.mp4');

    // Filter to Accidents
    await user.click(screen.getByTestId('sample-filter-accident'));
    expect(screen.getByTestId('sample-card-videos--1528.mp4')).toBeInTheDocument();
    expect(screen.queryByTestId('sample-card-videos--normal_traffic.mp4')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sample-card-Joiner--clip99.mp4')).not.toBeInTheDocument();

    // Filter to Normal
    await user.click(screen.getByTestId('sample-filter-normal'));
    expect(screen.queryByTestId('sample-card-videos--1528.mp4')).not.toBeInTheDocument();
    expect(screen.getByTestId('sample-card-videos--normal_traffic.mp4')).toBeInTheDocument();
    expect(screen.queryByTestId('sample-card-Joiner--clip99.mp4')).not.toBeInTheDocument();

    // Filter to Unlabeled
    await user.click(screen.getByTestId('sample-filter-unknown'));
    expect(screen.queryByTestId('sample-card-videos--1528.mp4')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sample-card-videos--normal_traffic.mp4')).not.toBeInTheDocument();
    expect(screen.getByTestId('sample-card-Joiner--clip99.mp4')).toBeInTheDocument();

    // Switch back to All
    await user.click(screen.getByTestId('sample-filter-all'));
    expect(screen.getByTestId('sample-card-videos--1528.mp4')).toBeInTheDocument();
    expect(screen.getByTestId('sample-card-videos--normal_traffic.mp4')).toBeInTheDocument();
    expect(screen.getByTestId('sample-card-Joiner--clip99.mp4')).toBeInTheDocument();
  });

  it('filters samples using the search bar (by filename, camera, location)', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-videos--1528.mp4');

    const searchInput = screen.getByTestId('sample-search-input');

    // Search by city
    await user.type(searchInput, 'Cairo');
    expect(screen.queryByTestId('sample-card-videos--1528.mp4')).not.toBeInTheDocument();
    expect(screen.getByTestId('sample-card-videos--normal_traffic.mp4')).toBeInTheDocument();
    expect(screen.queryByTestId('sample-card-Joiner--clip99.mp4')).not.toBeInTheDocument();

    // Clear search
    await user.click(screen.getByText('Clear'));
    expect(screen.getByTestId('sample-card-videos--1528.mp4')).toBeInTheDocument();

    // Search by camera ID
    await user.type(searchInput, '99');
    expect(screen.getByTestId('sample-card-Joiner--clip99.mp4')).toBeInTheDocument();
    expect(screen.queryByTestId('sample-card-videos--1528.mp4')).not.toBeInTheDocument();
  });

  it('sorts samples according to selected sort dropdown', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-videos--1528.mp4');

    const sortSelect = screen.getByTestId('sample-sort-select');

    // Sort by duration descending
    await user.selectOptions(sortSelect, 'duration-desc');

    const cards = screen.getAllByTestId(/^sample-card-/);
    // normal_traffic (32s) > 1528 (14.5s) > clip99 (8s)
    expect(cards[0]).toHaveAttribute('data-testid', 'sample-card-videos--normal_traffic.mp4');
    expect(cards[1]).toHaveAttribute('data-testid', 'sample-card-videos--1528.mp4');
    expect(cards[2]).toHaveAttribute('data-testid', 'sample-card-Joiner--clip99.mp4');
  });

  it('selects a sample clip upon click and updates camera, city, and district', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-videos--normal_traffic.mp4');

    const normalCard = screen.getByTestId('sample-card-videos--normal_traffic.mp4');
    await user.click(normalCard);

    // Verify normalCard has selected styling / aria-selected
    expect(normalCard).toHaveAttribute('aria-selected', 'true');

    // Verify camera ID input updated
    const camInput = screen.getByDisplayValue('2041');
    expect(camInput).toBeInTheDocument();
  });

  it('supports keyboard navigation (Enter/Space) to select a card', async () => {
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-Joiner--clip99.mp4');

    const clip99Card = screen.getByTestId('sample-card-Joiner--clip99.mp4');
    fireEvent.keyDown(clip99Card, { key: 'Enter', code: 'Enter' });

    expect(clip99Card).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByDisplayValue('99')).toBeInTheDocument();
  });

  it('opens and closes the Preview Modal with raw video stream player', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-preview-btn-videos--1528.mp4');

    // Click preview button
    await user.click(screen.getByTestId('sample-preview-btn-videos--1528.mp4'));

    // Modal should appear
    expect(screen.getByTestId('sample-preview-modal')).toBeInTheDocument();
    expect(screen.getByText('Multi-vehicle collision intersection')).toBeInTheDocument();

    const videoEl = screen.getByTestId('sample-preview-video') as HTMLVideoElement;
    expect(videoEl).toBeInTheDocument();
    expect(videoEl.getAttribute('src')).toBe('/api/samples/videos--1528.mp4/video');

    // Close via Close button
    await user.click(screen.getByTestId('sample-preview-close'));
    expect(screen.queryByTestId('sample-preview-modal')).not.toBeInTheDocument();
  });

  it('allows selecting the clip from inside the Preview Modal', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-preview-btn-videos--normal_traffic.mp4');

    await user.click(screen.getByTestId('sample-preview-btn-videos--normal_traffic.mp4'));
    expect(screen.getByTestId('sample-preview-modal')).toBeInTheDocument();

    // Click "Select This Clip"
    await user.click(screen.getByTestId('sample-preview-select'));

    // Modal should close
    expect(screen.queryByTestId('sample-preview-modal')).not.toBeInTheDocument();

    // Card should be selected
    expect(screen.getByTestId('sample-card-videos--normal_traffic.mp4')).toHaveAttribute('aria-selected', 'true');
  });

  it('starts the feed using POST /api/feeds/from-sample with sample_id and metadata', async () => {
    const user = userEvent.setup();
    const mockFeedResponse: FeedResponse = {
      id: 'feed_sample_123',
      camera_id: 1528,
      city: 'Shibin El Kom',
      district: 'District 13',
      status: 'processing',
      thumbnail_url: '/thumbs/1528.jpg',
      progress: {
        frames_sent: 10,
        total_frames: 100,
        fps: 30,
        percent: 10,
        active_trackers: 2,
        anomalies_detected: 0,
      },
      error: null,
      degraded: false,
    };

    (api.startFeedFromSample as any).mockResolvedValue(mockFeedResponse);
    (api.getFeed as any).mockResolvedValue(mockFeedResponse);

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    await screen.findByTestId('sample-card-videos--1528.mp4');

    // Click Start Pipeline Button
    const startBtn = screen.getByTestId('start-pipeline-btn');
    await user.click(startBtn);

    // Verify api.startFeedFromSample was called
    expect(api.startFeedFromSample).toHaveBeenCalledWith(
      'videos--1528.mp4',
      1528,
      'Shibin El Kom',
      'District 13'
    );

    // Verify busy warning appears while feed is processing
    await waitFor(() => {
      expect(screen.getByTestId('pipeline-busy-warning')).toBeInTheDocument();
      expect(startBtn).toBeDisabled();
    });
  });
});
