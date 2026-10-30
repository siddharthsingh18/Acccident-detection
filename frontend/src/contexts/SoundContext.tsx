import React, { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

interface SoundContextType {
  isSoundEnabled: boolean;
  volume: number; // 0.0 to 1.0
  enableSound: () => void;
  toggleSound: () => void;
  setSoundEnabled: (enabled: boolean) => void;
  setVolume: (vol: number) => void;
  playSiren: () => void;
}

const SoundContext = createContext<SoundContextType | undefined>(undefined);

export function SoundProvider({ children }: { children: React.ReactNode }) {
  const [isSoundEnabled, setIsSoundEnabled] = useState<boolean>(() => {
    const saved = localStorage.getItem('argus-sound-enabled');
    return saved === 'true';
  });

  const [volume, setVolumeState] = useState<number>(() => {
    const saved = localStorage.getItem('argus-volume');
    return saved !== null ? parseFloat(saved) : 0.8;
  });

  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Sync initial sound settings from backend on mount
  useEffect(() => {
    let isMounted = true;
    if (typeof window !== 'undefined' && window.location && window.location.host) {
      api.getSettings()
        .then((settings) => {
          if (!isMounted) return;
          setIsSoundEnabled(settings.alert_sound_enabled);
          setVolumeState(settings.siren_volume / 100);
          localStorage.setItem('argus-sound-enabled', String(settings.alert_sound_enabled));
          localStorage.setItem('argus-volume', String(settings.siren_volume / 100));
        })
        .catch(() => {
          // Silently fall back to cached/local settings when backend is offline
        });
    }

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const audio = new Audio('/siren.mp3');
    audio.preload = 'auto';
    audioRef.current = audio;

    return () => {
      audio.pause();
      audioRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = Math.max(0, Math.min(1, volume));
    }
    localStorage.setItem('argus-volume', String(volume));
  }, [volume]);

  useEffect(() => {
    localStorage.setItem('argus-sound-enabled', String(isSoundEnabled));
  }, [isSoundEnabled]);

  const enableSound = useCallback(() => {
    if (audioRef.current) {
      try {
        const playPromise = audioRef.current.play();
        if (playPromise && typeof playPromise.then === 'function') {
          playPromise
            .then(() => {
              audioRef.current?.pause();
              if (audioRef.current) audioRef.current.currentTime = 0;
              setIsSoundEnabled(true);
            })
            .catch((err) => {
              console.warn('Audio unlock blocked by browser:', err);
              setIsSoundEnabled(true);
            });
        } else {
          setIsSoundEnabled(true);
        }
      } catch {
        setIsSoundEnabled(true);
      }
    } else {
      setIsSoundEnabled(true);
    }
  }, []);

  const setSoundEnabled = useCallback((enabled: boolean) => {
    if (enabled) {
      enableSound();
    } else {
      setIsSoundEnabled(false);
    }
  }, [enableSound]);

  const toggleSound = useCallback(() => {
    if (!isSoundEnabled) {
      enableSound();
    } else {
      setIsSoundEnabled(false);
    }
  }, [isSoundEnabled, enableSound]);

  const setVolume = useCallback((val: number) => {
    setVolumeState(Math.max(0, Math.min(1, val)));
  }, []);

  const playSiren = useCallback(() => {
    if (!isSoundEnabled || !audioRef.current) return;
    audioRef.current.currentTime = 0;
    audioRef.current.play().catch((err) => {
      console.warn('Could not play siren audio:', err);
    });
  }, [isSoundEnabled]);

  return (
    <SoundContext.Provider
      value={{
        isSoundEnabled,
        volume,
        enableSound,
        toggleSound,
        setSoundEnabled,
        setVolume,
        playSiren,
      }}
    >
      {children}
    </SoundContext.Provider>
  );
}

export function useSound() {
  const context = useContext(SoundContext);
  if (!context) {
    throw new Error('useSound must be used within a SoundProvider');
  }
  return context;
}
