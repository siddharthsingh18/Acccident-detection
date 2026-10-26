import { useState, useEffect } from 'react';
import { Volume2, VolumeX, Moon, Sun, Shield } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useSound } from '@/contexts/SoundContext';
import { api, type HealthResponse } from '@/lib/api';

export function Navbar() {
  const { theme, toggleTheme } = useTheme();
  const { isSoundEnabled, volume, enableSound, toggleSound, setVolume } = useSound();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState(true);

  // Poll system health every 8 seconds
  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      try {
        const data = await api.getHealth();
        if (isMounted) {
          setHealth(data);
          setIsHealthLoading(false);
        }
      } catch {
        if (isMounted) {
          setHealth(null);
          setIsHealthLoading(false);
        }
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 8000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const isHealthy = health?.status === 'ok';
  const isDegraded = health?.status === 'degraded';

  return (
    <header className="h-16 px-4 md:px-6 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md flex items-center justify-between sticky top-0 z-40">
      {/* Brand & Status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
            <Shield className="w-4 h-4 text-cyan-400" />
          </div>
          <span className="font-bold tracking-wider text-white text-base md:text-lg">
            ARGUS <span className="text-cyan-400 text-xs font-mono font-normal">CONTROL ROOM</span>
          </span>
        </div>

        {/* Live Service Health Indicator */}
        <div className="hidden sm:flex items-center gap-2 pl-4 border-l border-slate-800">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs">
            {isHealthLoading ? (
              <span className="w-2 h-2 rounded-full bg-slate-500 animate-pulse" />
            ) : isHealthy ? (
              <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            ) : isDegraded ? (
              <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]" />
            ) : (
              <span className="w-2 h-2 rounded-full bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]" />
            )}
            <span className="font-mono text-slate-300">
              {isHealthLoading ? 'PROBING' : isHealthy ? 'ONLINE' : isDegraded ? 'DEGRADED' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      {/* Controls: Sound, Volume, Theme */}
      <div className="flex items-center gap-3">
        {/* Audio Siren Unlock / Controls */}
        <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-800 rounded-lg px-2.5 py-1.5">
          {!isSoundEnabled ? (
            <button
              onClick={enableSound}
              className="flex items-center gap-1.5 text-xs font-medium text-amber-400 hover:text-amber-300 transition"
              title="Click to unlock browser audio for incident sirens"
            >
              <VolumeX className="w-4 h-4 text-amber-400" />
              <span className="hidden sm:inline">Enable Sound</span>
            </button>
          ) : (
            <>
              <button
                onClick={toggleSound}
                className="text-emerald-400 hover:text-emerald-300 transition"
                title="Mute incident siren audio"
              >
                <Volume2 className="w-4 h-4" />
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={volume}
                onChange={(e) => setVolume(parseFloat(e.target.value))}
                className="w-16 h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                title={`Volume: ${Math.round(volume * 100)}%`}
              />
            </>
          )}
        </div>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition"
          aria-label="Toggle theme"
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-300" /> : <Moon className="w-4 h-4 text-cyan-400" />}
        </button>
      </div>
    </header>
  );
}
