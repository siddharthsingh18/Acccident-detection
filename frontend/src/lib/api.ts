import type { paths } from '@/types/api';

export type Incident = paths['/api/incidents']['get']['responses']['200']['content']['application/json']['items'][0];
export type IncidentsResponse = paths['/api/incidents']['get']['responses']['200']['content']['application/json'];
export type HealthResponse = paths['/api/health']['get']['responses']['200']['content']['application/json'];
export type FeedResponse = paths['/api/feeds']['post']['responses']['201']['content']['application/json'];
export type FeedCancelResponse = paths['/api/feeds/{id}/cancel']['post']['responses']['200']['content']['application/json'];

export interface IncidentFilters {
  start_date?: string;
  end_date?: string;
  start_time?: string;
  end_time?: string;
  city?: string;
  district?: string;
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
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    if (filters.start_time) params.append('start_time', filters.start_time);
    if (filters.end_time) params.append('end_time', filters.end_time);
    if (filters.city) params.append('city', filters.city);
    if (filters.district) params.append('district', filters.district);
    if (filters.limit) params.append('limit', String(filters.limit));
    if (filters.cursor !== undefined && filters.cursor !== null) params.append('cursor', String(filters.cursor));

    const res = await fetch(`/api/incidents?${params.toString()}`);
    return handleResponse<IncidentsResponse>(res);
  },

  async getIncident(id: string): Promise<Incident> {
    const res = await fetch(`/api/incidents/${id}`);
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

  getExportUrl(filters: IncidentFilters = {}): string {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    if (filters.start_time) params.append('start_time', filters.start_time);
    if (filters.end_time) params.append('end_time', filters.end_time);
    if (filters.city) params.append('city', filters.city);
    if (filters.district) params.append('district', filters.district);
    return `/api/incidents/export?${params.toString()}`;
  }
};
