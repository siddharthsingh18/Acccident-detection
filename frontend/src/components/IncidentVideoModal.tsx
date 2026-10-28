import { useEffect, useRef, useState, useCallback } from 'react';
import {
  X,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  ShieldAlert,
  MapPin,
  Calendar,
  Camera,
  CheckCircle2,
  XCircle,
  FileEdit,
} from 'lucide-react';
import type { Incident } from '@/lib/api';
import { api } from '@/lib/api';
import { ReviewBadge } from '@/components/ReviewBadge';

interface IncidentVideoModalProps {
  incident: Incident | null;
  onClose: () => void;
  onReviewUpdated?: (updated: Incident) => void;
}

export function IncidentVideoModal({ incident, onClose, onReviewUpdated }: IncidentVideoModalProps) {
  const [currentIncident, setCurrentIncident] = useState<Incident | null>(incident);
  const [reviewNote, setReviewNote] = useState<string>('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [reviewFeedback, setReviewFeedback] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [videoKey, setVideoKey] = useState(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [onClose]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  useEffect(() => {
    if (incident) {
      setCurrentIncident(incident);
      setReviewNote(incident.review_note || '');
      setReviewFeedback(null);
      setIsLoading(true);
      setHasError(false);
      setErrorMessage('');
      setVideoKey((prev) => prev + 1);
    }
  }, [incident]);

  if (!currentIncident) return null;

  const handleRetry = () => {
    setIsLoading(true);
    setHasError(false);
    setErrorMessage('');
    setVideoKey((prev) => prev + 1);
  };

  const handleReview = async (status: 'confirmed' | 'false_alarm') => {
    setIsSubmittingReview(true);
    setReviewFeedback(null);
    try {
      const updated = await api.reviewIncident(currentIncident.id, {
        status,
        note: reviewNote.trim() || undefined,
      });
      setCurrentIncident(updated);
      setReviewFeedback(status === 'confirmed' ? 'Incident confirmed' : 'Marked as false alarm');
      onReviewUpdated?.(updated);
    } catch (err: any) {
      setReviewFeedback(err.message || 'Failed to submit review');
    } finally {
      setIsSubmittingReview(false);
    }
  };

  const videoUrl = `/api/incidents/${currentIncident.id}/video`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl overflow-hidden rounded-xl bg-slate-900 border border-slate-700 shadow-2xl flex flex-col max-h-[92vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-3.5 border-b border-slate-800 bg-slate-950/60 shrink-0">
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
            <h2 className="text-lg font-semibold text-white tracking-wide flex items-center gap-2">
              <span>Incident Footage:</span>
              <span className="font-mono text-cyan-400">#{currentIncident.id}</span>
            </h2>
            <ReviewBadge status={currentIncident.review_status} size="sm" />
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 overflow-y-auto flex-1">
          {/* Video Player Column */}
          <div className="md:col-span-2 relative aspect-video bg-black flex items-center justify-center">
            {isLoading && !hasError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 z-10">
                <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin mb-2" />
                <span className="text-sm text-slate-300">Transcoding & streaming footage...</span>
              </div>
            )}

            {hasError ? (
              <div className="p-6 text-center flex flex-col items-center justify-center">
                <AlertTriangle className="w-12 h-12 text-red-400 mb-3" />
                <h3 className="text-lg font-medium text-white mb-1">Failed to Load Footage</h3>
                <p className="text-sm text-slate-400 mb-4 max-w-sm">
                  {errorMessage || 'The incident video could not be streamed or transcoded by the server.'}
                </p>
                <button
                  onClick={handleRetry}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-500 rounded-lg transition"
                >
                  <RefreshCw className="w-4 h-4" />
                  Retry Footage
                </button>
              </div>
            ) : (
              <video
                key={videoKey}
                ref={videoRef}
                data-testid="incident-video-player"
                controls
                autoPlay
                playsInline
                className="w-full h-full object-contain"
                onLoadedData={() => setIsLoading(false)}
                onError={() => {
                  setIsLoading(false);
                  setHasError(true);
                  setErrorMessage('Failed to decode or retrieve video stream from Master node.');
                }}
              >
                <source src={videoUrl} type="video/mp4" />
                Your browser does not support HTML5 video playback.
              </video>
            )}
          </div>

          {/* Details & Review Column */}
          <div className="p-5 flex flex-col justify-between bg-slate-900/90 border-t md:border-t-0 md:border-l border-slate-800 space-y-4">
            <div className="space-y-3.5">
              <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-cyan-400" />
                  Telemetry
                </div>
                <ReviewBadge status={currentIncident.review_status} size="sm" />
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex items-start gap-2.5">
                  <Camera className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                  <div>
                    <span className="text-slate-400 block text-xs">Camera Feed</span>
                    <span className="font-mono font-medium text-white">ID {currentIncident.camera_id}</span>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <Calendar className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                  <div>
                    <span className="text-slate-400 block text-xs">Timestamp</span>
                    <span className="font-mono text-white text-xs">{currentIncident.crash_time}</span>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <MapPin className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                  <div>
                    <span className="text-slate-400 block text-xs">Location</span>
                    <span className="text-white text-xs">
                      {currentIncident.city || 'Unknown'}, {currentIncident.district || 'Unassigned'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Human Verification Triage Actions */}
              <div className="pt-3 border-t border-slate-800 space-y-2.5">
                <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <FileEdit className="w-3.5 h-3.5 text-cyan-400" />
                    Operator Review
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {reviewNote.length}/500
                  </span>
                </div>

                <textarea
                  value={reviewNote}
                  onChange={(e) => setReviewNote(e.target.value.slice(0, 500))}
                  placeholder="Add operator verification note (optional)..."
                  rows={2}
                  className="w-full text-xs bg-slate-950/70 border border-slate-800 rounded-lg p-2 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/40 resize-none"
                />

                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => handleReview('confirmed')}
                    disabled={isSubmittingReview}
                    className="flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-red-500/20 text-red-300 border border-red-500/40 hover:bg-red-500/30 transition disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Confirm
                  </button>

                  <button
                    type="button"
                    onClick={() => handleReview('false_alarm')}
                    disabled={isSubmittingReview}
                    className="flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-500/30 transition disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    False Alarm
                  </button>
                </div>

                {reviewFeedback && (
                  <div className="text-[11px] text-center font-mono text-cyan-300 bg-cyan-950/40 border border-cyan-800/40 rounded px-2 py-1">
                    {reviewFeedback}
                  </div>
                )}
              </div>

              {/* Disclaimer */}
              <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px]">
                <div className="font-semibold uppercase tracking-wider mb-0.5 flex items-center gap-1 text-amber-400">
                  <ShieldAlert className="w-3 h-3" />
                  Decision Support Only
                </div>
                <p className="text-[10px] text-amber-200/90 leading-tight">
                  Verify footage before dispatching emergency responders.
                </p>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-800">
              <a
                href={videoUrl}
                target="_blank"
                rel="noreferrer"
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-lg transition"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Open Raw Clip
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default IncidentVideoModal;
