import { useState, useRef, useEffect } from 'react';
import { Volume2, VolumeX, Moon, Sun, Sparkles, CheckCircle2, AlertTriangle, HelpCircle, Cpu, X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useTheme } from '@/contexts/ThemeContext';
import { useSound } from '@/contexts/SoundContext';
import { useDemo } from '@/contexts/DemoContext';
import { useModelsStatus } from '@/hooks/useModelsStatus';
import { scorerLabel } from '@/lib/modelFormatters';
import { api } from '@/lib/api';

const POLICY_EXPLANATIONS: Record<string, string> = {
  any: 'Any model flags -> alert',
  majority: 'Majority of models flag -> alert',
  all: 'All models must agree -> alert',
  weighted: 'Weighted sum of scores crosses threshold -> alert',
};

export function Navbar() {
  const { theme, toggleTheme } = useTheme();
  const { isSoundEnabled, volume, toggleSound, setVolume } = useSound();
  const { isDemoMode, toggleDemoMode } = useDemo();
  const { modelsStatus, isError: isModelsError, isDegraded, scorers, policy } = useModelsStatus();

  const [isModelsOpen, setIsModelsOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isModelsOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setIsModelsOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsModelsOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isModelsOpen]);

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
    <header className="h-16 px-3 sm:px-4 md:px-6 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md flex items-center justify-between sticky top-0 z-40 transition-colors duration-200">
      {/* Brand */}
      <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
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
          <span className="font-bold tracking-wider text-slate-900 dark:text-white text-sm sm:text-base leading-none">
            ARGUS
          </span>
          <span className="text-cyan-600 dark:text-cyan-400 text-[9px] sm:text-[10px] font-mono tracking-widest uppercase font-semibold">
            Surveillance Ops
          </span>
        </div>
      </div>

      {/* Controls: Health Status, Demo Mode, Sound, Theme */}
      <div className="flex items-center gap-1.5 sm:gap-2.5">
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
          className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-2.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono select-none"
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

        {/* Models Status Indicator & Popover */}
        <div className="relative">
          <button
            ref={buttonRef}
            type="button"
            data-testid="models-status-button"
            aria-expanded={isModelsOpen}
            aria-haspopup="dialog"
            aria-label="Model ensemble status details"
            onClick={() => setIsModelsOpen(!isModelsOpen)}
            className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg border text-xs font-mono transition select-none cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 ${
              isModelsError || !modelsStatus
                ? 'bg-slate-100 dark:bg-slate-900 border-slate-300 dark:border-slate-800 text-slate-500'
                : isDegraded
                ? 'bg-amber-500/10 border-amber-500/40 text-amber-500 dark:text-amber-400'
                : 'bg-emerald-500/10 border-emerald-500/40 text-emerald-600 dark:text-emerald-400'
            }`}
          >
            {isModelsError || !modelsStatus ? (
              <HelpCircle className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            ) : isDegraded ? (
              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400 shrink-0" />
            ) : (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400 shrink-0" />
            )}
            <span className="hidden sm:inline font-semibold">
              {isModelsError || !modelsStatus
                ? 'Models Offline'
                : isDegraded
                ? 'Degraded (legacy only)'
                : 'Models OK'}
            </span>
          </button>

          {/* Popover */}
          {isModelsOpen && (
            <div
              ref={popoverRef}
              role="dialog"
              aria-label="Models Ensemble Status"
              data-testid="models-status-popover"
              className="absolute right-0 mt-2 w-80 sm:w-96 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl p-4 z-50 text-slate-900 dark:text-slate-100 animate-slide-in"
            >
              <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-cyan-500 dark:text-cyan-400" />
                  <h3 className="text-xs font-bold font-mono tracking-wider uppercase text-slate-900 dark:text-white">
                    Model Ensemble Status
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsModelsOpen(false)}
                  className="p-1 rounded-md text-slate-400 hover:text-slate-700 dark:hover:text-white transition cursor-pointer"
                  aria-label="Close popover"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="py-3 space-y-3">
                {/* Active Policy */}
                <div className="p-2.5 rounded-lg bg-slate-100 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 text-xs">
                  <div className="text-[10px] uppercase font-mono tracking-wider text-slate-500 dark:text-slate-400 font-semibold mb-0.5">
                    Active Ensemble Policy
                  </div>
                  <div className="font-medium text-slate-800 dark:text-slate-200">
                    {POLICY_EXPLANATIONS[policy] || `${policy} policy`}
                  </div>
                </div>

                {/* Degraded Alert */}
                {isDegraded && (
                  <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-xs flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-semibold uppercase tracking-wider font-mono">Degraded:</span>{' '}
                      Running with fewer models than configured. Some scorers are unavailable.
                    </div>
                  </div>
                )}

                {/* Scorers List */}
                <div className="space-y-2">
                  <div className="text-[10px] uppercase font-mono tracking-wider text-slate-500 dark:text-slate-400 font-semibold">
                    Registered Crash Scorers ({scorers.length})
                  </div>
                  {scorers.map((s) => {
                    const meta = scorerLabel(s.name);
                    return (
                      <div
                        key={s.name}
                        className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800/80 space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-xs text-slate-800 dark:text-slate-200">
                              {meta.label}
                            </span>
                            {s.trained_on?.startsWith("DEV SMOKE TEST") && (
                              <span
                                data-testid="dev-checkpoint-badge"
                                className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/40"
                                title="Developer smoke test checkpoint: scores are not meaningful"
                              >
                                DEV
                              </span>
                            )}
                          </div>
                          {s.available ? (
                            <span className="inline-flex items-center gap-1 text-[10px] font-mono font-medium text-emerald-600 dark:text-emerald-400">
                              <CheckCircle2 className="w-3 h-3" />
                              Available
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[10px] font-mono font-medium text-amber-500 dark:text-amber-400">
                              <AlertTriangle className="w-3 h-3" />
                              Unavailable
                            </span>
                          )}
                        </div>

                        {s.trained_on?.startsWith("DEV SMOKE TEST") && (
                          <div className="text-[10px] text-amber-600 dark:text-amber-400 font-mono bg-amber-500/10 p-1.5 rounded border border-amber-500/20">
                            ⚠️ DEV SMOKE TEST: Scores are synthetic/uncalibrated and not meaningful for production use.
                          </div>
                        )}

                        <div className="grid grid-cols-2 gap-x-2 text-[11px] font-mono text-slate-500 dark:text-slate-400">
                          <span>Version: <strong className="text-slate-700 dark:text-slate-300">{s.version}</strong></span>
                          <span>Trained on: <strong className="text-slate-700 dark:text-slate-300">{s.trained_on}</strong></span>
                          {s.calibration_date && (
                            <span className="col-span-2">Calibrated: <strong className="text-slate-700 dark:text-slate-300">{s.calibration_date}</strong></span>
                          )}
                        </div>

                        {s.reason_unavailable && (
                          <div className="text-[10px] text-amber-600 dark:text-amber-400 font-mono pt-0.5">
                            Reason: {s.reason_unavailable}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Verification disclaimer */}
                <div className="text-[10px] text-slate-500 dark:text-slate-400 border-t border-slate-200 dark:border-slate-800 pt-2 text-center">
                  Model estimates, not confirmed facts. Human verification required.
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Demo Mode Toggle */}
        <button
          type="button"
          onClick={toggleDemoMode}
          className={`flex items-center gap-1 sm:gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg text-xs font-semibold transition border cursor-pointer ${
            isDemoMode
              ? 'bg-amber-500/20 text-amber-500 dark:text-amber-300 border-amber-500/50 shadow-[0_0_12px_rgba(245,158,11,0.3)] animate-pulse'
              : 'bg-slate-100 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-800'
          }`}
          title="Toggle client-side demo alert simulator (Never modifies database)"
          aria-label="Toggle Demo Mode"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">DEMO</span>
          {isDemoMode && <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>}
        </button>

        {/* Audio Siren Controls (Mute Toggle + Volume Slider) */}
        <div className="flex items-center gap-1.5 sm:gap-2 bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-2 sm:px-2.5 py-1.5">
          <button
            type="button"
            onClick={toggleSound}
            className="flex items-center gap-1 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:text-cyan-500 transition cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
            title={isSoundEnabled ? 'Audio Alarms Active (Click to mute)' : 'Audio Muted (Click to enable)'}
            aria-label={isSoundEnabled ? 'Mute sound alarms' : 'Unmute sound alarms'}
          >
            {isSoundEnabled ? (
              <Volume2 className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />
            ) : (
              <VolumeX className="w-4 h-4 text-slate-400" />
            )}
            <span className="hidden md:inline">{isSoundEnabled ? 'ON' : 'MUTED'}</span>
          </button>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
            className="w-10 sm:w-14 md:w-16 h-1 bg-slate-300 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500 dark:accent-cyan-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
            title={`Siren Volume: ${Math.round(volume * 100)}%`}
            aria-label="Siren Volume Slider"
          />
        </div>

        {/* Theme Toggle Button */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-1.5 sm:p-2 rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
          aria-label="Toggle theme"
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-cyan-600" />}
        </button>
      </div>
    </header>
  );
}

export default Navbar;
