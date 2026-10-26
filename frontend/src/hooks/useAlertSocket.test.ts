import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useAlertSocket } from './useAlertSocket';
import type { AlertMessage } from '@/lib/api';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) this.onopen();
    }, 10);
  }

  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) this.onclose();
  });
}

describe('useAlertSocket Hook', () => {
  const originalWebSocket = globalThis.WebSocket;


  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.stubGlobal('WebSocket', originalWebSocket);
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('initializes and transitions to connected state', async () => {
    const { result } = renderHook(() => useAlertSocket());
    expect(result.current.connectionStatus).toBe('connecting');

    // Fast-forward open timer
    act(() => {
      vi.advanceTimersByTime(20);
    });

    expect(result.current.connectionStatus).toBe('connected');
    expect(result.current.alerts).toEqual([]);
    expect(result.current.latestAlert).toBeNull();
  });

  it('receives incoming alert messages and updates state', () => {
    const { result } = renderHook(() => useAlertSocket());

    act(() => {
      vi.advanceTimersByTime(20);
    });

    const mockAlert: AlertMessage = {
      incident_id: '1528_76',
      camera_id: 1528,
      starting_frame_id: 76,
      date: '2021-01-07',
      time: '09:39:31',
      city: 'Shibin El Kom',
      district: 'District 13',
      thumbnail_url: '/media/thumbnails/1528_76.jpg',
      video_url: '/api/incidents/1528_76/video',
    };

    const wsInstance = MockWebSocket.instances[0];
    act(() => {
      if (wsInstance.onmessage) {
        wsInstance.onmessage({ data: JSON.stringify(mockAlert) });
      }
    });

    expect(result.current.latestAlert).toEqual(mockAlert);
    expect(result.current.alerts).toHaveLength(1);
    expect(result.current.alerts[0].incident_id).toBe('1528_76');

    // Test dismissAlert
    act(() => {
      result.current.dismissAlert('1528_76');
    });
    expect(result.current.alerts).toHaveLength(0);
  });

  it('handles disconnect and attempts exponential backoff reconnect', () => {
    const { result } = renderHook(() => useAlertSocket());

    act(() => {
      vi.advanceTimersByTime(20);
    });
    expect(result.current.connectionStatus).toBe('connected');

    const wsInstance = MockWebSocket.instances[0];
    act(() => {
      wsInstance.close();
    });

    expect(result.current.connectionStatus).toBe('disconnected');

    // Advance by backoff timeout (1500ms)
    act(() => {
      vi.advanceTimersByTime(1600);
    });

    // Should create a second WebSocket instance to reconnect
    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(2);
  });
});
