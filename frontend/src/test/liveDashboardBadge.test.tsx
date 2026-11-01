import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LiveDashboard } from '@/pages/LiveDashboard';
import { api, type Incident } from '@/lib/api';

const mockUseAlertSocket = vi.fn();
const mockUseSound = vi.fn();
const mockUseDemo = vi.fn();

vi.mock('@/hooks/useAlertSocket', () => ({
  useAlertSocket: () => mockUseAlertSocket(),
}));

vi.mock('@/contexts/SoundContext', () => ({
  useSound: () => mockUseSound(),
}));

vi.mock('@/contexts/DemoContext', () => ({
  useDemo: () => mockUseDemo(),
}));

vi.mock('@/lib/api', () => ({
  api: {
    getRecentIncidents: vi.fn(),
  },
}));

describe('LiveDashboard - Model Scores & Agreement Badge', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSound.mockReturnValue({
      playSiren: vi.fn(),
    });
    mockUseDemo.mockReturnValue({
      demoAlert: null,
      setLastAlertTime: vi.fn(),
    });
    mockUseAlertSocket.mockReturnValue({
      alerts: [],
      latestAlert: null,
      connectionStatus: 'connected',
      clearAlerts: vi.fn(),
      dismissAlert: vi.fn(),
    });
    (api.getRecentIncidents as any).mockResolvedValue([]);
  });

  it('renders model agreement badge when incident has valid model_scores', async () => {
    const incidentWithScores: Incident = {
      id: 'cam1_100',
      rowid: 1,
      camera_id: 1,
      starting_frame_id: 100,
      crash_time: '2026-11-01 10:00:00',
      city: 'Cairo',
      district: 'Downtown',
      thumbnail_url: '/thumb.jpg',
      video_url: '/video.mp4',
      review_status: null,
      model_scores: {
        policy: 'majority',
        threshold: 0.5,
        decision: true,
        scorers: [
          { name: 'vif_svm', score: 0.85, fired: true, calibrated: true, available: true },
          { name: 'convae', score: 0.72, fired: true, calibrated: false, available: true },
          { name: 'resnet_onnx', score: 0.35, fired: false, calibrated: false, available: true },
        ],
      },
    };

    (api.getRecentIncidents as any).mockResolvedValue([incidentWithScores]);

    render(
      <MemoryRouter>
        <LiveDashboard />
      </MemoryRouter>
    );

    const badge = await screen.findByTestId('models-agree-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent('2/3');
    expect(badge).toHaveAttribute('title', expect.stringContaining('2 of 3 models flagged this'));
  });

  it('omits model agreement badge cleanly when incident has null model_scores', async () => {
    const legacyIncident: Incident = {
      id: 'cam2_200',
      rowid: 2,
      camera_id: 2,
      starting_frame_id: 200,
      crash_time: '2026-11-01 09:00:00',
      city: 'Alexandria',
      district: 'Corniche',
      thumbnail_url: '/thumb.jpg',
      video_url: '/video.mp4',
      review_status: null,
      model_scores: null,
    };

    (api.getRecentIncidents as any).mockResolvedValue([legacyIncident]);

    render(
      <MemoryRouter>
        <LiveDashboard />
      </MemoryRouter>
    );

    await screen.findByText(/Camera 2/i);
    expect(screen.queryByTestId('models-agree-badge')).not.toBeInTheDocument();
  });

  it('handles live WebSocket alert with valid model_scores', async () => {
    const liveAlert = {
      incident_id: 'live_cam3_50',
      camera_id: 3,
      starting_frame_id: 50,
      date: '2026-11-01',
      time: '12:00:00',
      city: 'Gizah',
      district: 'Pyramids',
      thumbnail_url: '/thumb3.jpg',
      video_url: '/video3.mp4',
      model_scores: {
        policy: 'any',
        threshold: 0.5,
        decision: true,
        scorers: [
          { name: 'vif_svm', score: 0.9, fired: true, calibrated: true, available: true },
        ],
      },
    };

    mockUseAlertSocket.mockReturnValue({
      alerts: [liveAlert],
      latestAlert: liveAlert,
      connectionStatus: 'connected',
      clearAlerts: vi.fn(),
      dismissAlert: vi.fn(),
    });

    render(
      <MemoryRouter>
        <LiveDashboard />
      </MemoryRouter>
    );

    const badge = await screen.findByTestId('models-agree-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent('1/1');
    expect(screen.getAllByText(/Camera 3/i).length).toBeGreaterThan(0);
  });

  it('handles live WebSocket alert with malformed model_scores without dropping the alert', async () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const malformedAlert: any = {
      incident_id: 'malformed_cam4_10',
      camera_id: 4,
      starting_frame_id: 10,
      date: '2026-11-01',
      time: '12:05:00',
      city: 'Port Said',
      district: 'Harbor',
      thumbnail_url: '/thumb4.jpg',
      video_url: '/video4.mp4',
      model_scores: {
        // Missing required policy and invalid scorers structure
        invalidField: 'bad_data',
        scorers: 'not-an-array',
      },
    };

    mockUseAlertSocket.mockReturnValue({
      alerts: [malformedAlert],
      latestAlert: malformedAlert,
      connectionStatus: 'connected',
      clearAlerts: vi.fn(),
      dismissAlert: vi.fn(),
    });

    render(
      <MemoryRouter>
        <LiveDashboard />
      </MemoryRouter>
    );

    // The alert is still displayed
    await waitFor(() => {
      expect(screen.getAllByText(/Camera 4/i).length).toBeGreaterThan(0);
    });

    // Badge is safely omitted because model_scores fell back to null
    expect(screen.queryByTestId('models-agree-badge')).not.toBeInTheDocument();
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Malformed model_scores in alert payload'),
      expect.anything()
    );

    consoleWarnSpy.mockRestore();
  });
});
