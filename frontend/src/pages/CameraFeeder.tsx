import { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  UploadCloud,
  Video,
  Play,
  XCircle,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Camera,
  MapPin,
  Building,
  ArrowRight
} from 'lucide-react';
import { api, type FeedResponse } from '@/lib/api';

const EGYPTIAN_CITIES = [
  'Cairo',
  'Alexandria',
  'Gizah',
  'Shubra El-Kheima',
  'Port Said',
  'Suez',
  'Luxor',
  'Al-Mansura',
  'Tanta',
  'Asyut',
  'Ismailia',
  'Fayyum',
  'Zagazig',
  'Aswan',
  'Damietta',
  'Damanhur',
  'Al-Minya',
  'Beni Suef',
  'Qena',
  'Sohag',
  'Hurghada',
  'Shibin El Kom',
  'Banha',
  'Arish',
];

const MAX_FILE_SIZE = 200 * 1024 * 1024; // 200 MB
const ALLOWED_EXTENSIONS = ['.mp4', '.avi', '.mkv', '.mov'];

export function CameraFeeder() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewThumbnail, setPreviewThumbnail] = useState<string | null>(null);
  const [cameraId, setCameraId] = useState<number>(() => Math.floor(1000 + Math.random() * 9000));
  const [city, setCity] = useState<string>('Cairo');
  const [district, setDistrict] = useState<string>('District 1');

  // Processing state
  const [activeFeed, setActiveFeed] = useState<FeedResponse | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [is409Conflict, setIs409Conflict] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pollingIntervalRef = useRef<number | null>(null);

  // Clean preview blob on unmount
  useEffect(() => {
    return () => {
      if (previewThumbnail && previewThumbnail.startsWith('blob:')) {
        URL.revokeObjectURL(previewThumbnail);
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [previewThumbnail]);

  // Handle local video selection and extract client preview
  const handleFile = (file: File) => {
    setErrorMessage(null);
    setIs409Conflict(false);

    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setErrorMessage(`Unsupported video extension '${ext}'. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`);
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setErrorMessage(`File exceeds 200MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`);
      return;
    }

    setSelectedFile(file);

    // Auto-extract first frame using HTML5 video + canvas
    const videoUrl = URL.createObjectURL(file);
    const video = document.createElement('video');
    video.src = videoUrl;
    video.currentTime = 0.1;
    video.muted = true;
    video.playsInline = true;

    video.onloadeddata = () => {
      const canvas = document.createElement('canvas');
      canvas.width = 480;
      canvas.height = 360;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg');
        setPreviewThumbnail(dataUrl);
      }
      URL.revokeObjectURL(videoUrl);
    };

    video.onerror = () => {
      // Fallback
      setPreviewThumbnail(null);
      URL.revokeObjectURL(videoUrl);
    };
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  // Start processing feed
  const handleProcess = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setErrorMessage(null);
    setIs409Conflict(false);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('camera_id', String(cameraId));
    formData.append('city', city);
    formData.append('district', district);

    try {
      const feed = await api.createFeed(formData);
      setActiveFeed(feed);
      setIsUploading(false);

      // Start live status polling
      startPolling(feed.id);
    } catch (err: any) {
      setIsUploading(false);
      const msg = err.message || 'Failed to submit camera feed.';
      setErrorMessage(msg);
      if (msg.includes('currently running') || msg.includes('409')) {
        setIs409Conflict(true);
      }
    }
  };

  // Poll progress for active feed
  const startPolling = (feedId: string) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    pollingIntervalRef.current = setInterval(async () => {
      try {
        const updated = await api.getFeed(feedId);
        setActiveFeed(updated);

        if (updated.status === 'done' || updated.status === 'failed' || updated.status === 'cancelled') {
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
          }
        }
      } catch (err: any) {
        console.error('Error polling feed status:', err);
      }
    }, 750);
  };

  // Cancel running feed
  const handleCancel = async () => {
    if (!activeFeed) return;
    try {
      await api.cancelFeed(activeFeed.id);
      setActiveFeed((prev) => (prev ? { ...prev, status: 'cancelled' } : null));
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to cancel feed.');
    }
  };

  const isProcessing =
    isUploading ||
    (activeFeed !== null &&
      (activeFeed.status === 'queued' || activeFeed.status === 'processing'));

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="pb-4 border-b border-slate-800">
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
          <Video className="w-6 h-6 text-cyan-400" />
          CCTV Camera Stream Ingest (Feeder)
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Simulate a physical CCTV camera node by uploading video streams into the Argus multi-node pipeline.
        </p>
      </div>

      {/* Error & 409 Conflict Alerts */}
      {errorMessage && (
        <div
          className={`p-4 rounded-xl border flex items-start gap-3 ${
            is409Conflict
              ? 'bg-amber-950/30 border-amber-500/50 text-amber-300'
              : 'bg-red-950/30 border-red-500/50 text-red-300'
          }`}
        >
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-semibold text-sm">
              {is409Conflict ? 'Pipeline Ingest Node Busy (409 Conflict)' : 'Feed Processing Error'}
            </h4>
            <p className="text-xs opacity-90">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Upload & Form Container */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left Column: Dropzone & Preview */}
        <div className="space-y-4">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
            Surveillance Footage Source
          </label>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            onClick={() => !isProcessing && fileInputRef.current?.click()}
            className={`relative aspect-video rounded-xl border-2 border-dashed flex flex-col items-center justify-center p-6 text-center cursor-pointer transition-all overflow-hidden ${
              isDragOver
                ? 'border-cyan-400 bg-cyan-950/20 shadow-[0_0_20px_rgba(6,182,212,0.3)]'
                : 'border-slate-700 bg-slate-900/50 hover:border-slate-600 hover:bg-slate-900'
            } ${isProcessing ? 'pointer-events-none opacity-60' : ''}`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              accept=".mp4,.avi,.mkv,.mov"
              className="hidden"
            />

            {previewThumbnail ? (
              <div className="relative w-full h-full">
                <img
                  src={previewThumbnail}
                  alt="Video Frame Preview"
                  className="w-full h-full object-cover rounded-lg"
                />
                <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                  <div className="w-12 h-12 rounded-full bg-cyan-500/90 flex items-center justify-center shadow-lg">
                    <Play className="w-5 h-5 text-slate-950 fill-slate-950 ml-0.5" />
                  </div>
                </div>
                <div className="absolute bottom-2 left-2 px-2 py-0.5 rounded bg-black/80 font-mono text-[10px] text-white">
                  {selectedFile?.name}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="w-12 h-12 rounded-full bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center mx-auto text-cyan-400">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">
                    Drop video footage here, or <span className="text-cyan-400">browse</span>
                  </p>
                  <p className="text-xs text-slate-500 mt-1">Supports MP4, AVI, MKV, MOV (up to 200MB)</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Node Metadata & Process Trigger */}
        <div className="space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
              Camera Node Configuration
            </label>

            {/* Camera ID */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
                <Camera className="w-3.5 h-3.5 text-cyan-400" />
                Camera Identifier
              </label>
              <input
                type="number"
                value={cameraId}
                disabled={isProcessing}
                onChange={(e) => setCameraId(parseInt(e.target.value) || 0)}
                className="w-full px-3.5 py-2 text-sm font-mono rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 transition disabled:opacity-50"
              />
            </div>

            {/* City */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
                <Building className="w-3.5 h-3.5 text-cyan-400" />
                Regional City
              </label>
              <select
                value={city}
                disabled={isProcessing}
                onChange={(e) => setCity(e.target.value)}
                className="w-full px-3.5 py-2 text-sm rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 transition disabled:opacity-50"
              >
                {EGYPTIAN_CITIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {/* District */}
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                Surveillance District
              </label>
              <input
                type="text"
                value={district}
                disabled={isProcessing}
                onChange={(e) => setDistrict(e.target.value)}
                className="w-full px-3.5 py-2 text-sm rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 transition disabled:opacity-50"
              />
            </div>
          </div>

          {/* Process & Cancel Buttons */}
          <div className="pt-4 flex items-center gap-3">
            <button
              onClick={handleProcess}
              disabled={!selectedFile || isProcessing}
              className={`flex-1 inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold transition ${
                !selectedFile || isProcessing
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                  : 'bg-cyan-400 hover:bg-cyan-300 text-slate-950 shadow-lg shadow-cyan-500/20'
              }`}
            >
              {isUploading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Uploading Stream...
                </>
              ) : isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Streaming Batches...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-slate-950" />
                  Process Video Stream
                </>
              )}
            </button>

            {isProcessing && (
              <button
                onClick={handleCancel}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium bg-red-950/40 text-red-400 border border-red-500/30 hover:bg-red-900/50 transition"
              >
                <XCircle className="w-4 h-4" />
                Cancel
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Live Stream Progress Panel */}
      {activeFeed && (
        <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl space-y-4 animate-slide-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="flex h-3 w-3 relative">
                {activeFeed.status === 'processing' ? (
                  <>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
                  </>
                ) : activeFeed.status === 'done' ? (
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                ) : (
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                )}
              </span>
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <span>Feed Session</span>
                  <span className="font-mono text-cyan-400 text-xs">#{activeFeed.id.slice(0, 8)}</span>
                </h3>
                <span className="text-xs text-slate-400">
                  Streaming 30-frame batches with 15-frame overlap to Master node (port 10000)
                </span>
              </div>
            </div>

            <div className="font-mono text-xs px-2.5 py-1 rounded bg-slate-950 text-slate-300 border border-slate-800 uppercase">
              {activeFeed.status}
            </div>
          </div>

          {/* Progress Bar */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-mono text-slate-400">
              <span>
                Frames Ingested: {activeFeed.progress.frames_sent} / {activeFeed.progress.total_frames || '...'}
              </span>
              <span className="font-bold text-cyan-400">{activeFeed.progress.percent}%</span>
            </div>
            <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
              <div
                className={`h-full transition-all duration-300 rounded-full ${
                  activeFeed.status === 'done'
                    ? 'bg-emerald-400'
                    : activeFeed.status === 'failed' || activeFeed.status === 'cancelled'
                    ? 'bg-red-500'
                    : 'bg-gradient-to-r from-cyan-500 to-emerald-400 shadow-[0_0_12px_rgba(6,182,212,0.8)]'
                }`}
                style={{ width: `${activeFeed.progress.percent}%` }}
              />
            </div>
          </div>

          {/* Finished Completion Summary */}
          {activeFeed.status === 'done' && (
            <div className="pt-3 border-t border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs text-emerald-400">
                <CheckCircle className="w-4 h-4 shrink-0" />
                <span>
                  Video feed completed. Dispatched {activeFeed.progress.frames_sent} frames to pipeline.
                </span>
              </div>
              <Link
                to="/"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-950 bg-cyan-400 hover:bg-cyan-300 px-3.5 py-1.5 rounded-lg transition"
              >
                <span>View in Live Dashboard</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          )}

          {activeFeed.status === 'cancelled' && (
            <div className="pt-3 border-t border-slate-800 text-xs text-amber-400 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>Camera feed was cancelled by operator. Subprocess terminated.</span>
            </div>
          )}

          {activeFeed.status === 'failed' && (
            <div className="pt-3 border-t border-slate-800 text-xs text-red-400 flex items-center gap-2">
              <XCircle className="w-4 h-4" />
              <span>Camera feed failed: {activeFeed.error || 'Subprocess error.'}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
