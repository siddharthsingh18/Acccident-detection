import React from 'react';
import { FileText } from 'lucide-react';
import { ComingSoonState } from '@/components/ComingSoonState';

export const Reports: React.FC = () => {
  return (
    <ComingSoonState
      title="Incident Reports"
      section="INCIDENTS"
      icon={FileText}
      phase="Phase 7"
      description="Formal decision-support audit documentation and summary reports for traffic authorities, municipal engineers, and emergency services."
      highlights={[
        "Custom date and time range export filters",
        "Direct one-click CSV summary data export",
        "Print-ready PDF report generation with decision-support disclaimers",
        "KPI summary executive cards and reviewed incident audit logs"
      ]}
    />
  );
};

export default Reports;
