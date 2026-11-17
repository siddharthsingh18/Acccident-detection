export type BatchOutcome =
  | 'Alert on accident clip'
  | 'No alert on normal clip'
  | 'Missed accident'
  | 'False alarm'
  | 'Not scored (unlabeled)'
  | 'No alert, but detection was low quality. This result is not reliable.'
  | 'No vehicles were detected in this video';

export interface BatchResultItem {
  id: string;
  name: string;
  relative_path: string;
  expected_label: 'accident' | 'normal' | 'unknown';
  label_source?: 'verified_by_frames' | 'folder' | 'unknown';
  detection_quality?: 'reference' | 'neural' | 'motion_fallback' | 'unavailable' | 'unknown';
  vehicles_detected_count?: number;
  cause_category?: string | null;
  alert_raised: boolean;
  time_to_first_alert_s: number | null;
  processing_time_s: number;
  status: 'completed' | 'failed' | 'cancelled';
  outcome: BatchOutcome;
  incident_id?: string | null;
  video_url?: string | null;
  error?: string | null;
  trace_summary?: {
    detector_used?: string;
    max_trackers?: number;
    dominant_filter?: string;
    max_classifier_score?: number | null;
    primary_cause?: string;
  } | null;
}

/**
 * Classifies the test run outcome according to Argus evaluation rules.
 */
export function classifyBatchOutcome(
  expectedLabel: 'accident' | 'normal' | 'unknown',
  alertRaised: boolean,
  detectionQuality?: string,
  vehiclesDetectedCount?: number
): BatchOutcome {
  if (alertRaised) {
    if (expectedLabel === 'accident') return 'Alert on accident clip';
    if (expectedLabel === 'normal') return 'False alarm';
    return 'Not scored (unlabeled)';
  }

  // Not alerted
  if (detectionQuality === 'motion_fallback' || detectionQuality === 'unavailable') {
    if (vehiclesDetectedCount === 0) {
      return 'No vehicles were detected in this video';
    }
    return 'No alert, but detection was low quality. This result is not reliable.';
  }

  if (vehiclesDetectedCount === 0 && detectionQuality && detectionQuality !== 'reference') {
    return 'No vehicles were detected in this video';
  }

  if (expectedLabel === 'accident') {
    return 'Missed accident';
  }
  if (expectedLabel === 'normal') {
    return 'No alert on normal clip';
  }
  return 'Not scored (unlabeled)';
}

/**
 * Generates an RFC 4180 compliant CSV string for batch test results.
 */
export function generateBatchResultsCsv(results: BatchResultItem[]): string {
  const headers = [
    'Clip Name',
    'Relative Path',
    'Expected Label',
    'Label Source',
    'Detection Quality',
    'Vehicles Detected',
    'Cause Category',
    'Alert Raised',
    'Time to First Alert (s)',
    'Processing Time (s)',
    'Classification Outcome',
    'Status',
    'Incident ID',
    'Error',
  ];

  const escapeCsv = (val: any) => {
    if (val == null) return '';
    const str = String(val);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const rows = results.map((r) => [
    escapeCsv(r.name),
    escapeCsv(r.relative_path),
    escapeCsv(r.expected_label),
    escapeCsv(r.label_source || 'unknown'),
    escapeCsv(r.detection_quality && r.detection_quality !== 'unknown' ? r.detection_quality : 'unknown quality'),
    escapeCsv(r.vehicles_detected_count != null ? r.vehicles_detected_count : (r.trace_summary?.max_trackers != null ? r.trace_summary.max_trackers : '-')),
    escapeCsv(r.cause_category || '-'),
    escapeCsv(r.alert_raised ? 'Yes' : 'No'),
    escapeCsv(r.time_to_first_alert_s != null ? r.time_to_first_alert_s : '-'),
    escapeCsv(r.processing_time_s),
    escapeCsv(r.outcome),
    escapeCsv(r.status),
    escapeCsv(r.incident_id || '-'),
    escapeCsv(r.error || '-'),
  ]);

  return [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
}

/**
 * Triggers a browser download of the CSV data.
 */
export function downloadCsv(filename: string, csvContent: string): void {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
