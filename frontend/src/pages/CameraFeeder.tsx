import { useState, useRef, useEffect, useMemo, Fragment } from 'react';
import { Link } from 'react-router-dom';
import {
  UploadCloud,
  Video,
  Play,
  X,
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
  ChevronLeft,
  Radio,
  Info,
  Columns,
  Eye,
  HelpCircle,
  SlidersHorizontal,
  PlayCircle,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';
import { api, type FeedResponse, type Incident, type SampleItem } from '@/lib/api';
import { classifyBatchOutcome, generateBatchResultsCsv, downloadCsv, type BatchResultItem } from '@/lib/batchRunner';
import { useAlertSocket } from '@/hooks/useAlertSocket';
import { useSound } from '@/contexts/SoundContext';
import { IncidentVideoModal } from '@/components/IncidentVideoModal';
import { ModelScoreBreakdown } from '@/components/ModelScoreBreakdown';
import { VideoPlayer } from '@/components/VideoPlayer';
import { formatScore, scorerLabel } from '@/lib/modelFormatters';

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

function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds)) return '--';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || isNaN(bytes)) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function CameraFeeder() {
  // Input State
  const [samples, setSamples] = useState<SampleItem[]>([]);
  const [selectedSample, setSelectedSample] = useState<SampleItem | null>(null);
  const [previewSample, setPreviewSample] = useState<SampleItem | null>(null);
  const [isLoadingSamples, setIsLoadingSamples] = useState<boolean>(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [inputVideoUrl, setInputVideoUrl] = useState<string | null>(null);
  const [cameraId, setCameraId] = useState<number>(1528);
  const [city, setCity] = useState<string>('Shibin El Kom');
  const [district, setDistrict] = useState<string>('District 13');
  const [sampleFilter, setSampleFilter] = useState<'all' | 'accident' | 'normal' | 'unknown'>('all');
  const [sampleSearch, setSampleSearch] = useState<string>('');
  const [sampleSort, setSampleSort] = useState<'name-asc' | 'name-desc' | 'duration-desc' | 'duration-asc' | 'size-desc'>('name-asc');
  const [page, setPage] = useState<number>(1);
  const PAGE_SIZE = 12;

  const accidentCount = useMemo(() => samples.filter((s) => s.expected_label === 'accident').length, [samples]);
  const normalCount = useMemo(() => samples.filter((s) => s.expected_label === 'normal').length, [samples]);
  const unknownCount = useMemo(() => samples.filter((s) => s.expected_label === 'unknown').length, [samples]);

  const filteredAndSortedSamples = useMemo(() => {
    let result = samples.filter((s) => {
      if (sampleFilter !== 'all' && s.expected_label !== sampleFilter) return false;
      if (sampleSearch.trim()) {
        const q = sampleSearch.toLowerCase();
        const matchName = s.name.toLowerCase().includes(q);
        const matchPath = s.relative_path.toLowerCase().includes(q);
        const matchCam = s.camera_id != null && String(s.camera_id).includes(q);
        const matchCity = s.city ? s.city.toLowerCase().includes(q) : false;
        const matchDistrict = s.district ? s.district.toLowerCase().includes(q) : false;
        const matchNotes = s.notes ? s.notes.toLowerCase().includes(q) : false;
        return matchName || matchPath || matchCam || matchCity || matchDistrict || matchNotes;
      }
      return true;
    });

    result.sort((a, b) => {
      switch (sampleSort) {
        case 'name-asc':
          return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
        case 'name-desc':
          return b.name.localeCompare(a.name, undefined, { numeric: true, sensitivity: 'base' });
        case 'duration-desc':
          return (b.duration_s ?? 0) - (a.duration_s ?? 0);
        case 'duration-asc':
          return (a.duration_s ?? 0) - (b.duration_s ?? 0);
        case 'size-desc':
          return b.size_bytes - a.size_bytes;
        default:
          return 0;
      }
    });

    return result;
  }, [samples, sampleFilter, sampleSearch, sampleSort]);

  const totalPages = Math.max(1, Math.ceil(filteredAndSortedSamples.length / PAGE_SIZE));
  const paginatedSamples = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filteredAndSortedSamples.slice(start, start + PAGE_SIZE);
  }, [filteredAndSortedSamples, page]);

  // Close preview modal on Escape
  useEffect(() => {
    if (!previewSample) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPreviewSample(null);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [previewSample]);

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
  const [isCompareModels, setIsCompareModels] = useState<boolean>(false);
  const [showDetectorHelpModal, setShowDetectorHelpModal] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pollingIntervalRef = useRef<number | null>(null);

  // Batch Test Runner State
  const [isBatchRunning, setIsBatchRunning] = useState<boolean>(false);
  const [showBatchConfirmModal, setShowBatchConfirmModal] = useState<boolean>(false);
  const [batchQueue, setBatchQueue] = useState<SampleItem[]>([]);
  const [batchCurrentIndex, setBatchCurrentIndex] = useState<number>(0);
  const [batchCurrentSample, setBatchCurrentSample] = useState<SampleItem | null>(null);
  const [batchCurrentFeed, setBatchCurrentFeed] = useState<FeedResponse | null>(null);
  const [batchElapsedSeconds, setBatchElapsedSeconds] = useState<number>(0);
  const [batchResults, setBatchResults] = useState<BatchResultItem[]>([]);
  const [activeConfig, setActiveConfig] = useState<any>(null);
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);

  const cancelBatchRef = useRef<boolean>(false);
  const currentFeedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (typeof api.getActiveConfig === 'function') {
      api.getActiveConfig().then(setActiveConfig).catch(() => {});
    }
  }, []);

  // Batch elapsed seconds counter
  useEffect(() => {
    let interval: number | null = null;
    if (isBatchRunning) {
      interval = window.setInterval(() => {
        setBatchElapsedSeconds((s) => s + 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isBatchRunning]);

  const batchEtaSeconds = useMemo(() => {
    if (!isBatchRunning || batchQueue.length === 0) return 0;
    if (batchCurrentIndex <= 1 || batchElapsedSeconds === 0) {
      const remainingClips = batchQueue.slice(Math.max(0, batchCurrentIndex - 1));
      const totalRemainingDur = remainingClips.reduce((acc, c) => acc + (c.duration_s || 15), 0);
      return Math.round(totalRemainingDur);
    }
    const completedCount = batchCurrentIndex - 1;
    const avgTimePerClip = batchElapsedSeconds / completedCount;
    const remainingCount = batchQueue.length - completedCount;
    return Math.round(avgTimePerClip * remainingCount);
  }, [isBatchRunning, batchQueue, batchCurrentIndex, batchElapsedSeconds]);

  const batchQueueEstimatedDuration = useMemo(() => {
    return batchQueue.reduce((acc, c) => acc + (c.duration_s || 15), 0);
  }, [batchQueue]);

  const handleOpenBatchConfirm = () => {
    if (isBatchRunning || isProcessing) return;
    setBatchQueue([...filteredAndSortedSamples]);
    setShowBatchConfirmModal(true);
  };

  const handleStartBatch = async () => {
    setShowBatchConfirmModal(false);
    if (batchQueue.length === 0) return;

    cancelBatchRef.current = false;
    setBatchElapsedSeconds(0);
    setBatchResults([]);
    setIsBatchRunning(true);

    const queue = [...batchQueue];
    const results: BatchResultItem[] = [];

    for (let i = 0; i < queue.length; i++) {
      if (cancelBatchRef.current) break;

      const sample = queue[i];
      setBatchCurrentIndex(i + 1);
      setBatchCurrentSample(sample);
      setBatchCurrentFeed(null);

      const clipStartTime = performance.now();
      let feed: FeedResponse;

      try {
        const camId = sample.camera_id || (sample.name.match(/\d+/) ? parseInt(sample.name.match(/\d+/)[0], 10) : 1528);
        const sampleCity = sample.city || 'Cairo';
        const sampleDistrict = sample.district || 'District 1';

        if (typeof api.startFeedFromSample === 'function') {
          feed = await api.startFeedFromSample(sample.id, camId, sampleCity, sampleDistrict);
        } else {
          feed = await api.startSampleFeed(sample.id, sampleCity, sampleDistrict);
        }
        currentFeedIdRef.current = feed.id;
        setBatchCurrentFeed(feed);
      } catch (err: any) {
        const procTime = Math.round((performance.now() - clipStartTime) / 100) / 10;
        results.push({
          id: sample.id,
          name: sample.name,
          relative_path: sample.relative_path,
          expected_label: sample.expected_label,
          label_source: sample.label_source || 'unknown',
          detection_quality: 'unknown',
          vehicles_detected_count: 0,
          cause_category: null,
          alert_raised: false,
          time_to_first_alert_s: null,
          processing_time_s: procTime,
          status: 'failed',
          outcome: classifyBatchOutcome(sample.expected_label, false),
          error: err.message || 'Failed to start feed',
          trace_summary: null,
        });
        setBatchResults([...results]);
        continue;
      }

      // Poll feed until terminal status
      let terminalFeed = feed;
      while (true) {
        if (cancelBatchRef.current) {
          try {
            await api.cancelFeed(feed.id);
          } catch {
            // ignore
          }
          terminalFeed = { ...feed, status: 'cancelled' };
          break;
        }

        await new Promise((r) => setTimeout(r, 400));
        try {
          const updated = await api.getFeed(feed.id);
          terminalFeed = updated;
          setBatchCurrentFeed(updated);
          if (['done', 'failed', 'cancelled'].includes(updated.status)) {
            break;
          }
        } catch {
          // ignore transient poll error
        }
      }

      const procTime = Math.round((performance.now() - clipStartTime) / 100) / 10;
      if (terminalFeed.status === 'cancelled') {
        results.push({
          id: sample.id,
          name: sample.name,
          relative_path: sample.relative_path,
          expected_label: sample.expected_label,
          label_source: sample.label_source || 'unknown',
          detection_quality: 'unknown',
          vehicles_detected_count: 0,
          cause_category: null,
          alert_raised: false,
          time_to_first_alert_s: null,
          processing_time_s: procTime,
          status: 'cancelled',
          outcome: classifyBatchOutcome(sample.expected_label, false),
          trace_summary: null,
        });
        setBatchResults([...results]);
        break; // Stop remaining queue on cancel
      } else if (terminalFeed.status === 'failed') {
        results.push({
          id: sample.id,
          name: sample.name,
          relative_path: sample.relative_path,
          expected_label: sample.expected_label,
          label_source: sample.label_source || 'unknown',
          detection_quality: 'unknown',
          vehicles_detected_count: 0,
          cause_category: null,
          alert_raised: false,
          time_to_first_alert_s: null,
          processing_time_s: procTime,
          status: 'failed',
          outcome: classifyBatchOutcome(sample.expected_label, false),
          error: terminalFeed.error || 'Pipeline error',
          trace_summary: null,
        });
        setBatchResults([...results]);
      } else {
        // Status is 'done'
        let incId: string | null = null;
        let detectedIncident: Incident | null = null;
        let alertRaised = false;

        if (Array.isArray(terminalFeed.detected_incidents)) {
          if (terminalFeed.detected_incidents.length > 0) {
            incId = terminalFeed.detected_incidents[0];
            alertRaised = true;
            try {
              detectedIncident = await api.getIncident(incId);
            } catch {
              // ignore
            }
          } else if ((terminalFeed.anomalies_detected ?? 0) > 0) {
            alertRaised = true;
          }
        } else {
          // Fallback when detected_incidents array is not provided by mock or legacy endpoint
          try {
            const incRes = await api.getIncidents({ camera_id: sample.camera_id || 1528, limit: 1 });
            detectedIncident = incRes.items[0] || null;
            if (detectedIncident) {
              incId = detectedIncident.id;
            }
          } catch {
            // ignore
          }
          alertRaised = !!detectedIncident || ((terminalFeed as any).anomalies_detected > 0);
        }

        let alertTime: number | null = null;
        if (detectedIncident?.starting_frame_id != null) {
          const fps = sample.fps || 30;
          alertTime = Math.round((detectedIncident.starting_frame_id / fps) * 10) / 10;
        }

        let traceSummary = null;
        let causeCategory: string | null = null;
        try {
          if (typeof api.getRunTrace === 'function') {
            const traceResp = await api.getRunTrace(sample.id);
            if (traceResp && traceResp.has_trace && traceResp.summary) {
              traceSummary = traceResp.summary;
              causeCategory = traceResp.summary.primary_cause || null;
            }
          }
        } catch {
          traceSummary = null;
        }

        const quality = terminalFeed?.detection_quality || (sample.has_box_file ? 'reference' : 'motion_fallback');
        const vCount = terminalFeed?.vehicles_detected_count ?? traceSummary?.max_trackers ?? 0;
        const outcome = classifyBatchOutcome(sample.expected_label, alertRaised, quality, vCount);
        results.push({
          id: sample.id,
          name: sample.name,
          relative_path: sample.relative_path,
          expected_label: sample.expected_label,
          label_source: sample.label_source || 'unknown',
          detection_quality: quality,
          vehicles_detected_count: vCount,
          cause_category: causeCategory,
          alert_raised: alertRaised,
          time_to_first_alert_s: alertTime,
          processing_time_s: procTime,
          status: 'completed',
          outcome,
          incident_id: detectedIncident?.id || incId || undefined,
          video_url: detectedIncident?.video_url || sample.video_url,
          trace_summary: traceSummary,
        });
        setBatchResults([...results]);
      }
    }

    setIsBatchRunning(false);
    currentFeedIdRef.current = null;
  };

  const handleCancelBatch = async () => {
    cancelBatchRef.current = true;
    if (currentFeedIdRef.current) {
      try {
        await api.cancelFeed(currentFeedIdRef.current);
      } catch (e) {
        console.warn('Failed to cancel active batch feed:', e);
      }
    }
  };

  const handleExportCsv = () => {
    if (batchResults.length === 0) return;
    const csv = generateBatchResultsCsv(batchResults);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    downloadCsv(`argus_batch_test_${timestamp}.csv`, csv);
  };

  const { latestAlert } = useAlertSocket();
  const { playSiren } = useSound();

  // Load sample feeds on mount
  useEffect(() => {
    let isMounted = true;
    const fetchSamples = async () => {
      setIsLoadingSamples(true);
      try {
        let items: SampleItem[] = [];
        if (typeof api.getSamples === 'function') {
          try {
            items = await api.getSamples();
          } catch (e) {
            console.warn('api.getSamples failed, falling back to getSampleFeeds', e);
          }
        }

        if (!items || items.length === 0) {
          if (typeof api.getSampleFeeds === 'function') {
            const legacy = await api.getSampleFeeds();
            items = legacy.map((s) => ({
              id: s.id,
              name: s.label || s.filename,
              relative_path: s.filename,
              size_bytes: 0,
              duration_s: null,
              resolution: null,
              fps: null,
              thumbnail_url: s.output_video_url || s.video_url,
              video_url: s.video_url,
              expected_label: s.has_accident ? 'accident' : 'normal',
              camera_id: s.camera_id,
              city: s.city,
              district: s.district,
              notes: s.description,
              has_accident: s.has_accident,
              incident_id: s.incident_id,
              output_video_url: s.output_video_url,
            })) as any;
          }
        }

        if (isMounted && items && items.length > 0) {
          setSamples(items);
          // Default to the first sample or 1528
          const defaultSample = items.find((s) => s.id.includes('1528') || s.name.includes('1528')) || items[0];
          setSelectedSample(defaultSample);
          setInputVideoUrl(defaultSample.video_url);
          if (defaultSample.camera_id) setCameraId(defaultSample.camera_id);
          if (defaultSample.city) setCity(defaultSample.city);
          if (defaultSample.district) setDistrict(defaultSample.district);
        }
      } catch (err) {
        console.warn('Could not load sample feeds from backend:', err);
      } finally {
        if (isMounted) setIsLoadingSamples(false);
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
        model_scores: latestAlert.model_scores || null,
      };
      setOutputIncident(inc);
      setOutputVideoUrl(latestAlert.video_url);
    }
  }, [latestAlert, cameraId, detectionOutcome, city, district, playSiren]);

  // Handle preset sample selection
  const handleSelectSample = (sample: SampleItem) => {
    if (activeFeed && (activeFeed.status === 'processing' || activeFeed.status === 'queued')) return;
    setErrorMessage(null);
    setIs409Conflict(false);
    setSelectedSample(sample);
    setSelectedFile(null);
    setInputVideoUrl(sample.video_url);
    if (sample.camera_id) {
      setCameraId(sample.camera_id);
    } else {
      const match = sample.name.match(/\d+/);
      if (match) {
        const parsed = parseInt(match[0], 10);
        if (!isNaN(parsed) && parsed > 0) setCameraId(parsed);
      }
    }
    if (sample.city) setCity(sample.city);
    if (sample.district) setDistrict(sample.district);
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
        if (typeof api.startFeedFromSample === 'function') {
          feed = await api.startFeedFromSample(selectedSample.id, cameraId, city, district);
        } else {
          feed = await api.startSampleFeed(selectedSample.id, city, district);
        }
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
      if (msg.includes('currently running') || msg.includes('409') || msg.includes('busy')) {
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
            // Determine outcome from feed detection results
            let detectedIncident: Incident | null = null;
            let hasDetectedIncidents = false;

            if (Array.isArray(updated.detected_incidents)) {
              if (updated.detected_incidents.length > 0) {
                hasDetectedIncidents = true;
                const incId = updated.detected_incidents[0];
                try {
                  detectedIncident = await api.getIncident(incId);
                } catch (err) {
                  console.debug('Failed to fetch detected incident details:', err);
                }
              }
            } else {
              // Fallback when detected_incidents array is not provided by mock or legacy endpoint
              try {
                const res = await api.getIncidents({ camera_id: cameraId, limit: 1 });
                detectedIncident = res.items[0] || null;
                hasDetectedIncidents = !!detectedIncident;
              } catch (err) {
                console.debug('No recent incident found for camera:', err);
              }
            }

            if (detectedIncident || hasDetectedIncidents) {
              playSiren();
              setDetectionOutcome('accident');
              if (detectedIncident) {
                setOutputIncident(detectedIncident);
                setOutputVideoUrl(detectedIncident.video_url || `/api/incidents/${detectedIncident.id}/video`);
              } else if (Array.isArray(updated.detected_incidents) && updated.detected_incidents[0]) {
                setOutputIncident(null);
                setOutputVideoUrl(`/api/incidents/${updated.detected_incidents[0]}/video`);
              }
            } else {
              setDetectionOutcome('normal');
              setOutputIncident(null);
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

  // Re-run previously uploaded feed without re-uploading bytes
  const handleRerunFeed = async () => {
    if (!activeFeed?.id || isProcessing) return;
    setDetectionOutcome('processing');
    setErrorMessage(null);
    try {
      const resp = await api.rerunFeed(activeFeed.id);
      setActiveFeed(resp);
      currentFeedIdRef.current = resp.id;

      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = window.setInterval(async () => {
        try {
          const updated = await api.getFeed(resp.id);
          setActiveFeed(updated);
          if (['done', 'failed', 'cancelled'].includes(updated.status)) {
            if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
            if (updated.status === 'done') {
              let detectedIncident: Incident | null = null;
              let hasDetectedIncidents = false;
              if (Array.isArray(updated.detected_incidents) && updated.detected_incidents.length > 0) {
                const incId = updated.detected_incidents[0];
                try {
                  detectedIncident = await api.getIncident(incId);
                  hasDetectedIncidents = true;
                } catch (err) {
                  console.debug('Failed to fetch detected incident details:', err);
                }
              }

              if (detectedIncident || hasDetectedIncidents) {
                playSiren();
                setDetectionOutcome('accident');
                if (detectedIncident) {
                  setOutputIncident(detectedIncident);
                  setOutputVideoUrl(detectedIncident.video_url || `/api/incidents/${detectedIncident.id}/video`);
                }
              } else {
                setDetectionOutcome('normal');
                setOutputIncident(null);
                setOutputVideoUrl(inputVideoUrl);
              }
            } else if (updated.status === 'failed') {
              setDetectionOutcome('idle');
              setErrorMessage(updated.error || 'Video replay failed in Argus pipeline.');
            }
          }
        } catch (err: any) {
          console.error('Error polling replay feed status:', err);
        }
      }, 400);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to replay feed.');
      setDetectionOutcome('idle');
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

      {/* Degraded Pipeline Mode Advisory Banner */}
      {activeFeed?.degraded && (
        <div
          data-testid="feed-degraded-banner"
          role="status"
          className="p-4 rounded-xl border bg-amber-950/30 border-amber-500/50 text-amber-300 flex items-center gap-3 text-xs"
        >
          <AlertTriangle className="w-5 h-5 shrink-0 text-amber-400" />
          <div>
            <span className="font-semibold uppercase tracking-wider font-mono">Degraded Mode:</span>{' '}
            Running with fewer models than configured. Alerts may be less reliable.
          </div>
        </div>
      )}

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

          {/* Sample Footage Gallery */}
          <div className="space-y-3">
            {/* Header with Title, Filter Chips, and Run Batch Button */}
            <div className="flex flex-col gap-2.5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
                  Sample Footage Catalog ({samples.length} Clips)
                </label>
                <button
                  type="button"
                  data-testid="batch-run-btn"
                  onClick={handleOpenBatchConfirm}
                  disabled={isBatchRunning || isProcessing || filteredAndSortedSamples.length === 0}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold font-mono uppercase tracking-wider bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 active:scale-[0.98] transition disabled:opacity-50 disabled:cursor-not-allowed self-start sm:self-auto"
                >
                  <PlayCircle className="w-3.5 h-3.5 text-cyan-400" />
                  <span>
                    {filteredAndSortedSamples.length === samples.length
                      ? `Run All (${samples.length})`
                      : `Run Filtered (${filteredAndSortedSamples.length})`}
                  </span>
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-1 bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[10px] font-mono self-start sm:self-auto">
                <button
                  type="button"
                  data-testid="sample-filter-all"
                  onClick={() => {
                    setSampleFilter('all');
                    setPage(1);
                  }}
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
                  data-testid="sample-filter-accident"
                  onClick={() => {
                    setSampleFilter('accident');
                    setPage(1);
                  }}
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
                  data-testid="sample-filter-normal"
                  onClick={() => {
                    setSampleFilter('normal');
                    setPage(1);
                  }}
                  className={`px-2 py-0.5 rounded transition ${
                    sampleFilter === 'normal'
                      ? 'bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/30'
                      : 'text-slate-400 hover:text-emerald-300'
                  }`}
                >
                  Normal ({normalCount})
                </button>
                <button
                  type="button"
                  data-testid="sample-filter-unknown"
                  onClick={() => {
                    setSampleFilter('unknown');
                    setPage(1);
                  }}
                  className={`px-2 py-0.5 rounded transition ${
                    sampleFilter === 'unknown'
                      ? 'bg-slate-700/50 text-slate-200 font-bold border border-slate-600'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Unlabeled ({unknownCount})
                </button>
              </div>
            </div>

            {/* Search and Sort Toolbar */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5 pointer-events-none" />
                <input
                  type="text"
                  data-testid="sample-search-input"
                  placeholder="Search by name, path, camera, location..."
                  value={sampleSearch}
                  onChange={(e) => {
                    setSampleSearch(e.target.value);
                    setPage(1);
                  }}
                  className="w-full pl-8 pr-12 py-1.5 text-xs font-mono rounded-lg bg-slate-950 border border-slate-800 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 transition"
                />
                {sampleSearch && (
                  <button
                    type="button"
                    onClick={() => {
                      setSampleSearch('');
                      setPage(1);
                    }}
                    className="absolute right-2.5 top-1.5 text-[11px] text-slate-500 hover:text-slate-300 font-mono px-1 py-0.5"
                  >
                    Clear
                  </button>
                )}
              </div>

              <div className="flex items-center gap-1.5 shrink-0 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1">
                <SlidersHorizontal className="w-3 h-3 text-slate-400" />
                <span className="text-[10px] font-mono text-slate-400">Sort:</span>
                <select
                  data-testid="sample-sort-select"
                  value={sampleSort}
                  onChange={(e) => {
                    setSampleSort(e.target.value as any);
                    setPage(1);
                  }}
                  className="bg-transparent text-xs font-mono text-slate-200 focus:outline-none cursor-pointer"
                >
                  <option value="name-asc" className="bg-slate-900 text-slate-200">Name (A → Z)</option>
                  <option value="name-desc" className="bg-slate-900 text-slate-200">Name (Z → A)</option>
                  <option value="duration-desc" className="bg-slate-900 text-slate-200">Duration (Longest)</option>
                  <option value="duration-asc" className="bg-slate-900 text-slate-200">Duration (Shortest)</option>
                  <option value="size-desc" className="bg-slate-900 text-slate-200">Size (Largest)</option>
                </select>
              </div>
            </div>

            {/* Gallery Grid */}
            <div className="max-h-80 overflow-y-auto pr-1">
              {isLoadingSamples ? (
                <div data-testid="samples-loading" className="py-12 text-center text-xs text-slate-400 font-mono space-y-2">
                  <RefreshCw className="w-5 h-5 mx-auto animate-spin text-cyan-400" />
                  <p>Loading video sample catalog...</p>
                </div>
              ) : filteredAndSortedSamples.length === 0 ? (
                <div className="py-10 text-center text-xs text-slate-500 font-mono border border-dashed border-slate-800 rounded-xl">
                  No sample videos match "{sampleSearch}"
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-2.5">
                  {paginatedSamples.map((s) => {
                    const isSelected = selectedSample?.id === s.id && !selectedFile;
                    return (
                      <div
                        key={s.id}
                        data-testid={`sample-card-${s.id}`}
                        role="button"
                        tabIndex={0}
                        aria-selected={isSelected}
                        aria-label={`Select sample ${s.name}`}
                        onClick={() => handleSelectSample(s)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handleSelectSample(s);
                          }
                        }}
                        className={`group relative rounded-xl border p-2 transition-all cursor-pointer flex flex-col justify-between motion-reduce:transition-none focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 ${
                          isSelected
                            ? 'bg-cyan-500/15 border-cyan-400 text-white shadow-[0_0_15px_rgba(6,182,212,0.25)] ring-1 ring-cyan-400/50'
                            : 'bg-slate-950/70 border-slate-800 hover:border-slate-700 text-slate-300 hover:bg-slate-900/60'
                        } ${isProcessing ? 'opacity-60 cursor-not-allowed' : ''}`}
                      >
                        {/* Thumbnail & Badges */}
                        <div className="relative aspect-video w-full rounded-lg overflow-hidden bg-black border border-slate-800/80 mb-1.5 flex items-center justify-center">
                          <img
                            src={s.thumbnail_url}
                            alt={s.name}
                            loading="lazy"
                            onError={(e) => {
                              (e.currentTarget as HTMLImageElement).style.display = 'none';
                            }}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 motion-reduce:transform-none"
                          />

                          {/* Preview Button */}
                          <button
                            type="button"
                            data-testid={`sample-preview-btn-${s.id}`}
                            aria-label={`Preview ${s.name}`}
                            title="Preview raw video stream"
                            onClick={(e) => {
                              e.stopPropagation();
                              setPreviewSample(s);
                            }}
                            className="absolute top-1.5 left-1.5 p-1 rounded bg-black/80 hover:bg-cyan-500 hover:text-slate-950 text-slate-300 border border-slate-700/80 transition opacity-85 group-hover:opacity-100 z-10"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>

                          {/* Expected Label Badge */}
                          <div className="absolute top-1.5 right-1.5 z-10">
                            {s.expected_label === 'accident' && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-red-950/90 text-red-300 border border-red-500/50 shadow-sm">
                                <Flame className="w-2.5 h-2.5 text-red-400 fill-red-400" />
                                <span>Accident</span>
                              </span>
                            )}
                            {s.expected_label === 'normal' && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-emerald-950/90 text-emerald-300 border border-emerald-500/50 shadow-sm">
                                <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" />
                                <span>Normal</span>
                              </span>
                            )}
                            {s.expected_label === 'unknown' && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-medium bg-slate-900/90 text-slate-300 border border-slate-700 shadow-sm">
                                <HelpCircle className="w-2.5 h-2.5 text-slate-400" />
                                <span>Unlabeled</span>
                              </span>
                            )}
                          </div>

                          {/* Duration & Resolution Overlay */}
                          <div className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/80 text-[9px] font-mono text-slate-300 flex items-center gap-1 border border-slate-800">
                            {s.duration_s != null && <span>{formatDuration(s.duration_s)}</span>}
                            {s.resolution && (
                              <>
                                <span className="text-slate-600">•</span>
                                <span>{s.resolution}</span>
                              </>
                            )}
                          </div>
                        </div>

                        {/* Card Meta */}
                        <div className="space-y-0.5">
                          <div className="flex items-center justify-between gap-1">
                            <h3 className="text-xs font-semibold text-white truncate" title={s.name}>
                              {s.name}
                            </h3>
                            {s.camera_id != null && (
                              <span className="text-[10px] font-mono text-cyan-400 font-bold shrink-0">
                                Cam {s.camera_id}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                            <span className="truncate max-w-[120px]" title={s.relative_path}>
                              {s.relative_path.split('/')[0]}
                            </span>
                            <span>{formatBytes(s.size_bytes)}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-1 text-xs font-mono text-slate-400 border-t border-slate-800/80">
                <span className="text-[11px]">
                  Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filteredAndSortedSamples.length)} of {filteredAndSortedSamples.length} clips
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="p-1 rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
                    aria-label="Previous Page"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                  </button>
                  <span className="text-[11px] px-1 font-semibold text-slate-300">
                    {page} / {totalPages}
                  </span>
                  <button
                    type="button"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    className="p-1 rounded bg-slate-950 border border-slate-800 text-slate-300 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed"
                    aria-label="Next Page"
                  >
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            )}
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

            {/* Pre-run Degraded Mode Warning */}
            {((selectedFile !== null) || (selectedSample && !selectedSample.has_box_file)) && (activeConfig?.detector === 'legacy' || !activeConfig) && (
              <div
                data-testid="prerun-fallback-warning"
                role="alert"
                className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/40 text-amber-300 text-xs flex items-start gap-2.5 animate-fade-in"
              >
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-semibold text-amber-200">
                    No detector is available for this video; results will be unreliable
                  </div>
                  <div className="text-[11px] text-amber-300/80 leading-relaxed">
                    This video has no pre-annotated box file and neural vehicle detection is inactive.
                    Argus will fall back to naive motion differencing which produces unreliable results.
                    {' '}
                    <button
                      type="button"
                      onClick={() => setShowDetectorHelpModal(true)}
                      className="underline text-amber-200 hover:text-white font-medium inline-flex items-center gap-1"
                    >
                      How to enable the detector <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </div>
            )}
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
                <VideoPlayer
                  src={inputVideoUrl}
                  title={`Raw Input Footage - Camera #${cameraId}`}
                  safeDownloadName={`input_camera_${cameraId}.mp4`}
                  controls
                  playsInline
                  loop
                  preload="metadata"
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
          <div className="pt-2 space-y-2">
            <div className="flex items-center gap-3">
              <button
                data-testid="start-pipeline-btn"
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

            {/* Ingest Node Busy Explanation */}
            {isProcessing && (
              <div
                data-testid="pipeline-busy-warning"
                role="status"
                className="p-2.5 rounded-lg bg-amber-950/30 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-2"
              >
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                <span>Pipeline Ingest Node Busy &mdash; another video feed is currently running. New submissions are disabled.</span>
              </div>
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
                  ? (activeFeed?.detection_quality === 'motion_fallback' || activeFeed?.detection_quality === 'unavailable' || (activeFeed as any)?.detection_mode === 'low-quality detection mode')
                    ? 'bg-amber-950/60 text-amber-300 border border-amber-500/40'
                    : 'bg-emerald-950/60 text-emerald-300 border border-emerald-500/40'
                  : 'bg-slate-950/60 text-slate-400 border border-slate-800'
              }`}>
                {detectionOutcome === 'idle'
                  ? 'STANDBY'
                  : detectionOutcome === 'normal'
                  ? ((activeFeed?.vehicles_detected_count ?? 0) === 0 && activeFeed?.detection_quality !== 'reference')
                    ? 'NO VEHICLES DETECTED'
                    : (activeFeed?.detection_quality === 'motion_fallback' || activeFeed?.detection_quality === 'unavailable' || (activeFeed as any)?.detection_mode === 'low-quality detection mode')
                    ? 'LOW QUALITY (UNRELIABLE)'
                    : 'NORMAL'
                  : detectionOutcome}
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
                (() => {
                  const isDegradedQuality =
                    activeFeed?.detection_quality === 'motion_fallback' ||
                    activeFeed?.detection_quality === 'unavailable' ||
                    (activeFeed as any)?.detection_mode === 'low-quality detection mode';

                  const zeroVehicles =
                    (activeFeed?.vehicles_detected_count ?? 0) === 0 &&
                    activeFeed?.detection_quality !== 'reference';

                  if (zeroVehicles) {
                    return (
                      <div
                        data-testid="outcome-zero-vehicles"
                        role="status"
                        className="p-4 rounded-xl border border-amber-500/40 bg-slate-900/90 text-white space-y-1.5 animate-fade-in"
                      >
                        <div className="flex items-center gap-2">
                          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                          <h4 className="font-bold text-xs text-amber-300 uppercase tracking-wider font-mono">
                            No vehicles were detected in this video
                          </h4>
                        </div>
                        <p className="text-xs text-slate-300">
                          The vehicle detector did not identify any vehicles throughout the entire clip. Crash classification could not be performed.
                        </p>
                      </div>
                    );
                  }

                  if (isDegradedQuality) {
                    return (
                      <div
                        data-testid="outcome-low-quality-warning"
                        role="alert"
                        className="p-4 rounded-xl border-2 border-amber-500/60 bg-amber-950/30 text-white space-y-1.5 animate-fade-in"
                      >
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                          <h4 className="font-bold text-xs text-amber-300 uppercase tracking-wider font-mono">
                            No alert, but detection was low quality. This result is not reliable.
                          </h4>
                        </div>
                        <p className="text-xs text-amber-200/80">
                          Motion fallback detector was active. Bounding boxes are uncalibrated and vehicle trajectories were dropped before classification.
                        </p>
                      </div>
                    );
                  }

                  return (
                    <div
                      data-testid="outcome-clean-normal"
                      className="p-4 rounded-xl border border-emerald-500/40 bg-emerald-950/20 text-white space-y-1.5 animate-fade-in"
                    >
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
                  );
                })()
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
                  <VideoPlayer
                    key={outputVideoUrl}
                    src={outputVideoUrl}
                    title={outputIncident ? `Detection Footage - Incident #${outputIncident.id}` : 'Detection Output Footage'}
                    safeDownloadName={outputIncident ? `incident_${outputIncident.id}.mp4` : 'output_clip.mp4'}
                    controls
                    playsInline
                    loop
                    autoPlay={false}
                    preload="metadata"
                    onError={() => {
                      if (inputVideoUrl && outputVideoUrl !== inputVideoUrl) {
                        setOutputVideoUrl(inputVideoUrl);
                      }
                    }}
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

            {/* Run Summary Line (Detector used, detection quality, vehicles seen, batches processed, alert count) */}
            {detectionOutcome !== 'idle' && detectionOutcome !== 'processing' && (
              <div
                data-testid="run-summary-line"
                className="mt-4 p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono flex flex-wrap items-center justify-between gap-3 shadow-inner"
              >
                <div className="flex items-center gap-2">
                  <span className="text-slate-500 uppercase text-[10px] tracking-wider font-semibold">Run Summary:</span>
                  <span className="text-white font-bold">{activeFeed?.id || (selectedSample ? selectedSample.id : 'Live')}</span>
                </div>
                <div className="flex flex-wrap items-center gap-4 text-[11px]">
                  <div>
                    <span className="text-slate-500 mr-1">Detector:</span>
                    <span data-testid="run-summary-detector" className="text-cyan-300 font-semibold">{activeFeed?.detector_name || 'legacy'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 mr-1">Quality:</span>
                    <span
                      data-testid="run-summary-quality"
                      className={`font-semibold ${
                        activeFeed?.detection_quality === 'neural' || activeFeed?.detection_quality === 'reference'
                          ? 'text-emerald-400'
                          : 'text-amber-400'
                      }`}
                    >
                      {activeFeed?.detection_quality || (selectedSample?.has_box_file ? 'reference' : 'unknown')}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 mr-1">Vehicles Seen:</span>
                    <span data-testid="run-summary-vehicles" className="text-white font-semibold">
                      {activeFeed?.vehicles_detected_count ?? 0}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 mr-1">Batches:</span>
                    <span data-testid="run-summary-batches" className="text-white font-semibold">
                      {activeFeed?.batches_processed ?? Math.max(1, Math.floor(((activeFeed?.progress?.frames_sent ?? 30) > 0 ? (activeFeed?.progress?.frames_sent ?? 30) : 30) / 30))}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 mr-1">Alerts:</span>
                    <span
                      data-testid="run-summary-alerts"
                      className={`font-semibold ${
                        (detectionOutcome === 'accident' || (activeFeed?.anomalies_detected ?? 0) > 0)
                          ? 'text-red-400'
                          : 'text-slate-300'
                      }`}
                    >
                      {detectionOutcome === 'accident' ? Math.max(1, activeFeed?.anomalies_detected ?? 1) : (activeFeed?.anomalies_detected ?? 0)}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Detected Events Timeline & Model Scoring (Shown after processing completes) */}
            {detectionOutcome !== 'idle' && detectionOutcome !== 'processing' && (
              <div data-testid="events-timeline-section" className="mt-4 p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-cyan-400" />
                    <h5 className="text-xs font-mono uppercase tracking-wider text-white font-bold">
                      Detected Event Timeline ({outputIncident ? '1 Event' : '0 Events'})
                    </h5>
                  </div>
                  {outputIncident?.model_scores && (
                    <button
                      type="button"
                      data-testid="compare-models-toggle"
                      onClick={() => setIsCompareModels(!isCompareModels)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono font-medium transition cursor-pointer border ${
                        isCompareModels
                          ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                          : 'bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-700'
                      }`}
                    >
                      <Columns className="w-3.5 h-3.5" />
                      <span>Compare models</span>
                    </button>
                  )}
                </div>

                {outputIncident ? (
                  <div className="space-y-3">
                    {/* Event Telemetry Row / Table */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-800/80">
                          <tr>
                            <th className="pb-1.5 font-semibold">Event ID</th>
                            <th className="pb-1.5 font-semibold">Time</th>
                            <th className="pb-1.5 font-semibold">Starting Frame</th>
                            <th className="pb-1.5 font-semibold">Location</th>
                            <th className="pb-1.5 font-semibold">Classification</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/40">
                          <tr>
                            <td className="py-2 text-cyan-400 font-bold">#{outputIncident.id}</td>
                            <td className="py-2 text-slate-300">{outputIncident.crash_time}</td>
                            <td className="py-2 text-amber-300">Frame {outputIncident.starting_frame_id}</td>
                            <td className="py-2 text-slate-300">{outputIncident.city || city}</td>
                            <td className="py-2">
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-red-950/80 text-red-300 border border-red-500/40">
                                Crash Detected
                              </span>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    {/* Compare Models Side-by-Side View */}
                    {isCompareModels && outputIncident.model_scores && (
                      <div data-testid="models-side-by-side" className="p-3 rounded-lg bg-slate-900/50 border border-slate-800 space-y-2">
                        <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
                          Side-by-Side Model Comparison
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                          {outputIncident.model_scores.scorers.map((s) => {
                            const meta = scorerLabel(s.name);
                            return (
                              <div
                                key={s.name}
                                data-testid={`compare-card-${s.name}`}
                                className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2"
                              >
                                <div className="flex items-center justify-between">
                                  <span className="text-xs font-semibold text-white truncate">{meta.label}</span>
                                  {s.fired ? (
                                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-950/80 text-red-300 border border-red-500/40 font-bold">
                                      Flagged
                                    </span>
                                  ) : (
                                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">
                                      Not flagged
                                    </span>
                                  )}
                                </div>
                                <div className="space-y-1">
                                  <div className="flex justify-between text-[11px] font-mono">
                                    <span className="text-slate-400">Score:</span>
                                    <span className="text-white font-bold">{formatScore(s.score)}</span>
                                  </div>
                                  <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden">
                                    <div
                                      className={`h-full ${s.fired ? 'bg-red-400' : 'bg-cyan-500'}`}
                                      style={{ width: `${Math.round((s.score || 0) * 100)}%` }}
                                    />
                                  </div>
                                </div>
                                <div className="text-[10px] font-mono text-slate-500 flex justify-between">
                                  <span>{s.calibrated ? 'Calibrated' : 'Uncalibrated'}</span>
                                  <span>{s.available ? 'Available' : 'Unavailable'}</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Integrated Model Score Breakdown */}
                    <div className="pt-2">
                      <ModelScoreBreakdown incident={outputIncident} />
                    </div>
                  </div>
                ) : (
                  <div data-testid="timeline-empty" className="p-4 rounded-lg bg-slate-900/30 border border-slate-800/80 text-center text-xs">
                    {activeFeed?.detection_quality === 'motion_fallback' || activeFeed?.detection_quality === 'unavailable' || (activeFeed as any)?.detection_mode === 'low-quality detection mode' ? (
                      <span className="text-amber-300 font-semibold flex items-center justify-center gap-1.5">
                        <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                        No alert, but detection was low quality. This result is not reliable.
                      </span>
                    ) : (activeFeed?.vehicles_detected_count ?? 0) === 0 && activeFeed?.detection_quality !== 'reference' ? (
                      <span className="text-amber-300 font-semibold flex items-center justify-center gap-1.5">
                        <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                        No vehicles were detected in this video
                      </span>
                    ) : (
                      <span className="text-slate-500">
                        No collision anomaly events detected across analyzed frame batches.
                      </span>
                    )}
                  </div>
                )}

                {/* Trajectory Time-series note */}
                <div
                  data-testid="trajectory-scores-notice"
                  className="p-3 rounded-lg bg-slate-900/40 border border-slate-800/80 text-xs text-slate-400 flex items-center gap-2"
                >
                  <Info className="w-4 h-4 text-cyan-400 shrink-0" />
                  <span>Per-frame trajectory scores not available for legacy pipeline runs</span>
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

              {activeFeed && activeFeed.status === 'done' && (
                <button
                  type="button"
                  data-testid="rerun-feed-btn"
                  onClick={handleRerunFeed}
                  disabled={isProcessing}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-cyan-300 transition border border-cyan-500/40"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Re-run Upload</span>
                </button>
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

      {/* ========================================================= */}
      {/* ========== BATCH TEST RUNNER & RESULTS SECTION ========== */}
      {/* ========================================================= */}
      {(isBatchRunning || batchResults.length > 0) && (
        <section
          data-testid="batch-section"
          aria-label="Batch Test Results"
          className="bg-slate-900/60 rounded-2xl border-2 border-cyan-500/30 p-5 space-y-5 shadow-xl relative overflow-hidden"
        >
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-800 gap-3">
            <div className="flex items-center gap-2.5">
              <span className={`w-3 h-3 rounded-full ${isBatchRunning ? 'bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(6,182,212,0.8)]' : 'bg-emerald-400'}`}></span>
              <div>
                <h3 className="text-base font-bold text-white uppercase tracking-wider font-mono flex items-center gap-2">
                  Batch Test Evaluation
                  <span className="text-xs font-normal text-slate-400 normal-case font-sans">
                    ({batchResults.length} / {batchQueue.length} Finished)
                  </span>
                </h3>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {batchResults.length > 0 && (
                <button
                  type="button"
                  data-testid="export-batch-csv-btn"
                  onClick={handleExportCsv}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
                >
                  <Download className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Download CSV</span>
                </button>
              )}

              {isBatchRunning && (
                <button
                  type="button"
                  data-testid="cancel-batch-btn"
                  onClick={handleCancelBatch}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-red-950/70 hover:bg-red-900/80 text-red-300 border border-red-500/40 transition"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  <span>Cancel Batch</span>
                </button>
              )}
            </div>
          </div>

          {/* Progress Header during Active Batch */}
          {isBatchRunning && (
            <div data-testid="batch-progress-card" className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-mono text-slate-300">
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 text-cyan-400 animate-spin" />
                  <span className="font-bold text-white">
                    Processing Clip {batchCurrentIndex} of {batchQueue.length}
                  </span>
                  <span className="text-slate-500">•</span>
                  <span className="text-cyan-400 font-semibold truncate max-w-xs">
                    {batchCurrentSample?.name || 'Loading...'}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-slate-400 text-[11px]">
                  <span>Elapsed: <strong className="text-white font-mono">{formatDuration(batchElapsedSeconds)}</strong></span>
                  <span>ETA: <strong className="text-cyan-300 font-mono">~{formatDuration(batchEtaSeconds)}</strong></span>
                </div>
              </div>

              {/* Progress Bar for Overall Batch */}
              <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
                <div
                  className="h-full bg-cyan-400 transition-all duration-300"
                  style={{ width: `${Math.round((batchCurrentIndex / Math.max(1, batchQueue.length)) * 100)}%` }}
                />
              </div>

              {/* Current Clip Ingest / Tracker Progress */}
              {batchCurrentFeed?.progress && (
                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1">
                  <span>
                    Frame Ingest: {batchCurrentFeed.progress.frames_sent ?? 0} / {batchCurrentFeed.progress.total_frames || '...'}
                  </span>
                  <span className="text-cyan-400 font-bold">{batchCurrentFeed.progress.percent ?? 0}%</span>
                </div>
              )}
            </div>
          )}

          {/* Disclaimer Note */}
          <div
            data-testid="batch-disclaimer"
            role="note"
            className="p-3 rounded-xl bg-slate-950/50 border border-slate-800 text-xs text-slate-400 flex items-center gap-2.5"
          >
            <Info className="w-4 h-4 text-cyan-400 shrink-0" />
            <span>
              <strong>Smoke test on local clips. Not a benchmark.</strong> Results reflect real-time live pipeline execution on local CCTV and dataset sample clips.
            </span>
          </div>

          {/* Active Pipeline Configuration Banner */}
          {activeConfig && (
            <div data-testid="active-config-banner" className="flex flex-wrap items-center gap-2 p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-xs font-mono">
              <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Active Config:</span>
              <span className="px-2 py-0.5 rounded bg-slate-800 text-cyan-300 border border-slate-700">
                Detector: {activeConfig.detector}
              </span>
              <span className={`px-2 py-0.5 rounded border ${activeConfig.adaptive_box_filter ? 'bg-cyan-950 text-cyan-300 border-cyan-600' : 'bg-slate-800 text-slate-400 border-slate-700'}`}>
                Adaptive Box: {activeConfig.adaptive_box_filter ? 'ON' : 'OFF'}
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Distance Factor: {activeConfig.distance_factor}
              </span>
              <span className={`px-2 py-0.5 rounded border ${activeConfig.single_vehicle ? 'bg-cyan-950 text-cyan-300 border-cyan-600' : 'bg-slate-800 text-slate-400 border-slate-700'}`}>
                Single Vehicle: {activeConfig.single_vehicle ? 'ON' : 'OFF'}
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                Threshold: {activeConfig.classifier_threshold}
              </span>
            </div>
          )}

          {/* Results Table */}
          {batchResults.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/80">
              <table data-testid="batch-results-table" className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-900/90 text-[10px] text-slate-400 uppercase tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold">Clip Name</th>
                    <th className="py-2.5 px-3 font-semibold">Expected</th>
                    <th className="py-2.5 px-3 font-semibold">Label Source</th>
                    <th className="py-2.5 px-3 font-semibold">Quality</th>
                    <th className="py-2.5 px-3 font-semibold">Cause</th>
                    <th className="py-2.5 px-3 font-semibold">Alert Raised?</th>
                    <th className="py-2.5 px-3 font-semibold">1st Alert (s)</th>
                    <th className="py-2.5 px-3 font-semibold">Proc Time</th>
                    <th className="py-2.5 px-3 font-semibold">Classification Outcome</th>
                    <th className="py-2.5 px-3 font-semibold">Status</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {batchResults.map((r) => (
                    <Fragment key={r.id}>
                      <tr data-testid={`batch-row-${r.id}`} className="hover:bg-slate-900/40 transition">
                        <td className="py-2 px-3">
                          <div className="font-bold text-white truncate max-w-[180px]" title={r.name}>{r.name}</div>
                          <div className="text-[10px] text-slate-500 truncate max-w-[180px]" title={r.relative_path}>{r.relative_path}</div>
                        </td>
                        <td className="py-2 px-3">
                          {r.expected_label === 'accident' && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-950/80 text-red-300 border border-red-500/40">
                              Accident
                            </span>
                          )}
                          {r.expected_label === 'normal' && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-500/40">
                              Normal
                            </span>
                          )}
                          {r.expected_label === 'unknown' && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-900 text-slate-400 border border-slate-700">
                              Unlabeled
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono text-slate-400 bg-slate-900 border border-slate-800">
                            {r.label_source || 'unknown'}
                          </span>
                        </td>
                        <td className="py-2 px-3">
                          {r.detection_quality === 'reference' ? (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono text-cyan-300 bg-cyan-950/60 border border-cyan-500/30">
                              reference
                            </span>
                          ) : r.detection_quality === 'neural' ? (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono text-emerald-300 bg-emerald-950/60 border border-emerald-500/30">
                              neural
                            </span>
                          ) : r.detection_quality === 'motion_fallback' ? (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold text-amber-300 bg-amber-950/80 border border-amber-500/40">
                              motion_fallback
                            </span>
                          ) : r.detection_quality === 'unavailable' ? (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold text-red-300 bg-red-950/80 border border-red-500/40">
                              unavailable
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono text-slate-400 bg-slate-900 border border-slate-700">
                              unknown quality
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold ${
                            r.cause_category === 'CRASH_DETECTED'
                              ? 'text-emerald-400 bg-emerald-950/60 border border-emerald-500/30'
                              : r.cause_category === 'CORRECT_NORMAL'
                              ? 'text-cyan-400 bg-cyan-950/60 border border-cyan-500/30'
                              : r.cause_category
                              ? 'text-amber-400 bg-amber-950/60 border border-amber-500/30'
                              : 'text-slate-500'
                          }`}>
                            {r.cause_category || '-'}
                          </span>
                        </td>
                        <td className="py-2 px-3">
                          {r.alert_raised ? (
                            <span className="text-red-400 font-bold flex items-center gap-1">
                              <Flame className="w-3 h-3 fill-red-400" /> Yes
                            </span>
                          ) : (
                            <span className="text-slate-400 font-medium">No</span>
                          )}
                        </td>
                        <td className="py-2 px-3 text-slate-300">
                          {r.time_to_first_alert_s != null ? `${r.time_to_first_alert_s}s` : '-'}
                        </td>
                        <td className="py-2 px-3 text-slate-300">
                          {r.processing_time_s}s
                        </td>
                        <td className="py-2 px-3">
                          {r.outcome === 'Alert on accident clip' && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-500/40">
                              Alert on accident clip
                            </span>
                          )}
                          {r.outcome === 'No alert on normal clip' && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/80 text-emerald-300 border border-emerald-500/40">
                              No alert on normal clip
                            </span>
                          )}
                          {r.outcome === 'Missed accident' && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-red-950/80 text-red-300 border border-red-500/40">
                              Missed accident
                            </span>
                          )}
                          {r.outcome === 'False alarm' && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/80 text-amber-300 border border-amber-500/40">
                              False alarm
                            </span>
                          )}
                          {r.outcome === 'Not scored (unlabeled)' && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-900 text-slate-400 border border-slate-700">
                              Not scored (unlabeled)
                            </span>
                          )}
                          {r.outcome === 'No alert, but detection was low quality. This result is not reliable.' && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/80 text-amber-300 border border-amber-500/40 flex items-center gap-1">
                              <AlertCircle className="w-3 h-3 text-amber-400 shrink-0" />
                              <span>No alert, but detection was low quality. This result is not reliable.</span>
                            </span>
                          )}
                          {r.outcome === 'No vehicles were detected in this video' && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/80 text-amber-300 border border-amber-500/40 flex items-center gap-1">
                              <AlertCircle className="w-3 h-3 text-amber-400 shrink-0" />
                              <span>No vehicles were detected in this video</span>
                            </span>
                          )}
                        </td>
                        <td className="py-2 px-3">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${
                            r.status === 'completed'
                              ? 'text-emerald-400 bg-emerald-950/40 border border-emerald-500/30'
                              : r.status === 'failed'
                              ? 'text-red-400 bg-red-950/40 border border-red-500/30'
                              : 'text-amber-400 bg-amber-950/40 border border-amber-500/30'
                          }`}>
                            {r.status}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              data-testid={`trace-toggle-${r.id}`}
                              onClick={() => setExpandedTraceId(expandedTraceId === r.id ? null : r.id)}
                              className={`px-2 py-1 rounded transition text-[11px] font-mono border ${
                                expandedTraceId === r.id
                                  ? 'bg-cyan-950/80 text-cyan-300 border-cyan-500/50'
                                  : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700'
                              }`}
                            >
                              {r.alert_raised ? 'Why alerted' : 'Why no alert'}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                const found = samples.find((s) => s.id === r.id);
                                if (found) setPreviewSample(found);
                              }}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition text-[11px]"
                            >
                              View Clip
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expandedTraceId === r.id && (
                        <tr data-testid={`trace-drawer-${r.id}`} className="bg-slate-950/90 border-b border-slate-800">
                          <td colSpan={11} className="p-3">
                            {r.trace_summary ? (
                              <div data-testid="trace-details" className="rounded-lg bg-slate-900 border border-slate-800 p-3 space-y-2 text-xs">
                                <div className="font-bold text-cyan-400 flex items-center justify-between">
                                  <span>Pipeline Trace Diagnostics</span>
                                  <span
                                    data-testid="trace-primary-cause"
                                    className={`font-mono text-[10px] px-2 py-0.5 rounded border ${
                                      r.trace_summary.primary_cause === 'LOW_QUALITY_DETECTION'
                                        ? 'bg-amber-950/80 text-amber-300 border-amber-500/50'
                                        : 'bg-slate-800 text-slate-300 border-slate-700'
                                    }`}
                                  >
                                    Cause: {r.trace_summary.primary_cause || 'UNKNOWN'}
                                  </span>
                                </div>
                                {r.trace_summary.primary_cause === 'LOW_QUALITY_DETECTION' && (
                                  <div
                                    data-testid="trace-low-quality-warning"
                                    className="p-2 rounded bg-amber-950/40 border border-amber-500/30 text-amber-300 text-[11px] flex items-center gap-1.5"
                                  >
                                    <AlertCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                                    <span>Video ran in degraded motion fallback mode. Vehicle detections and trajectory analysis are unreliable.</span>
                                  </div>
                                )}
                                <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 pt-1 font-mono text-[11px]">
                                  <div className="bg-slate-950 p-2 rounded border border-slate-800">
                                    <span className="text-slate-500 block text-[9px] uppercase">Detector</span>
                                    <span className="text-slate-200 font-bold">{r.trace_summary.detector_used || 'legacy'}</span>
                                  </div>
                                  <div className="bg-slate-950 p-2 rounded border border-slate-800">
                                    <span className="text-slate-500 block text-[9px] uppercase">Quality</span>
                                    <span className="text-slate-200 font-bold">{r.detection_quality || r.trace_summary.detection_quality || 'unknown'}</span>
                                  </div>
                                  <div className="bg-slate-950 p-2 rounded border border-slate-800">
                                    <span className="text-slate-500 block text-[9px] uppercase">Trackers</span>
                                    <span className="text-slate-200 font-bold">{r.trace_summary.max_trackers ?? 0}</span>
                                  </div>
                                  <div className="bg-slate-950 p-2 rounded border border-slate-800">
                                    <span className="text-slate-500 block text-[9px] uppercase">Batches</span>
                                    <span className="text-slate-200 font-bold">{r.trace_summary.batches_processed || r.trace_summary.total_batches || 1}</span>
                                  </div>
                                  <div className="bg-slate-950 p-2 rounded border border-slate-800">
                                    <span className="text-slate-500 block text-[9px] uppercase">Dominant Filter</span>
                                    <span className="text-amber-400 font-bold">{r.trace_summary.dominant_filter || 'NONE'}</span>
                                  </div>
                                  <div className="bg-slate-950 p-2 rounded border border-slate-800">
                                    <span className="text-slate-500 block text-[9px] uppercase">Max Score</span>
                                    <span className="text-cyan-300 font-bold">{r.trace_summary.max_classifier_score != null ? r.trace_summary.max_classifier_score.toFixed(4) : '--'}</span>
                                  </div>
                                </div>
                              </div>
                            ) : (
                              <div data-testid="no-trace-message" className="text-slate-400 italic text-xs py-2 px-3 bg-slate-900/50 rounded border border-slate-800">
                                No trace recorded
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Fullscreen Video Modal */}
      <IncidentVideoModal
        incident={modalIncident}
        onClose={() => setModalIncident(null)}
      />

      {/* Raw Sample Preview Modal */}
      {previewSample && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="preview-modal-title"
          data-testid="sample-preview-modal"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
          onClick={() => setPreviewSample(null)}
        >
          <div
            className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-5 space-y-4 shadow-2xl relative"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-cyan-950/60 text-cyan-300 border border-cyan-500/30">
                    Sample Stream Preview
                  </span>
                  <span className="text-xs font-mono text-slate-400 truncate max-w-xs sm:max-w-md">
                    {previewSample.relative_path}
                  </span>
                </div>
                <h2 id="preview-modal-title" className="text-base sm:text-lg font-bold text-white tracking-tight">
                  {previewSample.name}
                </h2>
              </div>
              <button
                type="button"
                data-testid="sample-preview-close"
                onClick={() => setPreviewSample(null)}
                aria-label="Close preview modal"
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            {/* Video Player */}
            <div className="relative aspect-video rounded-xl overflow-hidden bg-black border border-slate-800 shadow-inner">
              <VideoPlayer
                src={previewSample.video_url}
                poster={previewSample.thumbnail_url}
                title={`Preview ${previewSample.name}`}
                safeDownloadName={previewSample.name}
                testId="sample-preview-video"
                autoPlay={false}
                muted={false}
                controls
                playsInline
                loop
                preload="metadata"
                onClose={() => setPreviewSample(null)}
              />
            </div>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 space-y-0.5">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Ground Truth</span>
                <div className="font-semibold">
                  {previewSample.expected_label === 'accident' && <span className="text-red-400">Accident</span>}
                  {previewSample.expected_label === 'normal' && <span className="text-emerald-400">Normal</span>}
                  {previewSample.expected_label === 'unknown' && <span className="text-slate-400">Unlabeled</span>}
                </div>
              </div>

              <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 space-y-0.5">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Duration</span>
                <div className="font-semibold text-slate-200">{formatDuration(previewSample.duration_s)}</div>
              </div>

              <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 space-y-0.5">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">Format</span>
                <div className="font-semibold text-slate-200 truncate">
                  {previewSample.resolution || '--'} {previewSample.fps ? `(${previewSample.fps} fps)` : ''}
                </div>
              </div>

              <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 space-y-0.5">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">File Size</span>
                <div className="font-semibold text-slate-200">{formatBytes(previewSample.size_bytes)}</div>
              </div>
            </div>

            {previewSample.notes && (
              <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-xs text-slate-400 font-mono">
                <span className="text-slate-500 font-semibold uppercase text-[10px] block">Manifest Notes:</span>
                {previewSample.notes}
              </div>
            )}

            {/* Footer Controls */}
            <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setPreviewSample(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              >
                Close
              </button>
              <button
                type="button"
                data-testid="sample-preview-select"
                onClick={() => {
                  handleSelectSample(previewSample);
                  setPreviewSample(null);
                }}
                disabled={isProcessing}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider bg-cyan-400 hover:bg-cyan-300 text-slate-950 transition disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5 fill-slate-950" />
                Select This Clip
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Batch Test Confirmation Modal */}
      {showBatchConfirmModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="batch-confirm-title"
          data-testid="batch-confirm-modal"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
          onClick={() => setShowBatchConfirmModal(false)}
        >
          <div
            className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-5 space-y-4 shadow-2xl relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <PlayCircle className="w-5 h-5 text-cyan-400" />
                <h3 id="batch-confirm-title" className="text-base font-bold text-white tracking-tight">
                  Confirm Batch Test Run
                </h3>
              </div>
              <button
                type="button"
                data-testid="batch-confirm-cancel-btn"
                onClick={() => setShowBatchConfirmModal(false)}
                className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition"
              >
                <XCircle className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono text-slate-300">
              <p className="text-slate-200">
                You are about to launch sequential pipeline testing on{' '}
                <strong className="text-cyan-400">{batchQueue.length} clips</strong>.
              </p>

              <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Video Duration:</span>
                  <span className="text-white font-bold">~{formatDuration(batchQueueEstimatedDuration)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Accident Clips:</span>
                  <span className="text-red-400 font-bold">{batchQueue.filter((s) => s.expected_label === 'accident').length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Normal Clips:</span>
                  <span className="text-emerald-400 font-bold">{batchQueue.filter((s) => s.expected_label === 'normal').length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Unlabeled Clips:</span>
                  <span className="text-slate-400 font-bold">{batchQueue.filter((s) => s.expected_label === 'unknown').length}</span>
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-cyan-950/30 border border-cyan-500/30 text-cyan-300 text-[11px] flex items-center gap-2">
                <Info className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>Clips are processed strictly sequentially (one at a time). You can cancel the batch at any point.</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowBatchConfirmModal(false)}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                data-testid="batch-confirm-start-btn"
                onClick={handleStartBatch}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold uppercase tracking-wider bg-cyan-400 hover:cyan-300 text-slate-950 transition active:scale-[0.98]"
              >
                <Play className="w-3.5 h-3.5 fill-slate-950" />
                Start Sequential Batch
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detector Help Modal */}
      {showDetectorHelpModal && (
        <div
          data-testid="detector-help-modal"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in"
        >
          <div className="relative w-full max-w-lg overflow-hidden rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <h3 className="text-base font-bold text-white font-mono uppercase tracking-wider">
                  Vehicle Detector Configuration
                </h3>
              </div>
              <button
                type="button"
                data-testid="close-detector-help-modal"
                onClick={() => setShowDetectorHelpModal(false)}
                className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs text-slate-300">
              <p>
                Argus uses vehicle bounding boxes to initialize spatial trackers and compute Horn-Schunck violent flow descriptors.
              </p>

              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1.5">
                <div className="font-semibold text-amber-300 flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5" />
                  Why is detection degraded on uploaded videos?
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  The bundled sample clips rely on pre-annotated bounding boxes (<code className="text-cyan-400 font-mono">boxes/&lt;id&gt;.txt</code>). When an arbitrary video is uploaded without annotations, Argus falls back to naive motion frame differencing (<code className="text-amber-400 font-mono">MotionFallbackDetector</code>), which produces noisy contours and unreliable results.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/80 border border-cyan-500/30 space-y-1.5">
                <div className="font-semibold text-cyan-300 flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5" />
                  How to configure neural vehicle detection:
                </div>
                <ul className="list-disc pl-4 text-[11px] text-slate-400 space-y-1">
                  <li>
                    Set <code className="text-cyan-300 font-mono">ARGUS_DETECTOR=yolo</code> or neural detector mode before launching the supervisor.
                  </li>
                  <li>
                    In Phase 3, a permissive Apache-2.0 / BSD neural detector will be integrated directly for automatic vehicle localization on all uploads.
                  </li>
                  <li>
                    For benchmark evaluation, ground-truth box annotations can be registered in <code className="text-cyan-300 font-mono">boxes/</code>.
                  </li>
                </ul>
              </div>
            </div>

            <div className="flex items-center justify-end pt-2 border-t border-slate-800">
              <button
                type="button"
                data-testid="detector-help-close-btn"
                onClick={() => setShowDetectorHelpModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
export default CameraFeeder;
