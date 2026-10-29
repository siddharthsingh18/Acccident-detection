import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import type { AlertMessage } from '@/lib/api';

export type SocketStatus = 'connected' | 'connecting' | 'disconnected';

export interface AlertContextType {
  alerts: AlertMessage[];
  latestAlert: AlertMessage | null;
  connectionStatus: SocketStatus;
  clearAlerts: () => void;
  dismissAlert: (id: string) => void;
}

export const AlertContext = createContext<AlertContextType | undefined>(undefined);

export function AlertProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);
  const [latestAlert, setLatestAlert] = useState<AlertMessage | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<SocketStatus>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const backoffRef = useRef<number>(1000);
  const connectRef = useRef<() => void>(() => {});

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    const nextDelay = Math.min(backoffRef.current * 1.5, 10000);
    backoffRef.current = nextDelay;
    reconnectTimeoutRef.current = window.setTimeout(() => {
      connectRef.current();
    }, nextDelay);
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setConnectionStatus('connecting');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/alerts`;

    try {
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setConnectionStatus('connected');
        backoffRef.current = 1000;
      };

      socket.onmessage = (event) => {
        try {
          const alertData: AlertMessage = JSON.parse(event.data);
          setLatestAlert(alertData);
          setAlerts((prev) => [alertData, ...prev.filter((a) => a.incident_id !== alertData.incident_id)]);
        } catch (err) {
          console.error('Failed to parse WebSocket alert message:', err);
        }
      };

      socket.onclose = () => {
        setConnectionStatus('disconnected');
        wsRef.current = null;
        scheduleReconnect();
      };

      socket.onerror = () => {
        socket.close();
      };
    } catch {
      setConnectionStatus('disconnected');
      scheduleReconnect();
    }
  }, [scheduleReconnect]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const clearAlerts = useCallback(() => {
    setAlerts([]);
    setLatestAlert(null);
  }, []);

  const dismissAlert = useCallback((id: string) => {
    setAlerts((prev) => prev.filter((a) => a.incident_id !== id));
  }, []);

  return (
    <AlertContext.Provider
      value={{
        alerts,
        latestAlert,
        connectionStatus,
        clearAlerts,
        dismissAlert,
      }}
    >
      {children}
    </AlertContext.Provider>
  );
}

export function useAlertSocket(): AlertContextType {
  const context = useContext(AlertContext);
  if (!context) {
    throw new Error('useAlertSocket must be used within an AlertProvider');
  }
  return context;
}
