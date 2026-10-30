import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { Settings } from '@/pages/Settings';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { SoundProvider, useSound } from '@/contexts/SoundContext';
import { DemoProvider } from '@/contexts/DemoContext';
import { api, type SystemSettings } from '@/lib/api';

const mockSettings: SystemSettings = {
  alert_sound_enabled: true,
  siren_volume: 75,
  clip_retention_days: 45,
  min_alert_confidence: 0.65,
  updated_at: '2026-10-30T05:00:00Z',
  confidence_note: 'Stored in system profile; not yet applied to legacy pipeline',
};

function renderSettingsPage(customSettings = mockSettings) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  vi.spyOn(api, 'getSettings').mockResolvedValue(customSettings);
  vi.spyOn(api, 'getHealth').mockResolvedValue({
    status: 'ok',
    services: {},
    database: { accessible: true, total_incidents: 150 },
    ffmpeg: { available: true },
    zmq_listener: { running: true, status: 'running' },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <SoundProvider>
          <DemoProvider>
            <MemoryRouter>
              <Settings />
            </MemoryRouter>
          </DemoProvider>
        </SoundProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

describe('Settings Page & Sound Synchronization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all 5 configuration sections with initial backend values', async () => {
    renderSettingsPage();

    await screen.findByText(/Audio Alarms & Control Room Siren/i);

    // Check sections exist
    expect(screen.getByText(/Audio Alarms & Control Room Siren/i)).toBeInTheDocument();
    expect(screen.getByText(/Appearance & Display Theme/i)).toBeInTheDocument();
    expect(screen.getByText(/Video Clip Storage Retention/i)).toBeInTheDocument();
    expect(screen.getByText(/Detection Sensitivity & Confidence Threshold/i)).toBeInTheDocument();
    expect(screen.getByText(/About Argus Surveillance Platform/i)).toBeInTheDocument();

    // Check values populated from mockSettings
    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText(/45 Days Retention/i)).toBeInTheDocument();
    expect(screen.getByText(/65% Min Threshold/i)).toBeInTheDocument();
  });

  it('switches between Dark Control Room and Daylight themes', async () => {
    renderSettingsPage();

    await screen.findByText(/Appearance & Display Theme/i);

    const daylightBtn = screen.getByRole('button', { name: /Daylight Mode/i });
    act(() => {
      fireEvent.click(daylightBtn);
    });
    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(false);

    const darkBtn = screen.getByRole('button', { name: /Dark Control Room/i });
    act(() => {
      fireEvent.click(darkBtn);
    });
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.classList.contains('light')).toBe(false);
  });

  it('saves updated settings via mutation and displays success toast feedback', async () => {
    const updateSettingsSpy = vi.spyOn(api, 'updateSettings').mockResolvedValueOnce({
      alert_sound_enabled: false,
      siren_volume: 50,
      clip_retention_days: 60,
      min_alert_confidence: 0.8,
      updated_at: '2026-10-30T05:15:00Z',
    });

    renderSettingsPage();

    await screen.findByText(/Audio Alarms & Control Room Siren/i);

    // Change retention days input
    const retentionInput = screen.getByLabelText(/Clip File Retention Period/i);
    act(() => {
      fireEvent.change(retentionInput, { target: { value: '60' } });
    });

    // Submit form
    const saveBtn = screen.getByRole('button', { name: /Save System Settings/i });
    act(() => {
      fireEvent.click(saveBtn);
    });

    await waitFor(() => {
      expect(updateSettingsSpy).toHaveBeenCalledTimes(1);
    });

    // Success toast appears
    await waitFor(() => {
      expect(screen.getByText(/System settings saved and applied successfully/i)).toBeInTheDocument();
    });
  });

  it('SoundContext respects backend settings on mount and updates volume', async () => {
    vi.spyOn(api, 'getSettings').mockResolvedValueOnce({
      alert_sound_enabled: true,
      siren_volume: 90,
      clip_retention_days: 30,
      min_alert_confidence: 0.5,
    });

    const { result } = renderHook(() => useSound(), {
      wrapper: SoundProvider,
    });

    await waitFor(() => {
      expect(result.current.isSoundEnabled).toBe(true);
      expect(result.current.volume).toBe(0.9);
    });
  });
});
