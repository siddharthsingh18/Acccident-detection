import React from 'react';
import { CheckCircle2, XCircle, Clock } from 'lucide-react';

export type ReviewStatusType = 'confirmed' | 'false_alarm' | 'unreviewed' | null | undefined;

interface ReviewBadgeProps {
  status: ReviewStatusType;
  showIcon?: boolean;
  size?: 'sm' | 'md';
}

export const ReviewBadge: React.FC<ReviewBadgeProps> = ({
  status,
  showIcon = true,
  size = 'md',
}) => {
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';

  if (status === 'confirmed') {
    return (
      <span
        data-testid="review-badge-confirmed"
        className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-red-500/20 text-red-400 border border-red-500/40 shadow-[0_0_8px_rgba(239,68,68,0.2)] ${sizeClasses}`}
      >
        {showIcon && <CheckCircle2 className={`${iconSize} text-red-400 shrink-0`} />}
        <span>Confirmed Crash</span>
      </span>
    );
  }

  if (status === 'false_alarm') {
    return (
      <span
        data-testid="review-badge-false-alarm"
        className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-[0_0_8px_rgba(16,185,129,0.2)] ${sizeClasses}`}
      >
        {showIcon && <XCircle className={`${iconSize} text-emerald-400 shrink-0`} />}
        <span>False Alarm</span>
      </span>
    );
  }

  // Unreviewed / null / empty
  return (
    <span
      data-testid="review-badge-unreviewed"
      className={`inline-flex items-center gap-1.5 font-medium rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 ${sizeClasses}`}
    >
      {showIcon && <Clock className={`${iconSize} text-amber-400 shrink-0`} />}
      <span>Unreviewed</span>
    </span>
  );
};

export default ReviewBadge;
