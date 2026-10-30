import { Volume2, VolumeX, Sparkles } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useSound } from '@/contexts/SoundContext';
import { useDemo } from '@/contexts/DemoContext';
import { api } from '@/lib/api';

export function Navbar() {
  const { isSoundEnabled, toggleSound } = useSound();
  const { isDemoMode, toggleDemoMode } = useDemo();

  const { data: health, isError } = useQuery({
    queryKey: ['system-health'],
    queryFn: api.getHealth,
    refetchInterval: 15000,
    retry: 1,
  });

  const getHealthTooltip = () => {
    if (isError || !health) {
      return 'Argus Core: Unreachable (Backend Offline)';
    }
    const dbStatus = health.database?.accessible ? 'Connected' : 'Offline';
    const totalIncidents = health.database?.total_incidents !== undefined ? ` (${health.database.total_incidents} incidents)` : '';
    const ffmpegStatus = health.ffmpeg?.available ? 'Available' : 'Missing';
    const zmqStatus = health.zmq_listener?.running ? 'Running' : 'Stopped';
    return `Argus Core: ${health.status.toUpperCase()} | DB: ${dbStatus}${totalIncidents} | ZMQ: ${zmqStatus} | FFmpeg: ${ffmpegStatus}`;
  };

  return (
    <header className="h-16 px-4 md:px-6 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md flex items-center justify-between sticky top-0 z-40 transition-colors duration-200">
      {/* Brand */}
      <div className="flex items-center gap-2.5">
        {/* Custom Argus Multi-Eyed Surveillance Emblem */}
        <div className="relative w-8 h-8 rounded-lg bg-cyan-50 dark:bg-cyan-950/40 border border-cyan-400/40 dark:border-cyan-500/40 flex items-center justify-center shadow-[0_0_10px_rgba(6,182,212,0.2)]">
          <svg viewBox="0 0 32 32" className="w-5 h-5 text-cyan-600 dark:text-cyan-400" fill="none">
            <path
              d="M16 4 L28 10 L28 22 L16 28 L4 22 L4 10 Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <path
              d="M8 16 C12 11 20 11 24 16 C20 21 12 21 8 16 Z"
              stroke="currentColor"
              strokeWidth="1.2"
              fill="#0f172a"
            />
            <circle cx="16" cy="16" r="3" fill="#06b6d4" />
            <circle cx="16" cy="16" r="1.2" fill="#ef4444" />
          </svg>
        </div>

        <div className="flex flex-col">
          <span className="font-bold tracking-wider text-slate-900 dark:text-white text-base leading-none">
            ARGUS
          </span>
          <span className="text-cyan-600 dark:text-cyan-400 text-[10px] font-mono tracking-widest uppercase font-semibold">
            Surveillance Ops
          </span>
        </div>
      </div>

      {/* Controls: Health Status, Demo Mode, Sound, Theme */}
      <div className="flex items-center gap-2.5">
        {/* System Health Dot */}
        <div
          role="status"
          aria-label={
            isError || !health
              ? 'System status: Unreachable'
              : `System status: ${health.status.toUpperCase()}`
          }
          data-testid="health-status-indicator"
          title={getHealthTooltip()}
          className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono select-none"
        >
          <span
            data-testid="health-status-dot"
            className={`w-2 h-2 rounded-full transition-colors ${
              isError || !health || health.status === 'down'
                ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]'
                : health.status === 'degraded'
                ? 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]'
                : 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
            }`}
          />
          <span className="hidden sm:inline text-slate-600 dark:text-slate-400 uppercase text-[10px] font-semibold">
            {isError || !health ? 'OFFLINE' : health.status.toUpperCase()}
          </span>
        </div>

        {/* Demo Mode Toggle */}
        <button
          type="button"
          onClick={toggleDemoMode}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition border cursor-pointer ${
            isDemoMode
              ? 'bg-amber-500/20 text-amber-500 dark:text-amber-300 border-amber-500/50 shadow-[0_0_12px_rgba(245,158,11,0.3)] animate-pulse'
              : 'bg-slate-100 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-800'
          }`}
          title="Toggle client-side demo alert simulator (Never modifies database)"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">DEMO MODE</span>
          {isDemoMode && <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>}
        </button>

        {/* Quick Mute Toggle */}
        <button
          type="button"
          onClick={toggleSound}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition border cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 ${
            isSoundEnabled
              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20'
              : 'bg-slate-100 dark:bg-slate-900 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-200 dark:hover:bg-slate-800'
          }`}
          title={isSoundEnabled ? 'Audio Alarms Active (Click to mute)' : 'Audio Muted (Click to enable sound)'}
          aria-label={isSoundEnabled ? 'Mute sound alarms' : 'Unmute sound alarms'}
        >
          {isSoundEnabled ? (
            <>
              <Volume2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />
              <span className="hidden sm:inline">ALARM ON</span>
            </>
          ) : (
            <>
              <VolumeX className="w-4 h-4 text-slate-400" />
              <span className="hidden sm:inline">MUTED</span>
            </>
          )}
        </button>
      </div>
    </header>
  );
}
