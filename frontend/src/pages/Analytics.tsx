import React from 'react';
import { BarChart3 } from 'lucide-react';
import { ComingSoonState } from '@/components/ComingSoonState';

export const Analytics: React.FC = () => {
  return (
    <ComingSoonState
      title="Surveillance Analytics"
      section="INCIDENTS"
      icon={BarChart3}
      phase="Phase 6"
      description="Statistical intelligence and incident trend aggregation across monitored intersections. Analyze daily incident distributions, peak crash hours, high-risk intersections, and operator review metrics."
      highlights={[
        "Interactive time-series charts for incidents per day and incidents per hour",
        "Top 10 highest-incident surveillance camera rankings",
        "Triage breakdown: Confirmed vs. False Alarm vs. Unreviewed rates",
        "Mean time to operator verification (MTTR) performance metrics"
      ]}
    />
  );
};

export default Analytics;
