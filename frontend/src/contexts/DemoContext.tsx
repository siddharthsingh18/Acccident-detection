import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import type { AlertMessage } from '@/lib/api';

const DEMO_ALERTS_POOL: Omit<AlertMessage, 'date' | 'time'>[] = [
  {
    incident_id: 'DEMO-1528',
    camera_id: 1528,
    starting_frame_id: 76,
    city: 'Shibin El Kom',
    district: 'District 13',
    thumbnail_url: '/media/thumbnails/1528_76.jpg',
    video_url: '/api/incidents/1528_76/video',
    model_scores: {
      policy: 'majority',
      threshold: 0.5,
      decision: true,
      scorers: [
        { name: 'vif_svm', score: 0.92, fired: true, calibrated: true, available: true, latency_ms: 18 },
        { name: 'convae', score: 0.85, fired: true, calibrated: false, available: true, latency_ms: 45 },
        { name: 'resnet_onnx', score: 0.78, fired: true, calibrated: false, available: true, latency_ms: 32 },
      ],
    },
  },
  {
    incident_id: 'DEMO-1566',
    camera_id: 1566,
    starting_frame_id: 151,
    city: 'Hurghada',
    district: 'District 16',
    thumbnail_url: '/media/thumbnails/1566_151.jpg',
    video_url: '/api/incidents/1528_76/video',
    model_scores: {
      policy: 'majority',
      threshold: 0.5,
      decision: true,
      scorers: [
        { name: 'vif_svm', score: 0.82, fired: true, calibrated: true, available: true, latency_ms: 19 },
        { name: 'convae', score: 0.73, fired: true, calibrated: false, available: true, latency_ms: 43 },
        { name: 'resnet_onnx', score: 0.36, fired: false, calibrated: false, available: true, latency_ms: 31 },
      ],
    },
  },
  {
    incident_id: 'DEMO-1559',
    camera_id: 1559,
    starting_frame_id: 91,
    city: 'Cairo',
    district: 'District 7',
    thumbnail_url: '/media/thumbnails/1559_91.jpg',
    video_url: '/api/incidents/1528_76/video',
    model_scores: {
      policy: 'any',
      threshold: 0.5,
      decision: true,
      scorers: [
        { name: 'vif_svm', score: 0.78, fired: true, calibrated: true, available: true, latency_ms: 17 },
        { name: 'convae', score: 0.32, fired: false, calibrated: false, available: true, latency_ms: 40 },
        { name: 'resnet_onnx', score: 0.21, fired: false, calibrated: false, available: true, latency_ms: 28 },
      ],
    },
  },
  {
    incident_id: 'DEMO-1521',
    camera_id: 1521,
    starting_frame_id: 121,
    city: 'Qena',
    district: 'District 2',
    thumbnail_url: '/media/thumbnails/1521_121.jpg',
    video_url: '/api/incidents/1528_76/video',
    model_scores: {
      policy: 'majority',
      threshold: 0.5,
      decision: true,
      scorers: [
        { name: 'vif_svm', score: 0.89, fired: true, calibrated: true, available: true, latency_ms: 16 },
        { name: 'convae', score: 0.0, fired: false, calibrated: false, available: false, reason_unavailable: 'Model weights file missing' },
        { name: 'resnet_onnx', score: 0.84, fired: true, calibrated: false, available: true, latency_ms: 34 },
      ],
    },
  },
];

interface DemoContextType {
  isDemoMode: boolean;
  toggleDemoMode: () => void;
  demoAlert: AlertMessage | null;
  lastAlertTime: Date | null;
  setLastAlertTime: (time: Date) => void;
  triggerNextDemoAlert: () => void;
}

const DemoContext = createContext<DemoContextType | undefined>(undefined);

export function DemoProvider({ children }: { children: React.ReactNode }) {
  const [isDemoMode, setIsDemoMode] = useState<boolean>(false);
  const [demoAlert, setDemoAlert] = useState<AlertMessage | null>(null);
  const [lastAlertTime, setLastAlertTime] = useState<Date | null>(null);
  const poolIndexRef = useRef(0);
  const intervalRef = useRef<number | null>(null);

  const toggleDemoMode = useCallback(() => {
    setIsDemoMode((prev) => !prev);
  }, []);

  const triggerNextDemoAlert = useCallback(() => {
    const template = DEMO_ALERTS_POOL[poolIndexRef.current % DEMO_ALERTS_POOL.length];
    poolIndexRef.current += 1;

    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10);
    const timeStr = now.toTimeString().slice(0, 8);

    const alert: AlertMessage = {
      ...template,
      incident_id: `${template.incident_id}-${Math.floor(100 + Math.random() * 900)}`,
      date: dateStr,
      time: timeStr,
    };

    setDemoAlert(alert);
    setLastAlertTime(now);
  }, []);

  useEffect(() => {
    if (isDemoMode) {
      // Trigger first demo alert immediately
      triggerNextDemoAlert();
      // Then trigger every 14 seconds
      intervalRef.current = window.setInterval(triggerNextDemoAlert, 14000);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setDemoAlert(null);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isDemoMode, triggerNextDemoAlert]);

  return (
    <DemoContext.Provider
      value={{
        isDemoMode,
        toggleDemoMode,
        demoAlert,
        lastAlertTime,
        setLastAlertTime,
        triggerNextDemoAlert,
      }}
    >
      {children}
    </DemoContext.Provider>
  );
}

export function useDemo() {
  const context = useContext(DemoContext);
  if (!context) {
    throw new Error('useDemo must be used within a DemoProvider');
  }
  return context;
}
