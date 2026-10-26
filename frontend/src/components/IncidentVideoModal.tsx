import { useEffect, useRef, useState, useCallback } from 'react';
import { X, AlertTriangle, RefreshCw, ExternalLink, ShieldAlert, MapPin, Calendar, Camera } from 'lucide-react';
import type { Incident } from '@/lib/api';

interface IncidentVideoModalProps {
  incident: Incident | null;
  onClose: () => void;
}

export function IncidentVideoModal({ incident, onClose }: IncidentVideoModalProps) {
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
      setIsLoading(true);
      setHasError(false);
      setErrorMessage('');
      setVideoKey((prev) => prev + 1);
    }
  }, [incident]);

  if (!incident) return null;

  const handleRetry = () => {
    setIsLoading(true);
    setHasError(false);
    setErrorMessage('');
    setVideoKey((prev) => prev + 1);
  };

  const videoUrl = `/api/incidents/${incident.id}/video`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl overflow-hidden rounded-xl bg-slate-900 border border-slate-700 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
            <h2 className="text-lg font-semibold text-white tracking-wide">
              Incident Footage: <span className="font-mono text-cyan-400">#{incident.id}</span>
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0">
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

          {/* Details Sidebar Column */}
          <div className="p-5 flex flex-col justify-between bg-slate-900/90 border-t md:border-t-0 md:border-l border-slate-800">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <ShieldAlert className="w-4 h-4 text-red-400" />
                Collision Telemetry
              </div>

              <div className="space-y-2.5 text-sm">
                <div className="flex items-start gap-2.5">
                  <Camera className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                  <div>
                    <span className="text-slate-400 block text-xs">Camera Feed</span>
                    <span className="font-mono font-medium text-white">ID {incident.camera_id}</span>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <Calendar className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                  <div>
                    <span className="text-slate-400 block text-xs">Incident Timestamp</span>
                    <span className="font-mono text-white text-xs">{incident.crash_time}</span>
                  </div>
                </div>

                <div className="flex items-start gap-2.5">
                  <MapPin className="w-4 h-4 text-cyan-400 mt-0.5 shrink-0" />
                  <div>
                    <span className="text-slate-400 block text-xs">Location</span>
                    <span className="text-white">
                      {incident.city || 'Unknown'}, {incident.district || 'Unassigned'}
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800">
                  <span className="text-slate-400 block text-xs mb-1">Pipeline Stitched Frame</span>
                  <span className="font-mono text-xs px-2 py-0.5 bg-slate-800 text-slate-300 rounded border border-slate-700">
                    Starting Frame #{incident.starting_frame_id}
                  </span>
                </div>
              </div>
            </div>

            <div className="pt-4 mt-4 border-t border-slate-800">
              <a
                href={videoUrl}
                target="_blank"
                rel="noreferrer"
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-lg transition"
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
