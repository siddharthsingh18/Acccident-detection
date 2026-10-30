import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Settings as SettingsIcon,
  Volume2,
  Play,
  Database,
  ShieldAlert,
  Sliders,
  HardDrive,
  Info,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Sun,
  Moon,
  Save,
} from 'lucide-react';
import { api, type SystemSettings, type UpdateSettingsRequest } from '@/lib/api';
import { useSound } from '@/contexts/SoundContext';
import { useTheme } from '@/contexts/ThemeContext';

const settingsFormSchema = z.object({
  alert_sound_enabled: z.boolean(),
  siren_volume: z
    .number()
    .min(0, 'Volume must be at least 0%')
    .max(100, 'Volume cannot exceed 100%'),
  clip_retention_days: z
    .number()
    .min(1, 'Retention period must be at least 1 day')
    .max(365, 'Retention period cannot exceed 365 days'),
  min_alert_confidence: z
    .number()
    .min(0.0, 'Confidence must be at least 0.0')
    .max(1.0, 'Confidence cannot exceed 1.0'),
});

type SettingsFormData = z.infer<typeof settingsFormSchema>;

export const Settings: React.FC = () => {
  const queryClient = useQueryClient();
  const { setSoundEnabled, setVolume, playSiren } = useSound();
  const { theme, toggleTheme } = useTheme();

  const [toastMessage, setToastMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Fetch settings from backend
  const {
    data: settingsData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery<SystemSettings>({
    queryKey: ['settings'],
    queryFn: api.getSettings,
    staleTime: 30000,
  });

  // Fetch system health info for About section
  const { data: healthData } = useQuery({
    queryKey: ['system-health'],
    queryFn: api.getHealth,
    staleTime: 15000,
  });

  const {
    handleSubmit,
    control,
    reset,
    watch,
    formState: { errors, isDirty },
  } = useForm<SettingsFormData>({
    resolver: zodResolver(settingsFormSchema),
    defaultValues: {
      alert_sound_enabled: false,
      siren_volume: 80,
      clip_retention_days: 30,
      min_alert_confidence: 0.5,
    },
  });

  // Watch form values for live preview
  const watchedVolume = watch('siren_volume');
  const watchedSoundEnabled = watch('alert_sound_enabled');
  const watchedConfidence = watch('min_alert_confidence');
  const watchedRetention = watch('clip_retention_days');

  // Populate form when data loads
  useEffect(() => {
    if (settingsData) {
      reset({
        alert_sound_enabled: settingsData.alert_sound_enabled,
        siren_volume: settingsData.siren_volume,
        clip_retention_days: settingsData.clip_retention_days,
        min_alert_confidence: settingsData.min_alert_confidence,
      });
    }
  }, [settingsData, reset]);

  // Mutation to save settings
  const mutation = useMutation({
    mutationFn: (data: UpdateSettingsRequest) => api.updateSettings(data),
    onSuccess: (updated) => {
      queryClient.setQueryData(['settings'], updated);
      queryClient.invalidateQueries({ queryKey: ['settings'] });

      // Sync SoundContext with newly saved settings
      setSoundEnabled(updated.alert_sound_enabled);
      setVolume(updated.siren_volume / 100);

      setToastMessage({ text: 'System settings saved and applied successfully.', type: 'success' });
      setTimeout(() => setToastMessage(null), 4000);
    },
    onError: (err: any) => {
      setToastMessage({ text: err.message || 'Failed to save settings.', type: 'error' });
      setTimeout(() => setToastMessage(null), 5000);
    },
  });

  const onSubmit = (formData: SettingsFormData) => {
    mutation.mutate(formData);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto pb-16">
      {/* Toast Notification */}
      {toastMessage && (
        <div
          role="alert"
          className={`fixed top-20 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-xl text-white transition-all animate-slide-in border ${
            toastMessage.type === 'success'
              ? 'bg-emerald-950/90 border-emerald-500/80 shadow-[0_0_20px_rgba(16,185,129,0.3)]'
              : 'bg-red-950/90 border-red-500/80 shadow-[0_0_20px_rgba(239,68,68,0.3)]'
          }`}
        >
          {toastMessage.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
          )}
          <span className="text-sm font-medium">{toastMessage.text}</span>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[11px] font-mono uppercase font-bold tracking-wider bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/30">
              System Configuration
            </span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2.5">
            <SettingsIcon className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
            Control Room Settings
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Configure surveillance audio sirens, video clip retention policies, and classification sensitivity.
          </p>
        </div>

        {/* Human Verification Notice Badge */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-300 text-xs self-start sm:self-center">
          <ShieldAlert className="w-4 h-4 shrink-0 text-amber-500" />
          <span className="font-semibold">Decision Support Only</span>
        </div>
      </div>

      {/* Loading & Error States */}
      {isLoading && (
        <div className="p-12 text-center rounded-2xl bg-slate-100/60 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 animate-pulse space-y-3">
          <RefreshCw className="w-8 h-8 mx-auto text-cyan-500 animate-spin" />
          <p className="text-sm text-slate-500 dark:text-slate-400 font-mono">Loading system configuration...</p>
        </div>
      )}

      {!isLoading && isError && (
        <div className="p-6 rounded-2xl bg-red-950/20 border border-red-500/30 text-center space-y-3">
          <AlertCircle className="w-8 h-8 mx-auto text-red-400" />
          <p className="text-sm text-red-300 font-medium">Failed to load system settings from backend database.</p>
          <p className="text-xs text-slate-400">{(error as any)?.message || 'Database connection error'}</p>
          <button
            type="button"
            onClick={() => refetch()}
            className="px-4 py-2 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-700 transition"
          >
            Retry Connection
          </button>
        </div>
      )}

      {!isLoading && !isError && (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">

          {/* ======================================================== */}
          {/* SECTION 1: Audio Alarms & Siren Controls                */}
          {/* ======================================================== */}
          <section
            aria-labelledby="audio-settings-heading"
            className="p-5 md:p-6 rounded-2xl bg-white/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-5 transition-colors"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-600 dark:text-cyan-400">
                  <Volume2 className="w-5 h-5" />
                </div>
                <div>
                  <h2 id="audio-settings-heading" className="text-base font-bold text-slate-900 dark:text-white">
                    Audio Alarms & Control Room Siren
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Control audible alert playback when automated collision events are broadcast.
                  </p>
                </div>
              </div>
              <span className={`text-[11px] font-mono font-bold px-2.5 py-1 rounded-full uppercase ${
                watchedSoundEnabled
                  ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30'
                  : 'bg-slate-200 dark:bg-slate-800 text-slate-500 border border-slate-300 dark:border-slate-700'
              }`}>
                {watchedSoundEnabled ? 'Active' : 'Muted'}
              </span>
            </div>

            <div className="space-y-5">
              {/* Audio Toggle */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                <div>
                  <label htmlFor="alert_sound_enabled" className="text-sm font-semibold text-slate-900 dark:text-slate-100 block cursor-pointer">
                    Enable Incident Siren Audio
                  </label>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Plays control room alarm sound upon receiving critical real-time road accident alerts.
                  </p>
                </div>
                <Controller
                  name="alert_sound_enabled"
                  control={control}
                  render={({ field }) => (
                    <button
                      type="button"
                      id="alert_sound_enabled"
                      role="switch"
                      aria-checked={field.value}
                      onClick={() => field.onChange(!field.value)}
                      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 ${
                        field.value ? 'bg-cyan-500' : 'bg-slate-300 dark:bg-slate-700'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          field.value ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  )}
                />
              </div>

              {/* Siren Volume Slider */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label htmlFor="siren_volume" className="text-sm font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-cyan-500" />
                    Siren Audio Volume
                  </label>
                  <span className="text-sm font-mono font-bold text-cyan-600 dark:text-cyan-400">
                    {watchedVolume}%
                  </span>
                </div>
                <Controller
                  name="siren_volume"
                  control={control}
                  render={({ field }) => (
                    <input
                      id="siren_volume"
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={field.value}
                      onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
                      className="w-full h-2 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500 dark:accent-cyan-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
                    />
                  )}
                />
                <div className="flex justify-between text-[10px] font-mono text-slate-400">
                  <span>0% (Silent)</span>
                  <span>50%</span>
                  <span>100% (Maximum Output)</span>
                </div>
                {errors.siren_volume && (
                  <p className="text-xs text-red-500 mt-1">{errors.siren_volume.message}</p>
                )}
              </div>

              {/* Siren Test Button */}
              <div className="pt-2 flex items-center gap-3">
                <button
                  type="button"
                  onClick={playSiren}
                  className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-700 transition cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
                  title="Test siren audio output at current volume"
                >
                  <Play className="w-3.5 h-3.5 text-cyan-500 fill-cyan-500" />
                  <span>Test Siren Audio Output</span>
                </button>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  (Preview audio without sending dispatch events)
                </span>
              </div>
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 2: Appearance & Theme Controls                  */}
          {/* ======================================================== */}
          <section
            aria-labelledby="theme-settings-heading"
            className="p-5 md:p-6 rounded-2xl bg-white/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-4 transition-colors"
          >
            <div className="flex items-center gap-2.5 pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
                {theme === 'dark' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
              </div>
              <div>
                <h2 id="theme-settings-heading" className="text-base font-bold text-slate-900 dark:text-white">
                  Appearance & Display Theme
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Select between Argus Dark Control Room or High-Legibility Light interface.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
              <button
                type="button"
                onClick={() => {
                  if (theme !== 'dark') toggleTheme();
                }}
                className={`p-3.5 rounded-xl border flex items-center justify-between transition cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 ${
                  theme === 'dark'
                    ? 'border-cyan-500 bg-cyan-950/20 shadow-[0_0_12px_rgba(6,182,212,0.15)] text-white'
                    : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 text-slate-600 dark:text-slate-400 hover:border-slate-400'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Moon className={`w-5 h-5 ${theme === 'dark' ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <div>
                    <span className="text-sm font-bold block">Dark Control Room</span>
                    <span className="text-[11px] opacity-75">Optimized for 24/7 CCTV monitor walls</span>
                  </div>
                </div>
                {theme === 'dark' && <CheckCircle2 className="w-4 h-4 text-cyan-400" />}
              </button>

              <button
                type="button"
                onClick={() => {
                  if (theme !== 'light') toggleTheme();
                }}
                className={`p-3.5 rounded-xl border flex items-center justify-between transition cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 ${
                  theme === 'light'
                    ? 'border-cyan-500 bg-cyan-50/80 shadow-[0_0_12px_rgba(6,182,212,0.15)] text-slate-900'
                    : 'border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 text-slate-600 dark:text-slate-400 hover:border-slate-400'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Sun className={`w-5 h-5 ${theme === 'light' ? 'text-cyan-600' : 'text-slate-400'}`} />
                  <div>
                    <span className="text-sm font-bold block">Daylight Mode</span>
                    <span className="text-[11px] opacity-75">High contrast for brightly lit offices</span>
                  </div>
                </div>
                {theme === 'light' && <CheckCircle2 className="w-4 h-4 text-cyan-600" />}
              </button>
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 3: Video Clip Retention & Storage Policy         */}
          {/* ======================================================== */}
          <section
            aria-labelledby="retention-settings-heading"
            className="p-5 md:p-6 rounded-2xl bg-white/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-4 transition-colors"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  <HardDrive className="w-5 h-5" />
                </div>
                <div>
                  <h2 id="retention-settings-heading" className="text-base font-bold text-slate-900 dark:text-white">
                    Video Clip Storage Retention
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Automatically age-out video clip files while permanently preserving incident database records.
                  </p>
                </div>
              </div>
              <span className="text-xs font-mono font-bold px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                {watchedRetention} Days Retention
              </span>
            </div>

            <div className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <label htmlFor="clip_retention_days" className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Clip File Retention Period (1 – 365 Days)
                </label>
                <div className="flex items-center gap-2">
                  <Controller
                    name="clip_retention_days"
                    control={control}
                    render={({ field }) => (
                      <input
                        id="clip_retention_days"
                        type="number"
                        min={1}
                        max={365}
                        value={field.value}
                        onChange={(e) => field.onChange(parseInt(e.target.value, 10) || 1)}
                        className="w-20 px-2.5 py-1 rounded-lg text-center font-mono text-sm font-bold bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
                      />
                    )}
                  />
                  <span className="text-xs text-slate-500 font-mono">days</span>
                </div>
              </div>

              <Controller
                name="clip_retention_days"
                control={control}
                render={({ field }) => (
                  <input
                    type="range"
                    min={1}
                    max={365}
                    value={field.value}
                    onChange={(e) => field.onChange(parseInt(e.target.value, 10))}
                    className="w-full h-2 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500 dark:accent-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
                  />
                )}
              />

              <div className="flex justify-between text-[10px] font-mono text-slate-400">
                <span>1 Day (Ephemeral)</span>
                <span>30 Days (Standard)</span>
                <span>90 Days (Quarterly)</span>
                <span>365 Days (Annual)</span>
              </div>

              {errors.clip_retention_days && (
                <p className="text-xs text-red-500 mt-1">{errors.clip_retention_days.message}</p>
              )}

              {/* Retention Policy Guarantee Card */}
              <div className="mt-2 p-3 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 flex items-start gap-2.5">
                <Database className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-slate-800 dark:text-slate-200 font-medium">Safe Storage Guarantee:</strong>{' '}
                  Only saved clip files (`.avi`, `.mp4`) older than {watchedRetention} days are pruned by <code className="px-1 py-0.5 rounded bg-slate-200 dark:bg-slate-800 font-mono text-[11px]">make cleanup</code>.
                  Database rows in `CrashFrames` and operator review logs are <strong>never deleted</strong>.
                </div>
              </div>
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 4: Detection Sensitivity & Confidence           */}
          {/* ======================================================== */}
          <section
            aria-labelledby="confidence-settings-heading"
            className="p-5 md:p-6 rounded-2xl bg-white/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-4 transition-colors"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                  <Sliders className="w-5 h-5" />
                </div>
                <div>
                  <h2 id="confidence-settings-heading" className="text-base font-bold text-slate-900 dark:text-white">
                    Detection Sensitivity & Confidence Threshold
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Filter out low-probability false alerts from downstream review queue dispatching.
                  </p>
                </div>
              </div>
              <span className="text-xs font-mono font-bold px-2.5 py-1 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/30">
                {(watchedConfidence * 100).toFixed(0)}% Min Threshold
              </span>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label htmlFor="min_alert_confidence" className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Minimum Classification Confidence (0.00 – 1.00)
                </label>
                <span className="text-sm font-mono font-bold text-indigo-600 dark:text-indigo-400">
                  {watchedConfidence.toFixed(2)}
                </span>
              </div>

              <Controller
                name="min_alert_confidence"
                control={control}
                render={({ field }) => (
                  <input
                    id="min_alert_confidence"
                    type="range"
                    min={0.0}
                    max={1.0}
                    step={0.05}
                    value={field.value}
                    onChange={(e) => field.onChange(parseFloat(e.target.value))}
                    className="w-full h-2 bg-slate-200 dark:bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500 dark:accent-indigo-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/50"
                  />
                )}
              />

              <div className="flex justify-between text-[10px] font-mono text-slate-400">
                <span>0.00 (All Alerts)</span>
                <span>0.50 (Balanced)</span>
                <span>1.00 (High Strictness)</span>
              </div>

              {errors.min_alert_confidence && (
                <p className="text-xs text-red-500 mt-1">{errors.min_alert_confidence.message}</p>
              )}

              {/* Pipeline Roadmap Documentation Note */}
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-300 text-xs flex items-start gap-2.5">
                <Info className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                <div>
                  <strong className="uppercase font-mono text-[11px] block tracking-wide">Model Integration Note:</strong>
                  {settingsData?.confidence_note || 'Stored in system profile; not yet applied to legacy pipeline.'}
                  {' '}When ViF and YOLO confidence scoring bridges are active, events scoring below this scalar will be filtered from critical siren dispatch.
                </div>
              </div>
            </div>
          </section>

          {/* ======================================================== */}
          {/* SECTION 5: About & System Information                    */}
          {/* ======================================================== */}
          <section
            aria-labelledby="about-system-heading"
            className="p-5 md:p-6 rounded-2xl bg-white/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 space-y-4 transition-colors"
          >
            <div className="flex items-center gap-2.5 pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-600 dark:text-cyan-400">
                <Info className="w-5 h-5" />
              </div>
              <div>
                <h2 id="about-system-heading" className="text-base font-bold text-slate-900 dark:text-white">
                  About Argus Surveillance Platform
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Core runtime version, SQLite telemetry, and microservices connectivity.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                <span className="text-[10px] text-slate-500 block uppercase">System Version</span>
                <span className="text-sm font-bold text-slate-900 dark:text-white">v1.0.0</span>
                <span className="text-[10px] text-cyan-600 dark:text-cyan-400 block mt-0.5">Control Room Release</span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                <span className="text-[10px] text-slate-500 block uppercase">Backend Bridge</span>
                <span className={`text-sm font-bold ${healthData?.status === 'ok' ? 'text-emerald-500' : 'text-amber-500'}`}>
                  {healthData?.status ? healthData.status.toUpperCase() : 'CONNECTING'}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">FastAPI + ZeroMQ</span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                <span className="text-[10px] text-slate-500 block uppercase">Total Incidents</span>
                <span className="text-sm font-bold text-slate-900 dark:text-white">
                  {healthData?.database?.total_incidents !== undefined ? `${healthData.database.total_incidents} records` : 'Loaded'}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">CrashFrames SQLite</span>
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
                <span className="text-[10px] text-slate-500 block uppercase">Last Config Update</span>
                <span className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate block">
                  {settingsData?.updated_at ? settingsData.updated_at.slice(0, 19).replace('T', ' ') : 'Default'}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">Persistent in DB</span>
              </div>
            </div>

            {/* Regulatory Human Verification Notice */}
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-300 text-xs flex items-start gap-2.5">
              <ShieldAlert className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <strong className="uppercase font-semibold">Human Verification Mandate:</strong>{' '}
                Argus is an assisted decision support platform. A qualified control room operator must visually confirm every detected collision event before dispatching emergency medical or traffic response services. No setting may bypass human review.
              </div>
            </div>
          </section>

          {/* Form Actions Footer */}
          <div className="sticky bottom-4 z-20 flex items-center justify-between p-4 rounded-xl bg-white/90 dark:bg-slate-900/90 backdrop-blur border border-slate-300 dark:border-slate-700 shadow-xl">
            <div className="text-xs text-slate-500 dark:text-slate-400">
              {isDirty ? (
                <span className="text-amber-600 dark:text-amber-400 font-medium">Unsaved configuration changes pending</span>
              ) : (
                <span>All settings up to date</span>
              )}
            </div>

            <button
              type="submit"
              disabled={mutation.isPending}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 dark:bg-cyan-500 dark:hover:bg-cyan-400 text-white dark:text-slate-950 font-bold text-xs uppercase tracking-wider transition shadow-lg shadow-cyan-500/20 disabled:opacity-50 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
            >
              {mutation.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Save System Settings</span>
                </>
              )}
            </button>
          </div>

        </form>
      )}
    </div>
  );
};

export default Settings;
