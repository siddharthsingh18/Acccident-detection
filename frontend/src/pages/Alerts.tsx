import React from 'react';
import { Bell } from 'lucide-react';
import { ComingSoonState } from '@/components/ComingSoonState';

export const Alerts: React.FC = () => {
  return (
    <ComingSoonState
      title="Alerts & Notifications"
      section="CONFIGURATION"
      icon={Bell}
      phase="Phase 4"
      description="Real-time multi-channel dispatch integration. Automatically notify first responders and traffic operators via Telegram bots and custom HTTP webhooks when an accident is detected."
      highlights={[
        "Telegram bot token and chat destination configuration status",
        "Generic HTTP webhook dispatch with JSON incident payload",
        "Test alert dispatch trigger with live latency feedback",
        "Audit log of last 20 dispatch attempts with delivery status and rate-limiting"
      ]}
    />
  );
};

export default Alerts;
