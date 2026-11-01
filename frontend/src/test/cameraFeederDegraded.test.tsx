import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { CameraFeeder } from '@/pages/CameraFeeder';
import { api, type FeedResponse } from '@/lib/api';

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

describe('CameraFeeder - Degraded Mode Banner', () => {
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
        output_video_url: null,
      },
    ]);
  });

  it('displays degraded mode banner when feed response has degraded: true', async () => {
    const user = userEvent.setup();
    const degradedFeed: FeedResponse = {
      id: 'feed_deg_1',
      camera_id: 1528,
      city: 'Cairo',
      district: 'District 1',
      status: 'processing',
      thumbnail_url: '/thumbs/1528.jpg',
      progress: {
        frames_sent: 50,
        total_frames: 100,
        percent: 50,
      },
      created_at: '2026-11-01T10:00:00Z',
      degraded: true,
      active_scorers: ['vif_svm'],
    };

    (api.startSampleFeed as any).mockResolvedValue(degradedFeed);
    (api.getFeed as any).mockResolvedValue(degradedFeed);

    render(
      <MemoryRouter>
        <CameraFeeder />
      </MemoryRouter>
    );

    // Wait for samples to load and button to be enabled
    const runBtn = await screen.findByRole('button', { name: /Start Accident Detection Pipeline/i });
    expect(runBtn).not.toBeDisabled();
    await user.click(runBtn);

    const banner = await screen.findByTestId('feed-degraded-banner');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(/Running with fewer models than configured. Alerts may be less reliable./i);
  });
});
