import { Volume2, VolumeX, Moon, Sun, Sparkles } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useSound } from '@/contexts/SoundContext';
import { useDemo } from '@/contexts/DemoContext';

export function Navbar() {
  const { theme, toggleTheme } = useTheme();
  const { isSoundEnabled, volume, enableSound, toggleSound, setVolume } = useSound();
  const { isDemoMode, toggleDemoMode } = useDemo();

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

      {/* Controls: Demo Mode, Sound, Theme */}
      <div className="flex items-center gap-2.5">
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

        {/* Audio Siren Unlock / Controls */}
        <div className="flex items-center gap-2 bg-slate-100/90 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1.5">
          {!isSoundEnabled ? (
            <button
              type="button"
              onClick={enableSound}
              className="flex items-center gap-1.5 text-xs font-medium text-amber-600 dark:text-amber-400 hover:text-amber-500 transition cursor-pointer"
              title="Click to unlock browser audio for incident sirens"
            >
              <VolumeX className="w-4 h-4 text-amber-500 dark:text-amber-400" />
              <span className="hidden sm:inline">Enable Sound</span>
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={toggleSound}
                className="text-emerald-600 dark:text-emerald-400 hover:text-emerald-500 transition cursor-pointer"
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
                className="w-16 h-1 bg-slate-300 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-500 dark:accent-cyan-400"
                title={`Volume: ${Math.round(volume * 100)}%`}
              />
            </>
          )}
        </div>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className="p-2 rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition cursor-pointer"
          aria-label="Toggle theme"
          title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-cyan-600" />}
        </button>
      </div>
    </header>
  );
}
