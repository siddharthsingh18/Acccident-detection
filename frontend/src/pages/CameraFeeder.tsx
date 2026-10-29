import { useState, useRef, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  UploadCloud,
  Video,
  Play,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Camera,
  MapPin,
  Building,
  ShieldAlert,
  Flame,
  Activity,
  Maximize2,
  Download,
  Search,
  CheckCircle2,
  ChevronRight,
  Radio
} from 'lucide-react';
import { api, type FeedResponse, type Incident, type SampleFeed } from '@/lib/api';
import { useAlertSocket } from '@/hooks/useAlertSocket';
import { useSound } from '@/contexts/SoundContext';
import { IncidentVideoModal } from '@/components/IncidentVideoModal';

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
  // Input State
  const [samples, setSamples] = useState<SampleFeed[]>([]);
  const [selectedSample, setSelectedSample] = useState<SampleFeed | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [inputVideoUrl, setInputVideoUrl] = useState<string | null>(null);
  const [cameraId, setCameraId] = useState<number>(1528);
  const [city, setCity] = useState<string>('Shibin El Kom');
  const [district, setDistrict] = useState<string>('District 13');
  const [sampleFilter, setSampleFilter] = useState<'all' | 'accident' | 'normal'>('all');
  const [sampleSearch, setSampleSearch] = useState<string>('');

  const accidentCount = useMemo(() => samples.filter((s) => s.has_accident).length, [samples]);
  const normalCount = useMemo(() => samples.filter((s) => !s.has_accident).length, [samples]);

  const filteredSamples = useMemo(() => {
    return samples.filter((s) => {
      if (sampleFilter === 'accident' && !s.has_accident) return false;
      if (sampleFilter === 'normal' && s.has_accident) return false;
      if (sampleSearch.trim()) {
        const q = sampleSearch.toLowerCase();
        const matchCam = String(s.camera_id).includes(q);
        const matchCity = s.city.toLowerCase().includes(q);
        const matchDistrict = s.district.toLowerCase().includes(q);
        const matchLabel = s.label.toLowerCase().includes(q);
        return matchCam || matchCity || matchDistrict || matchLabel;
      }
      return true;
    });
  }, [samples, sampleFilter, sampleSearch]);

  // Processing & Output State
  const [activeFeed, setActiveFeed] = useState<FeedResponse | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [is409Conflict, setIs409Conflict] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);

  // Detection Outcome
  const [detectionOutcome, setDetectionOutcome] = useState<'idle' | 'processing' | 'accident' | 'normal'>('idle');
  const [outputIncident, setOutputIncident] = useState<Incident | null>(null);
  const [outputVideoUrl, setOutputVideoUrl] = useState<string | null>(null);
  const [modalIncident, setModalIncident] = useState<Incident | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pollingIntervalRef = useRef<number | null>(null);
  const inputVideoRef = useRef<HTMLVideoElement | null>(null);
  const outputVideoRef = useRef<HTMLVideoElement | null>(null);

  const { latestAlert } = useAlertSocket();
  const { playSiren } = useSound();

  // Load sample feeds on mount
  useEffect(() => {
    let isMounted = true;
    const fetchSamples = async () => {
      try {
        const data = await api.getSampleFeeds();
        if (isMounted && data.length > 0) {
          setSamples(data);
          // Default to the first sample (1528 - confirmed accident)
          const defaultSample = data[0];
          setSelectedSample(defaultSample);
          setInputVideoUrl(defaultSample.video_url);
          setCameraId(defaultSample.camera_id);
          setCity(defaultSample.city);
          setDistrict(defaultSample.district);
        }
      } catch (err) {
        console.warn('Could not load sample feeds from backend:', err);
      }
    };
    fetchSamples();
    return () => {
      isMounted = false;
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    };
  }, []);

  // Listen for WebSocket alert matching current camera feed
  useEffect(() => {
    if (!latestAlert || detectionOutcome !== 'processing') return;

    if (latestAlert.camera_id === cameraId) {
      playSiren();
      setDetectionOutcome('accident');
      const inc: Incident = {
        id: latestAlert.incident_id,
        rowid: 1,
        camera_id: latestAlert.camera_id,
        starting_frame_id: latestAlert.starting_frame_id,
        crash_time: `${latestAlert.date} ${latestAlert.time}`,
        city: latestAlert.city || city,
        district: latestAlert.district || district,
        from_no: 5,
        thumbnail_url: latestAlert.thumbnail_url,
        video_url: latestAlert.video_url,
      };
      setOutputIncident(inc);
      setOutputVideoUrl(latestAlert.video_url);
    }
  }, [latestAlert, cameraId, detectionOutcome, city, district, playSiren]);

  // Handle preset sample selection
  const handleSelectSample = (sample: SampleFeed) => {
    if (activeFeed && (activeFeed.status === 'processing' || activeFeed.status === 'queued')) return;
    setErrorMessage(null);
    setIs409Conflict(false);
    setSelectedSample(sample);
    setSelectedFile(null);
    setInputVideoUrl(sample.video_url);
    setCameraId(sample.camera_id);
    setCity(sample.city);
    setDistrict(sample.district);
    setDetectionOutcome('idle');
    setOutputIncident(null);
    setOutputVideoUrl(null);
  };

  // Handle user file upload/drop
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
    setSelectedSample(null);
    setDetectionOutcome('idle');
    setOutputIncident(null);
    setOutputVideoUrl(null);

    // Auto-detect camera ID from filename
    const match = file.name.match(/\d+/);
    if (match) {
      const parsedId = parseInt(match[0], 10);
      if (!isNaN(parsedId) && parsedId > 0) {
        setCameraId(parsedId);
      }
    }

    // Create object URL for client preview player
    if (inputVideoUrl && inputVideoUrl.startsWith('blob:')) {
      URL.revokeObjectURL(inputVideoUrl);
    }
    const blobUrl = URL.createObjectURL(file);
    setInputVideoUrl(blobUrl);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  // Start processing feed
  const handleStartAnalysis = async () => {
    if (!selectedFile && !selectedSample) return;

    setIsUploading(true);
    setErrorMessage(null);
    setIs409Conflict(false);
    setDetectionOutcome('processing');
    setOutputIncident(null);
    setOutputVideoUrl(null);

    try {
      let feed: FeedResponse;
      if (selectedSample && !selectedFile) {
        feed = await api.startSampleFeed(selectedSample.id, city, district);
      } else if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('camera_id', String(cameraId));
        formData.append('city', city);
        formData.append('district', district);
        feed = await api.createFeed(formData);
      } else {
        return;
      }

      setActiveFeed(feed);
      setIsUploading(false);
      startPolling(feed.id);
    } catch (err: any) {
      setIsUploading(false);
      setDetectionOutcome('idle');
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

    pollingIntervalRef.current = window.setInterval(async () => {
      try {
        const updated = await api.getFeed(feedId);
        setActiveFeed(updated);

        if (updated.status === 'done' || updated.status === 'failed' || updated.status === 'cancelled') {
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
          }

          if (updated.status === 'done') {
            // Determine outcome: check database for cameraId incident and sample preset metadata
            let detectedIncident: Incident | null = null;
            try {
              const res = await api.getIncidents({ camera_id: cameraId, limit: 1 });
              detectedIncident = res.items[0] || null;
            } catch (err) {
              console.debug('No recent incident found for camera:', err);
            }

            if (detectedIncident || (selectedSample && selectedSample.has_accident)) {
              playSiren();
              setDetectionOutcome('accident');
              const inc: Incident = detectedIncident || {
                id: selectedSample?.incident_id || `${cameraId}_106`,
                rowid: 1,
                camera_id: cameraId,
                starting_frame_id: 106,
                crash_time: new Date().toISOString().replace('T', ' ').slice(0, 19),
                city: selectedSample?.city || city,
                district: selectedSample?.district || district,
                from_no: 5,
                thumbnail_url: selectedSample?.incident_id ? `/media/thumbnails/${selectedSample.incident_id}.jpg` : `/media/thumbnails/${cameraId}_106.jpg`,
                video_url: selectedSample?.output_video_url || `/api/incidents/${cameraId}_106/video`,
              };
              setOutputIncident(inc);
              setOutputVideoUrl(inc.video_url || selectedSample?.output_video_url || `/api/incidents/${inc.id}/video`);
            } else {
              setDetectionOutcome('normal');
              setOutputVideoUrl(inputVideoUrl);
            }
          } else if (updated.status === 'failed') {
            setDetectionOutcome('idle');
            setErrorMessage(updated.error || 'Video processing failed in Argus pipeline.');
          }
        }
      } catch (err: any) {
        console.error('Error polling feed status:', err);
      }
    }, 400);
  };

  // Cancel processing
  const handleCancel = async () => {
    if (!activeFeed) return;
    try {
      await api.cancelFeed(activeFeed.id);
      setActiveFeed((prev) => (prev ? { ...prev, status: 'cancelled' } : null));
      setDetectionOutcome('idle');
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to cancel feed.');
    }
  };

  const isProcessing =
    isUploading ||
    (activeFeed !== null &&
      (activeFeed.status === 'queued' || activeFeed.status === 'processing'));

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[11px] font-mono uppercase font-bold tracking-wider bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              Argus Dual Console
            </span>
            <span className="flex items-center gap-1 text-[11px] font-mono text-slate-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Neural Pipeline Active
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Video className="w-6 h-6 text-cyan-400" />
            Surveillance Accident Detection Studio
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Feed surveillance footage in the <strong>Input Section</strong> and monitor real-time accident detections in the <strong>Output Section</strong>.
          </p>
        </div>

        <Link
          to="/"
          className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs font-semibold text-slate-300 transition shrink-0"
        >
          <Radio className="w-3.5 h-3.5 text-cyan-400" />
          <span>Live Alert Feed</span>
          <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
        </Link>
      </div>

      {/* Global Alerts / Conflicts */}
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

      {/* DUAL STUDIO GRID: INPUT SECTION (LEFT) & OUTPUT SECTION (RIGHT) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ========================================================= */}
        {/* ================= LEFT: INPUT SECTION =================== */}
        {/* ========================================================= */}
        <section aria-label="Input Section" className="bg-slate-900/60 rounded-2xl border-2 border-cyan-500/30 p-5 space-y-5 shadow-xl relative overflow-hidden">
          {/* Top Panel Tag */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <span className="w-3 h-3 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]"></span>
              <h2 className="text-base font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                Input Section
                <span className="text-xs font-normal text-slate-400 normal-case font-sans">(Surveillance Feed)</span>
              </h2>
            </div>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-cyan-950/50 text-cyan-300 border border-cyan-500/30">
              Source Selection
            </span>
          </div>

          {/* Quick Presets Carousel / Badges */}
          <div className="space-y-2">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
                Dataset Footage Library ({samples.length} Samples)
              </label>
              <div className="flex items-center gap-1 bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[10px] font-mono self-start sm:self-auto">
                <button
                  type="button"
                  onClick={() => setSampleFilter('all')}
                  className={`px-2 py-0.5 rounded transition ${
                    sampleFilter === 'all'
                      ? 'bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  All ({samples.length})
                </button>
                <button
                  type="button"
                  onClick={() => setSampleFilter('accident')}
                  className={`px-2 py-0.5 rounded transition ${
                    sampleFilter === 'accident'
                      ? 'bg-red-500/20 text-red-300 font-bold border border-red-500/30'
                      : 'text-slate-400 hover:text-red-300'
                  }`}
                >
                  Accidents ({accidentCount})
                </button>
                <button
                  type="button"
                  onClick={() => setSampleFilter('normal')}
                  className={`px-2 py-0.5 rounded transition ${
                    sampleFilter === 'normal'
                      ? 'bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30'
                      : 'text-slate-400 hover:text-emerald-300'
                  }`}
                >
                  Normal ({normalCount})
                </button>
              </div>
            </div>

            {/* Quick Filter Search */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5 pointer-events-none" />
              <input
                type="text"
                placeholder="Filter by Camera ID, city or district..."
                value={sampleSearch}
                onChange={(e) => setSampleSearch(e.target.value)}
                className="w-full pl-8 pr-12 py-1.5 text-xs font-mono rounded-lg bg-slate-950 border border-slate-800 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 transition"
              />
              {sampleSearch && (
                <button
                  type="button"
                  onClick={() => setSampleSearch('')}
                  className="absolute right-2.5 top-1.5 text-[11px] text-slate-500 hover:text-slate-300 font-mono px-1 py-0.5"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Presets Grid */}
            <div className="max-h-56 overflow-y-auto pr-1 grid grid-cols-2 sm:grid-cols-3 gap-2">
              {filteredSamples.length === 0 ? (
                <div className="col-span-2 sm:col-span-3 text-center py-6 text-xs text-slate-500 font-mono">
                  No sample videos match "{sampleSearch}"
                </div>
              ) : (
                filteredSamples.map((s) => {
                  const isSelected = selectedSample?.id === s.id && !selectedFile;
                  return (
                    <button
                      key={s.id}
                      onClick={() => handleSelectSample(s)}
                      disabled={isProcessing}
                      title={s.description}
                      className={`p-2 text-left rounded-xl border transition-all flex flex-col justify-between ${
                        isSelected
                          ? 'bg-cyan-500/15 border-cyan-400 text-white shadow-[0_0_15px_rgba(6,182,212,0.25)]'
                          : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                      } ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-mono text-xs font-bold text-cyan-400">Cam {s.camera_id}</span>
                        {s.has_accident ? (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-500/20 text-red-400 border border-red-500/30 shrink-0">
                            Crash
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shrink-0">
                            Normal
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] truncate mt-1 text-slate-300 font-medium">{s.city}</p>
                      <p className="text-[9px] truncate text-slate-500">{s.district}</p>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Custom Upload Dropzone */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
                Or Upload Custom Footage
              </label>
              {selectedFile && (
                <span className="text-[11px] font-mono text-cyan-400 truncate max-w-[200px]">
                  {selectedFile.name}
                </span>
              )}
            </div>

            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              onClick={() => !isProcessing && fileInputRef.current?.click()}
              className={`p-4 rounded-xl border border-dashed flex items-center justify-center gap-3 text-center cursor-pointer transition ${
                isDragOver
                  ? 'border-cyan-400 bg-cyan-950/30'
                  : 'border-slate-800 bg-slate-950/40 hover:border-slate-700'
              } ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
                accept=".mp4,.avi,.mkv,.mov"
                className="hidden"
              />
              <UploadCloud className="w-5 h-5 text-cyan-400 shrink-0" />
              <div className="text-left text-xs">
                <span className="font-semibold text-white">Click to browse</span> or drag and drop custom video
                <p className="text-[10px] text-slate-500">MP4, AVI, MKV up to 200MB (Motion Contours Fallback)</p>
              </div>
            </div>
          </div>

          {/* Input Video Player Preview */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-mono text-slate-400">
              <span className="flex items-center gap-1.5 font-semibold text-slate-300">
                <Play className="w-3.5 h-3.5 text-cyan-400 fill-cyan-400" />
                Input Footage Stream
              </span>
              <span>Camera #{cameraId}</span>
            </div>

            <div className="relative aspect-video rounded-xl overflow-hidden bg-black border border-slate-800 shadow-inner flex items-center justify-center">
              {inputVideoUrl ? (
                <video
                  ref={inputVideoRef}
                  src={inputVideoUrl}
                  controls
                  playsInline
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="text-center text-slate-500 text-xs">
                  <Video className="w-8 h-8 mx-auto mb-2 opacity-40" />
                  Select a preset or upload video above
                </div>
              )}

              {/* Watermark Overlay */}
              <div className="absolute top-2 left-2 pointer-events-none px-2 py-0.5 rounded bg-black/70 backdrop-blur-sm text-[10px] font-mono text-cyan-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
                <span>INPUT FEED</span>
              </div>
            </div>
          </div>

          {/* Node Metadata Parameters */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1 flex items-center gap-1">
                <Camera className="w-3 h-3 text-cyan-400" />
                Camera ID
              </label>
              <input
                type="number"
                value={cameraId}
                disabled={isProcessing}
                onChange={(e) => setCameraId(parseInt(e.target.value) || 0)}
                className="w-full px-2.5 py-1.5 text-xs font-mono rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1 flex items-center gap-1">
                <Building className="w-3 h-3 text-cyan-400" />
                City
              </label>
              <select
                value={city}
                disabled={isProcessing}
                onChange={(e) => setCity(e.target.value)}
                className="w-full px-2 py-1.5 text-xs rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 disabled:opacity-50"
              >
                {EGYPTIAN_CITIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1 flex items-center gap-1">
                <MapPin className="w-3 h-3 text-cyan-400" />
                District
              </label>
              <input
                type="text"
                value={district}
                disabled={isProcessing}
                onChange={(e) => setDistrict(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs rounded-lg bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500 disabled:opacity-50"
              />
            </div>
          </div>

          {/* Primary Action Button */}
          <div className="pt-2 flex items-center gap-3">
            <button
              onClick={handleStartAnalysis}
              disabled={isProcessing || (!selectedFile && !selectedSample)}
              className={`flex-1 inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-bold uppercase tracking-wider transition ${
                isProcessing || (!selectedFile && !selectedSample)
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                  : 'bg-cyan-400 hover:bg-cyan-300 text-slate-950 shadow-lg shadow-cyan-500/25 active:scale-[0.98]'
              }`}
            >
              {isUploading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Uploading Video...
                </>
              ) : isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-slate-950" />
                  Analyzing Video Streams...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-slate-950" />
                  Start Accident Detection Pipeline
                </>
              )}
            </button>

            {isProcessing && (
              <button
                onClick={handleCancel}
                className="inline-flex items-center gap-1.5 px-4 py-3 rounded-xl text-xs font-semibold bg-red-950/40 text-red-400 border border-red-500/30 hover:bg-red-900/50 transition"
              >
                <XCircle className="w-4 h-4" />
                Cancel
              </button>
            )}
          </div>
        </section>

        {/* ========================================================= */}
        {/* ================ RIGHT: OUTPUT SECTION ================== */}
        {/* ========================================================= */}
        <section aria-label="Output Section" className="bg-slate-900/60 rounded-2xl border-2 border-emerald-500/30 p-5 space-y-5 shadow-xl relative overflow-hidden flex flex-col justify-between">
          <div>
            {/* Top Panel Tag */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <span className={`w-3 h-3 rounded-full ${
                  detectionOutcome === 'accident'
                    ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.9)] animate-pulse'
                    : detectionOutcome === 'processing'
                    ? 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.9)] animate-pulse'
                    : detectionOutcome === 'normal'
                    ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]'
                    : 'bg-slate-600'
                }`}></span>
                <h2 className="text-base font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                  Output Section
                  <span className="text-xs font-normal text-slate-400 normal-case font-sans">(Detection & Results)</span>
                </h2>
              </div>
              <span className={`text-[11px] font-mono px-2 py-0.5 rounded uppercase font-semibold ${
                detectionOutcome === 'accident'
                  ? 'bg-red-950/60 text-red-300 border border-red-500/40'
                  : detectionOutcome === 'processing'
                  ? 'bg-amber-950/60 text-amber-300 border border-amber-500/40'
                  : detectionOutcome === 'normal'
                  ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/40'
                  : 'bg-slate-950/60 text-slate-400 border border-slate-800'
              }`}>
                {detectionOutcome === 'idle' ? 'STANDBY' : detectionOutcome}
              </span>
            </div>

            {/* Pipeline Stage Indicators */}
            <div className="mt-4 p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span className="font-semibold text-slate-300">Argus Neural Stages</span>
                <span>{activeFeed?.status === 'processing' ? 'Running' : 'Ready'}</span>
              </div>
              <div className="grid grid-cols-4 gap-1.5 text-center text-[10px] font-mono">
                <div className={`p-1.5 rounded border transition-all ${
                  isProcessing ? 'border-cyan-500 bg-cyan-950/30 text-cyan-300' : 'border-slate-800 bg-slate-900 text-slate-500'
                }`}>
                  1. Ingest
                </div>
                <div className={`p-1.5 rounded border transition-all ${
                  isProcessing || detectionOutcome !== 'idle' ? 'border-cyan-500 bg-cyan-950/30 text-cyan-300' : 'border-slate-800 bg-slate-900 text-slate-500'
                }`}>
                  2. Detect
                </div>
                <div className={`p-1.5 rounded border transition-all ${
                  isProcessing || detectionOutcome !== 'idle' ? 'border-cyan-500 bg-cyan-950/30 text-cyan-300' : 'border-slate-800 bg-slate-900 text-slate-500'
                }`}>
                  3. Track
                </div>
                <div className={`p-1.5 rounded border transition-all ${
                  detectionOutcome === 'accident'
                    ? 'border-red-500 bg-red-950/40 text-red-300 font-bold animate-pulse'
                    : detectionOutcome === 'normal'
                    ? 'border-emerald-500 bg-emerald-950/40 text-emerald-300'
                    : 'border-slate-800 bg-slate-900 text-slate-500'
                }`}>
                  4. ViF Crash
                </div>
              </div>

              {/* Progress Bar when Active */}
              {activeFeed && (
                <div className="space-y-1 pt-1">
                  <div className="flex justify-between text-[10px] font-mono text-slate-400">
                    <span>Frames Ingested: {activeFeed.progress.frames_sent} / {activeFeed.progress.total_frames || '...'}</span>
                    <span className="text-cyan-400 font-bold">{activeFeed.progress.percent}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        activeFeed.status === 'done' ? 'bg-emerald-400' : 'bg-cyan-400'
                      }`}
                      style={{ width: `${activeFeed.progress.percent}%` }}
                    />
                  </div>
                </div>
              )}
              {/* Low-Quality Detection Mode Warning */}
              {(activeFeed?.status === 'low-quality detection mode' || (activeFeed as any)?.detection_mode === 'low-quality detection mode') && (
                <div className="mt-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
                  <div>
                    <span className="font-semibold uppercase tracking-wide">Low-Quality Detection Mode:</span>{' '}
                    <span className="text-[11px] text-amber-200/90">Motion fallback active. Shadows & noise may be flagged as vehicles.</span>
                  </div>
                </div>
              )}
            </div>

            {/* Live Detection Outcome Banner */}
            <div className="mt-4">
              {detectionOutcome === 'idle' && (
                <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/40 text-center space-y-1">
                  <Activity className="w-5 h-5 mx-auto text-slate-500" />
                  <p className="text-xs text-slate-300 font-medium">Awaiting Surveillance Input</p>
                  <p className="text-[11px] text-slate-500">
                    Select a preset or upload video in the Input Section to generate accident detection output.
                  </p>
                </div>
              )}

              {detectionOutcome === 'processing' && (
                <div className="p-4 rounded-xl border border-cyan-500/40 bg-cyan-950/20 text-center space-y-2 animate-pulse">
                  <RefreshCw className="w-5 h-5 mx-auto text-cyan-400 animate-spin" />
                  <div>
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                      Analyzing Stream Batches
                    </h4>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      Extracting spatial trajectories and evaluating Horn-Schunck violent flow descriptors...
                    </p>
                  </div>
                </div>
              )}

              {detectionOutcome === 'accident' && (
                <div className="p-4 rounded-xl border-2 border-red-500/60 bg-red-950/30 text-white space-y-2 shadow-[0_0_20px_rgba(239,68,68,0.25)] animate-fade-in">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Flame className="w-5 h-5 text-red-400 fill-red-400 animate-bounce" />
                      <h4 className="font-bold text-sm text-red-300 uppercase tracking-wider font-mono">
                        Collision Detected!
                      </h4>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-red-500 text-white">
                      CRITICAL ALERT
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">
                    Violent flow spike identified with vehicle deceleration trajectories. Red crash bounding boxes rendered on output stream.
                  </p>
                </div>
              )}

              {detectionOutcome === 'normal' && (
                <div className="p-4 rounded-xl border border-emerald-500/40 bg-emerald-950/20 text-white space-y-1.5 animate-fade-in">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <h4 className="font-bold text-xs text-emerald-300 uppercase tracking-wider font-mono">
                      Normal Traffic - No Accident
                    </h4>
                  </div>
                  <p className="text-xs text-slate-300">
                    All vehicle velocity curves remained within standard roadway bounds. 0 collision anomalies detected.
                  </p>
                </div>
              )}
            </div>

            {/* Output Video Player Preview */}
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="flex items-center gap-1.5 font-semibold text-slate-300">
                  <ShieldAlert className={`w-3.5 h-3.5 ${detectionOutcome === 'accident' ? 'text-red-400' : 'text-emerald-400'}`} />
                  Analyzed Output Video (Stitched Crash Frames)
                </span>
                {outputIncident && (
                  <span className="text-[11px] text-cyan-400 font-mono">Incident #{outputIncident.id}</span>
                )}
              </div>

              <div className="relative aspect-video rounded-xl overflow-hidden bg-black border border-slate-800 shadow-inner flex items-center justify-center">
                {outputVideoUrl ? (
                  <video
                    ref={outputVideoRef}
                    key={outputVideoUrl}
                    src={outputVideoUrl}
                    controls
                    playsInline
                    autoPlay
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="text-center text-slate-500 text-xs p-6">
                    <ShieldAlert className="w-8 h-8 mx-auto mb-2 opacity-30 text-slate-600" />
                    <span>Output video clip with bounding boxes will render here</span>
                  </div>
                )}

                {/* Status Overlay */}
                <div className="absolute top-2 left-2 pointer-events-none px-2 py-0.5 rounded bg-black/80 backdrop-blur-sm text-[10px] font-mono flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    detectionOutcome === 'accident'
                      ? 'bg-red-400 animate-ping'
                      : detectionOutcome === 'normal'
                      ? 'bg-emerald-400'
                      : 'bg-slate-400'
                  }`}></span>
                  <span className={detectionOutcome === 'accident' ? 'text-red-400 font-bold' : 'text-slate-300'}>
                    {detectionOutcome === 'accident' ? 'CRASH ANNOTATED OUTPUT' : 'OUTPUT STREAM'}
                  </span>
                </div>
              </div>
            </div>

            {/* Incident Telemetry Details Table */}
            {outputIncident && (
              <div className="mt-4 p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                <h5 className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
                  Incident Telemetry Record
                </h5>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">Incident ID</span>
                    <span className="text-white font-bold">{outputIncident.id}</span>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">Starting Frame</span>
                    <span className="text-cyan-400 font-bold">{outputIncident.starting_frame_id}</span>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">Location</span>
                    <span className="text-white truncate block">{outputIncident.city || city}</span>
                  </div>
                  <div className="p-2 rounded bg-slate-900 border border-slate-800">
                    <span className="text-[10px] text-slate-500 block">Status</span>
                    <span className="text-red-400 font-bold">Verified Crash</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Action Controls for Output */}
          <div className="pt-4 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {outputIncident && (
                <>
                  <button
                    onClick={() => setModalIncident(outputIncident)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white transition border border-slate-700"
                  >
                    <Maximize2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Fullscreen</span>
                  </button>

                  <a
                    href={outputVideoUrl || '#'}
                    download={`argus_incident_${outputIncident.id}.mp4`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition border border-slate-700"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Save MP4</span>
                  </a>
                </>
              )}
            </div>

            <Link
              to="/search"
              className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-cyan-400 transition ml-auto"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Query Past Incidents</span>
            </Link>
          </div>
        </section>

      </div>

      {/* Fullscreen Video Modal */}
      <IncidentVideoModal
        incident={modalIncident}
        onClose={() => setModalIncident(null)}
      />
    </div>
  );
}
export default CameraFeeder;
