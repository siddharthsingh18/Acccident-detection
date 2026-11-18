import type { paths } from '@/types/api';
import {
  type ModelScores,
  type ModelsStatusResponse,
  ModelsStatusResponseSchema,
} from './modelsContract';

export type ReviewStatus = 'confirmed' | 'false_alarm' | 'unreviewed' | null;

export type RawIncident = paths['/api/incidents']['get']['responses']['200']['content']['application/json']['items'][0];

export interface Incident extends Omit<RawIncident, 'review_status'> {
  review_status?: ReviewStatus;
  review_note?: string | null;
  reviewed_at?: string | null;
  model_scores?: ModelScores | null;
  detection_quality?: 'reference' | 'neural' | 'motion_fallback' | 'unavailable' | 'unknown';
  detector_name?: string | null;
}

export interface IncidentsResponse {
  items: Incident[];
  count: number;
  next_cursor?: number | null;
  has_more: boolean;
}

export type HealthResponse = paths['/api/health']['get']['responses']['200']['content']['application/json'];
export type FeedResponse = paths['/api/feeds']['post']['responses']['201']['content']['application/json'] & {
  degraded?: boolean;
  active_scorers?: string[];
  detected_incidents?: string[];
  anomalies_detected?: number;
  detection_quality?: 'reference' | 'neural' | 'motion_fallback' | 'unavailable' | 'unknown';
  detector_name?: string;
  detector_config?: Record<string, any>;
  vehicles_detected_count?: number;
  batches_processed?: number;
  is_test?: boolean;
  effective_config?: Record<string, any>;
};
export type FeedCancelResponse = paths['/api/feeds/{id}/cancel']['post']['responses']['200']['content']['application/json'];

export interface IncidentFilters {
  camera_id?: number;
  start_date?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  city?: string;
  district?: string;
  review_status?: string;
  feed_id?: string;
  include_test?: boolean;
  limit?: number;
  cursor?: number;
}

export interface AlertMessage {
  incident_id: string;
  camera_id: number;
  starting_frame_id: number;
  date: string;
  time: string;
  city?: string;
  district?: string;
  thumbnail_url: string;
  video_url: string;
  model_scores?: ModelScores | null;
}

export interface SystemSettings {
  alert_sound_enabled: boolean;
  siren_volume: number;
  clip_retention_days: number;
  min_alert_confidence: number;
  updated_at?: string | null;
  confidence_note?: string;
}

export interface UpdateSettingsRequest {
  alert_sound_enabled: boolean;
  siren_volume: number;
  clip_retention_days: number;
  min_alert_confidence: number;
}

export interface SampleFeed {
  id: string;
  filename: string;
  camera_id: number;
  city: string;
  district: string;
  label: string;
  description: string;
  has_accident: boolean;
  incident_id: string | null;
  video_url: string;
  output_video_url: string | null;
}

export interface SampleItem {
  id: string;
  name: string;
  relative_path: string;
  size_bytes: number;
  duration_s: number | null;
  resolution: string | null;
  fps: number | null;
  thumbnail_url: string;
  video_url: string;
  expected_label: 'accident' | 'normal' | 'unknown';
  label_source?: 'verified_by_frames' | 'folder' | 'unknown';
  camera_id?: number | null;
  city?: string | null;
  district?: string | null;
  notes?: string | null;
  has_box_file?: boolean;
  detection_quality?: 'reference' | 'neural' | 'motion_fallback' | 'unavailable' | 'unknown';
}

export interface TraceSummaryResponse {
  run_id: string;
  has_trace: boolean;
  summary: {
    detector_used?: string;
    detection_quality?: string;
    max_trackers?: number;
    total_batches?: number;
    batches_processed?: number;
    dominant_filter?: string;
    max_classifier_score?: number | null;
    alert_count?: number;
    primary_cause?: string;
    filter_counts?: Record<string, number>;
    pairs_evaluated?: number;
  } | null;
  records_count?: number;
  message?: string;
}

export interface ActiveConfigResponse {
  detector: string;
  trace_enabled: boolean;
  adaptive_box_filter: boolean;
  distance_factor: number;
  single_vehicle: boolean;
  classifier_threshold: number;
  ensemble_enabled: boolean;
  crash_policy: string;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = 'An unexpected error occurred';
    try {
      const json = await res.json();
      errorDetail = json.message || json.detail || JSON.stringify(json);
    } catch {
      errorDetail = await res.text() || res.statusText;
    }
    throw new Error(errorDetail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    const res = await fetch('/api/health');
    return handleResponse<HealthResponse>(res);
  },

  async getRecentIncidents(): Promise<Incident[]> {
    const res = await fetch('/api/incidents/recent');
    return handleResponse<Incident[]>(res);
  },

  async getIncidents(filters: IncidentFilters = {}): Promise<IncidentsResponse> {
    const params = new URLSearchParams();
    if (filters.camera_id !== undefined && filters.camera_id !== null) {
      params.append('camera_id', String(filters.camera_id));
    }
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    if (filters.start_time) params.append('start_time', filters.start_time);
    if (filters.end_time) params.append('end_time', filters.end_time);
    if (filters.city) params.append('city', filters.city);
    if (filters.district) params.append('district', filters.district);
    if (filters.review_status && filters.review_status !== 'all') {
      params.append('review_status', filters.review_status);
    }
    if (filters.feed_id) params.append('feed_id', filters.feed_id);
    if (filters.include_test) params.append('include_test', 'true');
    if (filters.limit) params.append('limit', String(filters.limit));
    if (filters.cursor !== undefined && filters.cursor !== null) params.append('cursor', String(filters.cursor));

    const res = await fetch(`/api/incidents?${params.toString()}`);
    return handleResponse<IncidentsResponse>(res);
  },

  async getIncident(id: string): Promise<Incident> {
    const res = await fetch(`/api/incidents/${id}`);
    return handleResponse<Incident>(res);
  },

  async reviewIncident(
    id: string,
    body: { status: 'confirmed' | 'false_alarm'; note?: string }
  ): Promise<Incident> {
    const res = await fetch(`/api/incidents/${id}/review`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    return handleResponse<Incident>(res);
  },

  async createFeed(formData: FormData): Promise<FeedResponse> {
    const res = await fetch('/api/feeds', {
      method: 'POST',
      body: formData,
    });
    return handleResponse<FeedResponse>(res);
  },

  async getFeed(id: string): Promise<FeedResponse> {
    const res = await fetch(`/api/feeds/${id}`);
    return handleResponse<FeedResponse>(res);
  },

  async cancelFeed(id: string): Promise<FeedCancelResponse> {
    const res = await fetch(`/api/feeds/${id}/cancel`, {
      method: 'POST',
    });
    return handleResponse<FeedCancelResponse>(res);
  },

  async rerunFeed(
    id: string,
    payload?: {
      camera_id?: number;
      city?: string;
      district?: string;
      detector?: string;
      is_test?: boolean;
      detector_confidence?: number;
      adaptive_box_filter?: boolean;
      distance_factor?: number;
      single_vehicle_mode?: boolean;
      frame_stride?: number;
    }
  ): Promise<FeedResponse> {
    const res = await fetch(`/api/feeds/${id}/rerun`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload || {}),
    });
    return handleResponse<FeedResponse>(res);
  },

  async compareRuns(idA: string, idB: string): Promise<any> {
    const res = await fetch(`/api/feeds/${idA}/compare/${idB}`);
    return handleResponse<any>(res);
  },

  async getSampleFeeds(): Promise<SampleFeed[]> {
    const res = await fetch('/api/feeds/samples');
    return handleResponse<SampleFeed[]>(res);
  },

  async getSamples(): Promise<SampleItem[]> {
    const res = await fetch('/api/samples');
    return handleResponse<SampleItem[]>(res);
  },

  async startFeedFromSample(sampleId: string, cameraId?: number, city?: string, district?: string, isTest: boolean = true): Promise<FeedResponse> {
    const res = await fetch('/api/feeds/from-sample', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        sample_id: sampleId,
        camera_id: cameraId,
        city,
        district,
        is_test: isTest,
      }),
    });
    return handleResponse<FeedResponse>(res);
  },

  async startSampleFeed(sampleId: string, city: string, district: string): Promise<FeedResponse> {
    const formData = new FormData();
    formData.append('sample_id', sampleId);
    formData.append('city', city);
    formData.append('district', district);
    const res = await fetch('/api/feeds/sample', {
      method: 'POST',
      body: formData,
    });
    return handleResponse<FeedResponse>(res);
  },

  getExportUrl(filters: IncidentFilters = {}): string {
    const params = new URLSearchParams();
    if (filters.camera_id !== undefined && filters.camera_id !== null) {
      params.append('camera_id', String(filters.camera_id));
    }
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    if (filters.start_time) params.append('start_time', filters.start_time);
    if (filters.end_time) params.append('end_time', filters.end_time);
    if (filters.city) params.append('city', filters.city);
    if (filters.district) params.append('district', filters.district);
    if (filters.review_status && filters.review_status !== 'all') {
      params.append('review_status', filters.review_status);
    }
    if (filters.feed_id) params.append('feed_id', filters.feed_id);
    if (filters.include_test) params.append('include_test', 'true');
    return `/api/incidents/export?${params.toString()}`;
  },

  async getSettings(): Promise<SystemSettings> {
    const res = await fetch('/api/settings');
    return handleResponse<SystemSettings>(res);
  },

  async updateSettings(body: UpdateSettingsRequest): Promise<SystemSettings> {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    return handleResponse<SystemSettings>(res);
  },

  async getModelsStatus(): Promise<ModelsStatusResponse> {
    const res = await fetch('/api/models/status');
    const json = await handleResponse<unknown>(res);
    return ModelsStatusResponseSchema.parse(json);
  },

  async getRunTrace(runId: string): Promise<TraceSummaryResponse> {
    const res = await fetch(`/api/feeds/trace/${encodeURIComponent(runId)}`);
    return handleResponse<TraceSummaryResponse>(res);
  },

  async getActiveConfig(): Promise<ActiveConfigResponse> {
    const res = await fetch('/api/feeds/config/active');
    return handleResponse<ActiveConfigResponse>(res);
  }
};
