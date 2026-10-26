import React, { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';

interface SoundContextType {
  isSoundEnabled: boolean;
  volume: number;
  enableSound: () => void;
  toggleSound: () => void;
  setVolume: (vol: number) => void;
  playSiren: () => void;
}

const SoundContext = createContext<SoundContextType | undefined>(undefined);

export function SoundProvider({ children }: { children: React.ReactNode }) {
  const [isSoundEnabled, setIsSoundEnabled] = useState(false);
  const [volume, setVolumeState] = useState<number>(() => {
    const saved = localStorage.getItem('argus-volume');
    return saved !== null ? parseFloat(saved) : 0.8;
  });

  const audioRef = useRef<HTMLAudioElement | null>(null);

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
      audioRef.current.volume = volume;
    }
    localStorage.setItem('argus-volume', String(volume));
  }, [volume]);

  const enableSound = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.play().then(() => {
        audioRef.current?.pause();
        if (audioRef.current) audioRef.current.currentTime = 0;
        setIsSoundEnabled(true);
      }).catch((err) => {
        console.warn('Audio unlock blocked by browser:', err);
      });
    } else {
      setIsSoundEnabled(true);
    }
  }, []);

  const toggleSound = useCallback(() => {
    if (!isSoundEnabled) {
      enableSound();
    } else {
      setIsSoundEnabled(false);
    }
  }, [isSoundEnabled, enableSound]);

  const setVolume = useCallback((val: number) => {
    setVolumeState(val);
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
