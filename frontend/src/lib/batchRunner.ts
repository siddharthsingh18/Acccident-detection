export type BatchOutcome =
  | 'Alert on accident clip'
  | 'No alert on normal clip'
  | 'Missed accident'
  | 'False alarm'
  | 'Not scored (unlabeled)';

export interface BatchResultItem {
  id: string;
  name: string;
  relative_path: string;
  expected_label: 'accident' | 'normal' | 'unknown';
  alert_raised: boolean;
  time_to_first_alert_s: number | null;
  processing_time_s: number;
  status: 'completed' | 'failed' | 'cancelled';
  outcome: BatchOutcome;
  incident_id?: string | null;
  video_url?: string | null;
  error?: string | null;
}

/**
 * Classifies the test run outcome according to Argus evaluation rules.
 */
export function classifyBatchOutcome(
  expectedLabel: 'accident' | 'normal' | 'unknown',
  alertRaised: boolean
): BatchOutcome {
  if (expectedLabel === 'accident') {
    return alertRaised ? 'Alert on accident clip' : 'Missed accident';
  }
  if (expectedLabel === 'normal') {
    return alertRaised ? 'False alarm' : 'No alert on normal clip';
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
