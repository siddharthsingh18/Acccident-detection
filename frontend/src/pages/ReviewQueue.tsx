import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  ClipboardCheck,
  CheckCircle2,
  XCircle,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  Camera,
  RefreshCw,
  Sparkles,
  Radio,
  FileEdit,
  ExternalLink,
} from 'lucide-react';
import { api, type Incident } from '@/lib/api';
import { ReviewBadge } from '@/components/ReviewBadge';

export function ReviewQueue() {
  const [queue, setQueue] = useState<Incident[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [reviewedSessionCount, setReviewedSessionCount] = useState(0);

  const videoRef = useRef<HTMLVideoElement | null>(null);

  const loadUnreviewedIncidents = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.getIncidents({ review_status: 'unreviewed', limit: 100 });
      setQueue(res.items);
      setCurrentIndex(0);
      setIsLoading(false);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch unreviewed incidents.');
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUnreviewedIncidents();
  }, [loadUnreviewedIncidents]);

  const currentItem = queue[currentIndex] || null;

  const handleDecision = useCallback(
    async (status: 'confirmed' | 'false_alarm') => {
      if (!currentItem || isSubmitting) return;

      setIsSubmitting(true);
      setFeedback(null);
      try {
        await api.reviewIncident(currentItem.id, {
          status,
          note: reviewNote.trim() || undefined,
        });

        setReviewedSessionCount((prev) => prev + 1);
        setFeedback(
          status === 'confirmed'
            ? `Confirmed Incident #${currentItem.id}`
            : `Flagged Incident #${currentItem.id} as False Alarm`
        );

        // Remove from queue and advance
        setQueue((prevQueue) => {
          const nextQueue = prevQueue.filter((_, idx) => idx !== currentIndex);
          if (currentIndex >= nextQueue.length) {
            setCurrentIndex(Math.max(0, nextQueue.length - 1));
          }
          return nextQueue;
        });

        setReviewNote('');
      } catch (err: any) {
        setFeedback(err.message || 'Failed to submit review');
      } finally {
        setIsSubmitting(false);
      }
    },
    [currentItem, currentIndex, isSubmitting, reviewNote]
  );

  const handleNext = useCallback(() => {
    if (currentIndex < queue.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      setReviewNote('');
      setFeedback(null);
    }
  }, [currentIndex, queue.length]);

  const handlePrev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
      setReviewNote('');
      setFeedback(null);
    }
  }, [currentIndex]);

  // Keyboard shortcuts: C, F, J, K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept when user is typing in an input or textarea
      const targetTag = (e.target as HTMLElement)?.tagName?.toUpperCase();
      if (targetTag === 'INPUT' || targetTag === 'TEXTAREA') {
        return;
      }

      if (e.key === 'c' || e.key === 'C') {
        e.preventDefault();
        handleDecision('confirmed');
      } else if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        handleDecision('false_alarm');
      } else if (e.key === 'j' || e.key === 'J' || e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        handleNext();
      } else if (e.key === 'k' || e.key === 'K' || e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        handlePrev();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleDecision, handleNext, handlePrev]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div>
          <div className="text-[11px] font-mono uppercase tracking-wider text-cyan-400 font-semibold mb-1">
            MONITORING / INCIDENT REVIEW
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
            <ClipboardCheck className="w-6 h-6 text-cyan-400" />
            <span>Review Queue</span>
          </h1>
        </div>

        {/* Queue Metrics & Refresh */}
        <div className="flex items-center gap-3">
          <span
            data-testid="items-left-badge"
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-mono font-bold bg-amber-500/10 text-amber-300 border border-amber-500/30"
          >
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            {queue.length} unreviewed left
          </span>

          {reviewedSessionCount > 0 && (
            <span className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <Sparkles className="w-3.5 h-3.5" />
              {reviewedSessionCount} reviewed today
            </span>
          )}

          <button
            onClick={loadUnreviewedIncidents}
            disabled={isLoading}
            className="p-2 text-slate-400 hover:text-white rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 transition"
            title="Reload queue"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* Keyboard Shortcuts Help Bar */}
      <div className="bg-slate-900/40 border border-slate-800/60 rounded-xl px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>
            <strong>Human Decision Support:</strong> Verify incident footage before initiating emergency response dispatch.
          </span>
        </div>

        <div className="flex items-center gap-3 font-mono text-[11px] text-slate-300">
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 font-bold text-red-300">C</kbd> Confirm
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 font-bold text-emerald-300">F</kbd> False Alarm
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 font-bold text-cyan-300">J</kbd> Next
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 font-bold text-cyan-300">K</kbd> Prev
          </span>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="p-12 text-center rounded-xl border border-slate-800 bg-slate-900/30">
          <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-400">Loading unreviewed surveillance alerts...</p>
        </div>
      )}

      {/* Error State */}
      {!isLoading && error && (
        <div className="p-8 text-center rounded-xl border border-red-500/30 bg-red-950/20 max-w-lg mx-auto">
          <ShieldAlert className="w-10 h-10 text-red-400 mx-auto mb-2" />
          <h3 className="text-base font-medium text-white mb-1">Queue Sync Error</h3>
          <p className="text-xs text-slate-400 mb-4">{error}</p>
          <button
            onClick={loadUnreviewedIncidents}
            className="px-4 py-2 text-xs font-medium text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition"
          >
            Retry Loading
          </button>
        </div>
      )}

      {/* Empty State: Queue Complete */}
      {!isLoading && !error && queue.length === 0 && (
        <div
          data-testid="queue-empty-state"
          className="rounded-xl border border-slate-800/80 bg-slate-900/30 p-12 text-center max-w-xl mx-auto space-y-5 shadow-2xl"
        >
          <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400 shadow-[0_0_24px_rgba(16,185,129,0.15)]">
            <CheckCircle2 className="w-8 h-8" />
          </div>

          <div className="space-y-1.5">
            <h2 className="text-xl font-bold text-white">Review Queue is Clear</h2>
            <p className="text-sm text-slate-400 leading-relaxed max-w-md mx-auto">
              All candidate collision events have been reviewed by operators. New detections from edge camera nodes will appear here automatically.
            </p>
          </div>

          <div className="pt-2 flex items-center justify-center gap-3">
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-cyan-500 text-slate-950 hover:bg-cyan-400 transition"
            >
              <Radio className="w-4 h-4" />
              Live Dashboard
            </Link>
            <button
              onClick={loadUnreviewedIncidents}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition border border-slate-700"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Check for New Alerts
            </button>
          </div>
        </div>
      )}

      {/* Main Review Workspace */}
      {!isLoading && !error && currentItem && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Video Player & Navigation (2/3 width) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="relative aspect-video rounded-xl overflow-hidden bg-black border border-slate-800 shadow-2xl flex items-center justify-center">
              <video
                key={currentItem.id}
                ref={videoRef}
                data-testid="review-video-player"
                controls
                autoPlay
                playsInline
                className="w-full h-full object-contain"
              >
                <source src={`/api/incidents/${currentItem.id}/video`} type="video/mp4" />
                Your browser does not support HTML5 video playback.
              </video>

              {/* Overlay Top Bar */}
              <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 rounded-md text-xs font-mono font-bold bg-slate-950/80 text-cyan-400 border border-slate-700/80 backdrop-blur-sm">
                    #{currentItem.id}
                  </span>
                  <ReviewBadge status={currentItem.review_status} size="sm" />
                </div>

                <div className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-slate-950/80 text-slate-300 border border-slate-700/80 backdrop-blur-sm">
                  Item {currentIndex + 1} of {queue.length}
                </div>
              </div>
            </div>

            {/* Stepper Navigation Controls */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs">
              <button
                type="button"
                onClick={handlePrev}
                disabled={currentIndex === 0}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Previous [K]</span>
              </button>

              <div className="text-slate-400 font-mono">
                Navigating {currentIndex + 1} / {queue.length}
              </div>

              <button
                type="button"
                onClick={handleNext}
                disabled={currentIndex === queue.length - 1}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <span>Next [J]</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Right Column: Telemetry & Triage Actions (1/3 width) */}
          <div className="space-y-5">
            {/* Telemetry Card */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4 shadow-lg">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                <span className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Camera className="w-3.5 h-3.5 text-cyan-400" />
                  Incident Telemetry
                </span>
                <ReviewBadge status={currentItem.review_status} size="sm" />
              </div>

              <div className="space-y-3 text-xs">
                <div className="flex items-start justify-between">
                  <span className="text-slate-400">Camera Feed</span>
                  <span className="font-mono font-bold text-white">ID {currentItem.camera_id}</span>
                </div>

                <div className="flex items-start justify-between">
                  <span className="text-slate-400">Timestamp</span>
                  <span className="font-mono text-slate-200">{currentItem.crash_time}</span>
                </div>

                <div className="flex items-start justify-between">
                  <span className="text-slate-400">Location</span>
                  <span className="text-right text-slate-200">
                    {currentItem.city || 'Unknown'}, {currentItem.district || 'Unassigned'}
                  </span>
                </div>

                <div className="flex items-start justify-between">
                  <span className="text-slate-400">Pipeline Frame</span>
                  <span className="font-mono text-slate-300">Frame #{currentItem.starting_frame_id}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800/80">
                <a
                  href={`/api/incidents/${currentItem.id}/video`}
                  target="_blank"
                  rel="noreferrer"
                  className="w-full inline-flex items-center justify-center gap-1.5 text-xs text-slate-400 hover:text-cyan-400 transition"
                >
                  <ExternalLink className="w-3 h-3" />
                  <span>Open raw MP4 clip</span>
                </a>
              </div>
            </div>

            {/* Operator Triage Actions Card */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-4 shadow-lg">
              <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-300">
                <span className="flex items-center gap-1.5">
                  <FileEdit className="w-3.5 h-3.5 text-cyan-400" />
                  Operator Decision
                </span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {reviewNote.length}/500
                </span>
              </div>

              <textarea
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value.slice(0, 500))}
                placeholder="Optional triage note (e.g. rear-end collision, high impact)..."
                rows={3}
                className="w-full text-xs bg-slate-950/80 border border-slate-800 rounded-lg p-3 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/40 resize-none"
              />

              {/* Triage Buttons */}
              <div className="space-y-2">
                <button
                  type="button"
                  data-testid="confirm-btn"
                  onClick={() => handleDecision('confirmed')}
                  disabled={isSubmitting}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-red-500/20 text-red-300 border border-red-500/40 hover:bg-red-500/30 transition disabled:opacity-50 shadow-md shadow-red-950/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
                >
                  <CheckCircle2 className="w-4 h-4 text-red-400" />
                  <span>Confirm Collision (C)</span>
                </button>

                <button
                  type="button"
                  data-testid="false-alarm-btn"
                  onClick={() => handleDecision('false_alarm')}
                  disabled={isSubmitting}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30 transition disabled:opacity-50 shadow-md shadow-emerald-950/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                >
                  <XCircle className="w-4 h-4 text-emerald-400" />
                  <span>False Alarm (F)</span>
                </button>
              </div>

              {feedback && (
                <div
                  data-testid="decision-feedback"
                  className="text-xs text-center font-mono text-cyan-300 bg-cyan-950/40 border border-cyan-800/40 rounded-lg px-3 py-2"
                >
                  {feedback}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ReviewQueue;
