import { ModelScoreBreakdown } from '@/components/ModelScoreBreakdown';
import type { Incident } from '@/lib/api';
import { Cpu, CheckCircle2, Split, AlertTriangle, HelpCircle } from 'lucide-react';

const mockAllAgree: Incident = {
  id: 'DEV-ALL-AGREE',
  rowid: 1,
  camera_id: 101,
  starting_frame_id: 42,
  crash_time: '2026-11-01 12:00:00',
  city: 'Cairo',
  district: 'District 1',
  thumbnail_url: '/placeholder-thumbnail.svg',
  video_url: '/video.mp4',
  review_status: 'unreviewed',
  model_scores: {
    policy: 'majority',
    threshold: 0.5,
    decision: true,
    scorers: [
      { name: 'vif_svm', score: 0.94, fired: true, calibrated: true, available: true, latency_ms: 15 },
      { name: 'convae', score: 0.88, fired: true, calibrated: false, available: true, latency_ms: 42 },
      { name: 'resnet_onnx', score: 0.81, fired: true, calibrated: false, available: true, latency_ms: 30 },
    ],
  },
};

const mockSplitDecision: Incident = {
  id: 'DEV-SPLIT-DECISION',
  rowid: 2,
  camera_id: 102,
  starting_frame_id: 65,
  crash_time: '2026-11-01 12:05:00',
  city: 'Alexandria',
  district: 'Corniche',
  thumbnail_url: '/placeholder-thumbnail.svg',
  video_url: '/video.mp4',
  review_status: 'unreviewed',
  model_scores: {
    policy: 'majority',
    threshold: 0.5,
    decision: true,
    scorers: [
      { name: 'vif_svm', score: 0.82, fired: true, calibrated: true, available: true, latency_ms: 18 },
      { name: 'convae', score: 0.74, fired: true, calibrated: false, available: true, latency_ms: 44 },
      { name: 'resnet_onnx', score: 0.35, fired: false, calibrated: false, available: true, latency_ms: 28 },
    ],
  },
};

const mockOneFlagged: Incident = {
  id: 'DEV-ONE-FLAGGED',
  rowid: 3,
  camera_id: 103,
  starting_frame_id: 88,
  crash_time: '2026-11-01 12:10:00',
  city: 'Gizah',
  district: 'Dokki',
  thumbnail_url: '/placeholder-thumbnail.svg',
  video_url: '/video.mp4',
  review_status: 'unreviewed',
  model_scores: {
    policy: 'any',
    threshold: 0.5,
    decision: true,
    scorers: [
      { name: 'vif_svm', score: 0.79, fired: true, calibrated: true, available: true, latency_ms: 17 },
      { name: 'convae', score: 0.28, fired: false, calibrated: false, available: true, latency_ms: 39 },
      { name: 'resnet_onnx', score: 0.19, fired: false, calibrated: false, available: true, latency_ms: 27 },
    ],
  },
};

const mockDegraded: Incident = {
  id: 'DEV-DEGRADED',
  rowid: 4,
  camera_id: 104,
  starting_frame_id: 112,
  crash_time: '2026-11-01 12:15:00',
  city: 'Port Said',
  district: 'Harbor',
  thumbnail_url: '/placeholder-thumbnail.svg',
  video_url: '/video.mp4',
  review_status: 'unreviewed',
  model_scores: {
    policy: 'majority',
    threshold: 0.5,
    decision: true,
    scorers: [
      { name: 'vif_svm', score: 0.91, fired: true, calibrated: true, available: true, latency_ms: 16 },
      { name: 'convae', score: 0.0, fired: false, calibrated: false, available: false, reason_unavailable: 'PyTorch extra not installed' },
      { name: 'resnet_onnx', score: 0.85, fired: true, calibrated: false, available: true, latency_ms: 33 },
    ],
  },
};

const mockNullScores: Incident = {
  id: 'DEV-NULL-SCORES',
  rowid: 5,
  camera_id: 105,
  starting_frame_id: 15,
  crash_time: '2026-11-01 09:00:00',
  city: 'Luxor',
  district: 'East Bank',
  thumbnail_url: '/placeholder-thumbnail.svg',
  video_url: '/video.mp4',
  review_status: 'confirmed',
  model_scores: null,
};

export function DevComponentShowcase() {
  return (
    <div className="space-y-8 pb-12" data-testid="dev-components-showcase">
      <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Cpu className="w-6 h-6 text-cyan-400" />
          <h1 className="text-xl font-bold font-mono text-slate-900 dark:text-white uppercase tracking-wider">
            Dev Component Showcase: ModelScoreBreakdown
          </h1>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Internal development storybook showing all operator-facing ML score breakdown states and edge cases.
        </p>
      </div>

      {/* State 1: All Agree */}
      <section className="space-y-3" data-testid="state-all-agree">
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <h2 className="text-sm font-semibold font-mono text-slate-800 dark:text-slate-200 uppercase">
            1. All Models Agree (Consensus)
          </h2>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <ModelScoreBreakdown incident={mockAllAgree} />
        </div>
      </section>

      {/* State 2: Split Decision */}
      <section className="space-y-3" data-testid="state-split-decision">
        <div className="flex items-center gap-2">
          <Split className="w-4 h-4 text-cyan-400" />
          <h2 className="text-sm font-semibold font-mono text-slate-800 dark:text-slate-200 uppercase">
            2. Split Decision (Majority 2 of 3 Flagged)
          </h2>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <ModelScoreBreakdown incident={mockSplitDecision} />
        </div>
      </section>

      {/* State 3: One Flagged */}
      <section className="space-y-3" data-testid="state-one-flagged">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <h2 className="text-sm font-semibold font-mono text-slate-800 dark:text-slate-200 uppercase">
            3. Only One Model Flagged ('any' policy alert)
          </h2>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <ModelScoreBreakdown incident={mockOneFlagged} />
        </div>
      </section>

      {/* State 4: Degraded Ensemble */}
      <section className="space-y-3" data-testid="state-degraded">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <h2 className="text-sm font-semibold font-mono text-slate-800 dark:text-slate-200 uppercase">
            4. Degraded Mode (Scorer Unavailable)
          </h2>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <ModelScoreBreakdown incident={mockDegraded} />
        </div>
      </section>

      {/* State 5: Null Scores (Legacy Incident) */}
      <section className="space-y-3" data-testid="state-null-scores">
        <div className="flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-slate-400" />
          <h2 className="text-sm font-semibold font-mono text-slate-800 dark:text-slate-200 uppercase">
            5. Legacy Incident (Null model_scores)
          </h2>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <ModelScoreBreakdown incident={mockNullScores} />
        </div>
      </section>
    </div>
  );
}

export default DevComponentShowcase;

