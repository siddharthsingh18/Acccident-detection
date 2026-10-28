import React from 'react';
import { Settings as SettingsIcon } from 'lucide-react';
import { ComingSoonState } from '@/components/ComingSoonState';

export const Settings: React.FC = () => {
  return (
    <ComingSoonState
      title="System Settings"
      section="CONFIGURATION"
      icon={SettingsIcon}
      phase="Phase 3"
      description="Control room audio alarms, media clip retention policies, and computer vision classification confidence thresholds."
      highlights={[
        "Audio alarm enable/disable toggle for live accident detections",
        "Control room siren volume control (0-100%)",
        "Video clip storage retention policy (automatic retention cleanup)",
        "Minimum collision detection confidence filter"
      ]}
    />
  );
};

export default Settings;
