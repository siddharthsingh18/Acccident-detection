import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, AlertCircle, RefreshCw, Radio, Camera, MapPin, Clock, CheckCircle2, Sparkles, Video } from 'lucide-react';
import { api, type Incident } from '@/lib/api';
import { useAlertSocket } from '@/hooks/useAlertSocket';
import { useSound } from '@/contexts/SoundContext';
import { useDemo } from '@/contexts/DemoContext';
import { IncidentVideoModal } from '@/components/IncidentVideoModal';

interface DisplayIncident {
  id: string;
  camera_id: number;
  starting_frame_id: number;
  crash_time: string;
  city?: string;
  district?: string;
  thumbnail_url: string;
  video_url: string;
  isNewAlert?: boolean;
  isDemo?: boolean;
}

export function LiveDashboard() {
  const [incidents, setIncidents] = useState<DisplayIncident[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const { latestAlert, connectionStatus } = useAlertSocket();
  const { playSiren } = useSound();
  const { demoAlert, setLastAlertTime } = useDemo();
  const processedAlertIds = useRef<Set<string>>(new Set());

  // Load 10 most recent incidents on mount
  useEffect(() => {
    let isMounted = true;
    const fetchInitial = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await api.getRecentIncidents();
        if (isMounted) {
          setIncidents(data);
          setIsLoading(false);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Failed to load recent incidents.');
          setIsLoading(false);
        }
      }
    };

    fetchInitial();
    return () => {
      isMounted = false;
    };
  }, []);

  // Listen for live alerts from WebSocket
  useEffect(() => {
    if (!latestAlert || processedAlertIds.current.has(latestAlert.incident_id)) {
      return;
    }

    processedAlertIds.current.add(latestAlert.incident_id);
    setLastAlertTime(new Date());

    // Play siren
    playSiren();

    // Show toast
    setToastMessage(`Accident Alert detected on Camera ${latestAlert.camera_id} (${latestAlert.city || 'Unknown'})`);
    const toastTimer = setTimeout(() => setToastMessage(null), 6000);

    // Add to highlighted IDs (green highlight like Qt app for 6 seconds)
    setHighlightedIds((prev) => new Set(prev).add(latestAlert.incident_id));
    const highlightTimer = setTimeout(() => {
      setHighlightedIds((prev) => {
        const next = new Set(prev);
        next.delete(latestAlert.incident_id);
        return next;
      });
    }, 6000);

    // Convert AlertMessage to DisplayIncident and prepend
    const newIncident: DisplayIncident = {
      id: latestAlert.incident_id,
      camera_id: latestAlert.camera_id,
      starting_frame_id: latestAlert.starting_frame_id,
      crash_time: `${latestAlert.date} ${latestAlert.time}`,
      city: latestAlert.city,
      district: latestAlert.district,
      thumbnail_url: latestAlert.thumbnail_url,
      video_url: latestAlert.video_url,
      isNewAlert: true,
      isDemo: false,
    };

    setIncidents((prev) => [newIncident, ...prev.filter((item) => item.id !== newIncident.id)]);

    return () => {
      clearTimeout(toastTimer);
      clearTimeout(highlightTimer);
    };
  }, [latestAlert, playSiren, setLastAlertTime]);

  // Listen for simulated Demo alerts
  useEffect(() => {
    if (!demoAlert || processedAlertIds.current.has(demoAlert.incident_id)) {
      return;
    }

    processedAlertIds.current.add(demoAlert.incident_id);
    playSiren();

    setToastMessage(`[DEMO] Simulated Alert: Camera ${demoAlert.camera_id} (${demoAlert.city})`);
    const toastTimer = setTimeout(() => setToastMessage(null), 6000);

    setHighlightedIds((prev) => new Set(prev).add(demoAlert.incident_id));
    const highlightTimer = setTimeout(() => {
      setHighlightedIds((prev) => {
        const next = new Set(prev);
        next.delete(demoAlert.incident_id);
        return next;
      });
    }, 6000);

    const demoIncident: DisplayIncident = {
      id: demoAlert.incident_id,
      camera_id: demoAlert.camera_id,
      starting_frame_id: demoAlert.starting_frame_id,
      crash_time: `${demoAlert.date} ${demoAlert.time}`,
      city: demoAlert.city,
      district: demoAlert.district,
      thumbnail_url: demoAlert.thumbnail_url,
      video_url: demoAlert.video_url,
      isNewAlert: true,
      isDemo: true,
    };

    setIncidents((prev) => [demoIncident, ...prev.filter((item) => item.id !== demoIncident.id)]);

    return () => {
      clearTimeout(toastTimer);
      clearTimeout(highlightTimer);
    };
  }, [demoAlert, playSiren]);

  const handleCardClick = (item: DisplayIncident) => {
    setSelectedIncident({
      id: item.id,
      rowid: 0,
      camera_id: item.camera_id,
      starting_frame_id: item.starting_frame_id,
      city: item.city,
      district: item.district,
      crash_time: item.crash_time,
      from_no: 5,
      thumbnail_url: item.thumbnail_url,
      video_url: item.video_url,
    });
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification for incoming real-time alerts */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-xl bg-red-950/90 border border-red-500/80 shadow-[0_0_20px_rgba(239,68,68,0.5)] text-white animate-slide-in">
          <ShieldAlert className="w-5 h-5 text-red-400 shrink-0 animate-bounce" />
          <div>
            <div className="text-xs uppercase font-mono tracking-wider text-red-300 font-semibold">
              Live Alert Received
            </div>
            <div className="text-sm font-medium text-white">{toastMessage}</div>
          </div>
        </div>
      )}

      {/* Dashboard Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Radio className="w-6 h-6 text-cyan-400" />
            Live Surveillance Dashboard
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Real-time automated incident detection across deployed CCTV camera edge nodes.
          </p>
        </div>

        {/* Header Actions */}
        <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-center">
          <Link
            to="/feeder"
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-bold text-xs uppercase tracking-wider transition shadow-md shadow-cyan-500/20"
          >
            <Video className="w-3.5 h-3.5" />
            <span>Detection Studio (Input & Output)</span>
          </Link>

          {/* WebSocket Connection Badge */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono">
            <span
              className={`w-2 h-2 rounded-full ${
                connectionStatus === 'connected'
                  ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                  : connectionStatus === 'connecting'
                  ? 'bg-amber-400 animate-pulse'
                  : 'bg-red-400'
              }`}
            />
            <span className="text-slate-300">
              ALERT STREAM:{' '}
              <strong className="text-white uppercase">{connectionStatus}</strong>
            </span>
          </div>
        </div>
      </div>

      {/* Human Verification Advisory Banner */}
      <div className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs">
        <ShieldAlert className="w-4 h-4 shrink-0 text-amber-400" />
        <div>
          <span className="font-semibold uppercase tracking-wide">Human verification required:</span>{' '}
          Argus is an assisted decision support platform. A qualified operator must visually confirm every alert before dispatching emergency response.
        </div>
      </div>

      {/* Loading Skeleton State */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3 animate-pulse">
              <div className="w-full aspect-video bg-slate-800 rounded-lg" />
              <div className="h-4 bg-slate-800 rounded w-1/3" />
              <div className="h-3 bg-slate-800 rounded w-2/3" />
              <div className="h-3 bg-slate-800 rounded w-1/2" />
            </div>
          ))}
        </div>
      )}

      {/* Error State */}
      {!isLoading && error && (
        <div className="p-8 rounded-xl border border-red-500/30 bg-red-950/20 text-center max-w-lg mx-auto">
          <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
          <h3 className="text-lg font-medium text-white mb-1">Failed to Connect to Surveillance Stream</h3>
          <p className="text-sm text-slate-400 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition"
          >
            <RefreshCw className="w-4 h-4" />
            Reload Dashboard
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && incidents.length === 0 && (
        <div className="p-12 rounded-xl border border-slate-800 bg-slate-900/40 text-center max-w-md mx-auto">
          <CheckCircle2 className="w-12 h-12 text-cyan-400 mx-auto mb-3 opacity-60" />
          <h3 className="text-lg font-medium text-white mb-1">All Clear</h3>
          <p className="text-sm text-slate-400">
            No road accident incidents detected currently. Active camera feeds will stream live alerts here instantly.
          </p>
        </div>
      )}

      {/* Incidents Grid */}
      {!isLoading && !error && incidents.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {incidents.map((incident) => {
            const isHighlighted = highlightedIds.has(incident.id);
            return (
              <div
                key={incident.id}
                data-testid="incident-card"
                onClick={() => handleCardClick(incident)}
                className={`group cursor-pointer rounded-xl overflow-hidden border transition-all duration-300 transform hover:-translate-y-1 hover:shadow-xl ${
                  isHighlighted
                    ? 'border-emerald-400 bg-emerald-950/20 shadow-[0_0_25px_rgba(16,185,129,0.4)] animate-slide-in'
                    : 'border-slate-800 bg-slate-900/70 hover:border-cyan-500/50 hover:bg-slate-900'
                }`}
              >
                {/* Thumbnail Header */}
                <div className="relative aspect-video bg-black overflow-hidden">
                  <img
                    src={incident.thumbnail_url}
                    alt={`Incident ${incident.id}`}
                    loading="lazy"
                    className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = '/media/thumbnails/fallback';
                    }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent opacity-80" />

                  {/* Highlight Ribbon / Incident Badge */}
                  <div className="absolute top-3 left-3 flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded font-mono text-xs font-bold bg-slate-950/80 text-cyan-400 border border-slate-700/80 backdrop-blur-sm">
                      #{incident.id}
                    </span>
                    {incident.isDemo && (
                      <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-500 text-slate-950 flex items-center gap-1">
                        <Sparkles className="w-3 h-3" />
                        DEMO
                      </span>
                    )}
                    {isHighlighted && (
                      <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-500 text-slate-950 animate-pulse">
                        NEW ALERT
                      </span>
                    )}
                  </div>

                  {/* Play Indicator Overlay */}
                  <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition bg-black/40">
                    <div className="w-12 h-12 rounded-full bg-cyan-500/90 text-slate-950 flex items-center justify-center shadow-lg">
                      <div className="w-0 h-0 border-y-8 border-y-transparent border-l-12 border-l-slate-950 ml-1" />
                    </div>
                  </div>
                </div>

                {/* Metadata Card Footer */}
                <div className="p-4 space-y-2.5">
                  <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
                    <span className="flex items-center gap-1.5 text-white font-medium">
                      <Camera className="w-3.5 h-3.5 text-cyan-400" />
                      Camera {incident.camera_id}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      {incident.crash_time}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 text-xs text-slate-300">
                    <MapPin className="w-3.5 h-3.5 text-red-400 shrink-0" />
                    <span className="truncate">
                      {incident.city || 'Unknown Location'}, {incident.district || 'Unassigned'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Video Modal */}
      <IncidentVideoModal
        incident={selectedIncident}
        onClose={() => setSelectedIncident(null)}
      />
    </div>
  );
}
