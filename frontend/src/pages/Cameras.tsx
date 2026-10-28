import React from 'react';
import { Camera } from 'lucide-react';
import { ComingSoonState } from '@/components/ComingSoonState';

export const Cameras: React.FC = () => {
  return (
    <ComingSoonState
      title="Cameras"
      section="SOURCES"
      icon={Camera}
      phase="Phase 5"
      description="Traffic surveillance camera registry and feed configuration. Manage camera locations, stream sources (file, webcam, RTSP), and verify live stream reachability."
      highlights={[
        "Camera registry with GPS coordinates, city, and district indexing",
        "Source configuration: Video Files, Webcams, and RTSP stream addresses",
        "Stream connection verification and ffprobe container diagnostics",
        "Secure credential masking for authenticated RTSP stream URLs"
      ]}
    />
  );
};

export default Cameras;
