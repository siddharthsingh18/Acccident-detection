import React, { useState, useRef, useEffect, useCallback } from 'react';
import { RotateCcw, Download, AlertTriangle, Loader2 } from 'lucide-react';

export interface VideoPlayerProps {
  src: string;
  poster?: string;
  title?: string;
  autoPlay?: boolean;
  muted?: boolean;
  controls?: boolean;
  playsInline?: boolean;
  preload?: 'auto' | 'metadata' | 'none';
  className?: string;
  testId?: string;
  safeDownloadName?: string;
  onClose?: () => void;
}

export function mapMediaErrorCode(code?: number, message?: string): string {
  switch (code) {
    case 1:
      return 'Video playback was aborted by the browser.';
    case 2:
      return 'Network error occurred while fetching video stream.';
    case 3:
      return 'Decoding error: video stream is corrupted or unreadable.';
    case 4:
      return 'Video format or codec is not supported by your browser.';
    default:
      return message && message.trim().length > 0
        ? message
        : 'Failed to load video stream from server.';
  }
}

export function VideoPlayer({
  src,
  poster,
  title,
  autoPlay = false,
  muted = false,
  controls = true,
  playsInline = true,
  preload = 'metadata',
  className = '',
  testId = 'video-player',
  safeDownloadName,
  onClose,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isBuffering, setIsBuffering] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [errorCode, setErrorCode] = useState<number | undefined>(undefined);
  const [reloadKey, setReloadKey] = useState(0);
  const [posterValid, setPosterValid] = useState(true);

  // Check user motion preferences safely (guarding for jsdom/environments without matchMedia)
  const prefersReducedMotion =
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false;

  const shouldAutoplay = autoPlay && !prefersReducedMotion;

  // Reset state when source changes
  useEffect(() => {
    setIsLoading(true);
    setIsBuffering(false);
    setHasError(false);
    setErrorMessage('');
    setErrorCode(undefined);
    setReloadKey((prev) => prev + 1);
  }, [src]);

  const handleRetry = useCallback(() => {
    setIsLoading(true);
    setIsBuffering(false);
    setHasError(false);
    setErrorMessage('');
    setErrorCode(undefined);
    setReloadKey((prev) => prev + 1);
    if (videoRef.current && typeof videoRef.current.load === 'function') {
      videoRef.current.load();
    }
  }, []);

  const handleError = useCallback(() => {
    setIsLoading(false);
    setIsBuffering(false);
    setHasError(true);

    const mediaError = videoRef.current?.error;
    const code = mediaError?.code;
    const rawMsg = mediaError?.message;
    setErrorCode(code);
    const friendlyMsg = mapMediaErrorCode(code, rawMsg);
    setErrorMessage(friendlyMsg);
    console.warn(`[Argus VideoPlayer] Playback error: code ${code} (${friendlyMsg}) on ${src}`);
  }, [src]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === ' ' || e.code === 'Space') {
        e.preventDefault();
        if (videoRef.current) {
          if (videoRef.current.paused) {
            const promise = videoRef.current.play();
            if (promise !== undefined && typeof promise?.catch === 'function') {
              promise.catch(() => {});
            }
          } else {
            videoRef.current.pause();
          }
        }
      } else if (e.key === 'Escape' && onClose) {
        e.preventDefault();
        onClose();
      }
    },
    [onClose]
  );

  const fallbackDownloadFilename = safeDownloadName || (src.split('/').pop()?.split('?')[0] || 'clip.mp4');

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      role="region"
      aria-label={title || 'Video Player'}
      onKeyDown={handleKeyDown}
      className={`relative w-full h-full bg-black flex items-center justify-center overflow-hidden focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/80 ${className}`}
    >
      {/* Loading & Buffering Indicator */}
      {isLoading && !hasError && (
        <div
          data-testid="video-loading-state"
          className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-xs text-white"
        >
          <Loader2 className="w-8 h-8 text-cyan-400 animate-spin mb-3" />
          <span className="text-sm font-medium text-slate-200">Preparing video stream...</span>
          <span className="text-xs text-slate-400 mt-1">Transcoding & seeking enabled</span>
        </div>
      )}

      {isBuffering && !isLoading && !hasError && (
        <div
          data-testid="video-buffering-state"
          className="absolute top-3 right-3 z-20 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-950/80 border border-slate-700/60 text-xs text-slate-300"
        >
          <Loader2 className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
          <span>Buffering...</span>
        </div>
      )}

      {/* Error Fallback Banner */}
      {hasError ? (
        <div
          data-testid="video-error-state"
          className="relative z-20 p-6 flex flex-col items-center justify-center text-center max-w-md mx-auto"
        >
          <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-3">
            <AlertTriangle className="w-6 h-6 text-red-400" />
          </div>
          <h4 className="text-base font-semibold text-white mb-1">Video Stream Unavailable</h4>
          <p className="text-sm text-slate-300 mb-1 leading-relaxed">
            {errorMessage || 'Unable to decode or stream video clip.'}
          </p>
          {errorCode && (
            <p className="text-xs font-mono text-slate-500 mb-4">Error Code: {errorCode}</p>
          )}

          <div className="flex items-center gap-3 mt-2">
            <button
              type="button"
              onClick={handleRetry}
              data-testid="video-retry-button"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium shadow-sm transition cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Retry Playback</span>
            </button>

            <a
              href={src}
              download={fallbackDownloadFilename}
              data-testid="video-download-link"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download Clip</span>
            </a>
          </div>
        </div>
      ) : (
        <video
          key={reloadKey}
          ref={videoRef}
          data-testid={testId}
          src={src}
          poster={posterValid ? poster : undefined}
          controls={controls}
          autoPlay={shouldAutoplay}
          muted={muted}
          playsInline={playsInline}
          preload={preload}
          className="w-full h-full object-contain"
          onLoadedData={() => {
            setIsLoading(false);
            setIsBuffering(false);
          }}
          onWaiting={() => setIsBuffering(true)}
          onPlaying={() => {
            setIsLoading(false);
            setIsBuffering(false);
          }}
          onError={handleError}
        >
          Your browser does not support HTML5 video playback.
        </video>
      )}

      {/* Poster Image Error Handling */}
      {poster && posterValid && (
        <img
          src={poster}
          alt=""
          className="hidden"
          onError={() => setPosterValid(false)}
        />
      )}
    </div>
  );
}
