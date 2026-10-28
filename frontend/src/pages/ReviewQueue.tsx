import React from 'react';
import { ClipboardCheck } from 'lucide-react';
import { ComingSoonState } from '@/components/ComingSoonState';

export const ReviewQueue: React.FC = () => {
  return (
    <ComingSoonState
      title="Review Queue"
      section="MONITORING"
      icon={ClipboardCheck}
      phase="Phase 2"
      description="Human verification queue for candidate road-accident events. Operators review candidate crash footage, confirm incident classifications, or discard false alarms with rapid keyboard shortcuts."
      highlights={[
        "Chronological incident review queue (newest candidate crashes first)",
        "Inline H.264 video playback with range scrubbing and frame-by-frame inspection",
        "One-click Confirm and False Alarm classification buttons with operator notes",
        "Streamlined keyboard triage shortcuts: C (Confirm), F (False Alarm), J/K (Next/Previous)"
      ]}
    />
  );
};

export default ReviewQueue;
