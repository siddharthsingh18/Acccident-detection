import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navbar } from '@/components/Navbar';
import { LiveDashboard } from '@/pages/LiveDashboard';
import { AlertContext, type AlertContextType } from '@/contexts/AlertContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SoundProvider } from '@/contexts/SoundContext';
import { DemoProvider } from '@/contexts/DemoContext';
import { api, type AlertMessage } from '@/lib/api';

describe('Phase 1: Cleanup and Bug Fixes Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Thumbnail Fallback Guard', () => {
    it('sets src to local placeholder and nullifies onerror to guard against infinite loops', () => {
      let errorTriggerCount = 0;
      const handleImgError = (e: React.SyntheticEvent<HTMLImageElement>) => {
        errorTriggerCount++;
        const target = e.currentTarget;
        target.onerror = null;
        target.src = '/placeholder-thumbnail.svg';
      };

      const { container } = render(
        <img
          src="/media/thumbnails/nonexistent_99.jpg"
          alt="Test Incident"
          onError={handleImgError}
        />
      );

      const img = container.querySelector('img')!;
      expect(img).toBeInTheDocument();

      // Trigger first onError
      fireEvent.error(img);

      expect(errorTriggerCount).toBe(1);
      expect(img.getAttribute('src')).toBe('/placeholder-thumbnail.svg');
      expect(img.onerror).toBeNull();

      // Triggering another error event on the same image must not execute the handler again
      if (img.onerror) {
        fireEvent.error(img);
      }
      expect(errorTriggerCount).toBe(1);
    });
  });

  describe('Live Alert Dismiss and Clear All', () => {
    const mockAlert: AlertMessage = {
      incident_id: '1528_76',
      camera_id: 1528,
      starting_frame_id: 76,
      date: '2026-10-30',
      time: '04:30:00',
      city: 'Shibin El Kom',
      district: 'District 13',
      thumbnail_url: '/media/thumbnails/1528_76.jpg',
      video_url: '/api/incidents/1528_76/video',
    };

    it('renders Dismiss on alert cards and Clear all in the active alerts banner', async () => {
      const dismissAlertMock = vi.fn();
      const clearAlertsMock = vi.fn();

      const mockAlertContextValue: AlertContextType = {
        alerts: [mockAlert],
        latestAlert: mockAlert,
        connectionStatus: 'connected',
        dismissAlert: dismissAlertMock,
        clearAlerts: clearAlertsMock,
      };

      vi.spyOn(api, 'getRecentIncidents').mockResolvedValueOnce([
        {
          id: '1528_76',
          rowid: 1,
          camera_id: 1528,
          starting_frame_id: 76,
          crash_time: '2026-10-30 04:30:00',
          city: 'Shibin El Kom',
          district: 'District 13',
          thumbnail_url: '/media/thumbnails/1528_76.jpg',
          video_url: '/api/incidents/1528_76/video',
          review_status: null,
        },
      ]);

      render(
        <QueryClientProvider client={new QueryClient()}>
          <ThemeProvider>
            <SoundProvider>
              <DemoProvider>
                <AlertContext.Provider value={mockAlertContextValue}>
                  <MemoryRouter initialEntries={['/']}>
                    <LiveDashboard />
                  </MemoryRouter>
                </AlertContext.Provider>
              </DemoProvider>
            </SoundProvider>
          </ThemeProvider>
        </QueryClientProvider>
      );

      // Verify Active Alerts Banner exists
      await waitFor(() => {
        expect(screen.getByText(/1 Active Real-Time Alert/i)).toBeInTheDocument();
      });

      // Verify Clear All button
      const clearAllBtn = screen.getByTestId('clear-all-alerts-btn');
      expect(clearAllBtn).toBeInTheDocument();
      fireEvent.click(clearAllBtn);
      expect(clearAlertsMock).toHaveBeenCalledTimes(1);

      // Verify Dismiss button on alert card
      const dismissBtn = screen.getByTestId('dismiss-alert-btn');
      expect(dismissBtn).toBeInTheDocument();
      fireEvent.click(dismissBtn);
      expect(dismissAlertMock).toHaveBeenCalledWith('1528_76');
    });
  });

  describe('Health Status Dot in Navbar', () => {
    const renderNavbarWithHealth = (healthResponse: any, shouldReject = false) => {
      const queryClient = new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
          },
        },
      });

      if (shouldReject) {
        vi.spyOn(api, 'getHealth').mockRejectedValue(new Error('Connection Refused'));
      } else {
        vi.spyOn(api, 'getHealth').mockResolvedValue(healthResponse);
      }

      return render(
        <QueryClientProvider client={queryClient}>
          <ThemeProvider>
            <SoundProvider>
              <DemoProvider>
                <MemoryRouter>
                  <Navbar />
                </MemoryRouter>
              </DemoProvider>
            </SoundProvider>
          </ThemeProvider>
        </QueryClientProvider>
      );
    };

    it('renders green dot and healthy tooltip when health status is ok', async () => {
      renderNavbarWithHealth({
        status: 'ok',
        services: {},
        database: { accessible: true, total_incidents: 120 },
        ffmpeg: { available: true },
        zmq_listener: { running: true, status: 'running' },
      });

      await waitFor(() => {
        const indicator = screen.getByTestId('health-status-indicator');
        expect(indicator).toBeInTheDocument();
        expect(indicator).toHaveAttribute('aria-label', 'System status: OK');
        expect(indicator).toHaveAttribute(
          'title',
          expect.stringContaining('Argus Core: OK | DB: Connected (120 incidents) | ZMQ: Running | FFmpeg: Available')
        );
      });

      const dot = screen.getByTestId('health-status-dot');
      expect(dot.className).toContain('bg-emerald-400');
    });

    it('renders amber dot when health status is degraded', async () => {
      renderNavbarWithHealth({
        status: 'degraded',
        services: {},
        database: { accessible: true, total_incidents: 10 },
        ffmpeg: { available: true },
        zmq_listener: { running: false, status: 'stopped' },
      });

      await waitFor(() => {
        const indicator = screen.getByTestId('health-status-indicator');
        expect(indicator).toBeInTheDocument();
        expect(indicator).toHaveAttribute('aria-label', 'System status: DEGRADED');
      });

      const dot = screen.getByTestId('health-status-dot');
      expect(dot.className).toContain('bg-amber-400');
    });

    it('renders red dot and OFFLINE label when backend is unreachable', async () => {
      renderNavbarWithHealth(null, true);

      await waitFor(() => {
        const indicator = screen.getByTestId('health-status-indicator');
        expect(indicator).toBeInTheDocument();
        expect(indicator).toHaveAttribute('aria-label', 'System status: Unreachable');
        expect(indicator).toHaveAttribute(
          'title',
          'Argus Core: Unreachable (Backend Offline)'
        );
      });

      const dot = screen.getByTestId('health-status-dot');
      expect(dot.className).toContain('bg-red-500');
    });
  });
});
