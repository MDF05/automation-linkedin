import React from 'react';
import { clsx } from 'clsx';

export type StatusDotStatus = 'online' | 'offline' | 'warning' | 'error';

export interface StatusDotProps {
  status: StatusDotStatus;
  className?: string;
}

const colorMap: Record<StatusDotStatus, string> = {
  online: 'bg-green-500',
  offline: 'bg-gray-400',
  warning: 'bg-yellow-400',
  error: 'bg-red-500',
};

export const StatusDot: React.FC<StatusDotProps> = ({ status, className }) => {
  return (
    <span
      role="img"
      aria-label={status}
      className={clsx('inline-block h-2.5 w-2.5 rounded-full', colorMap[status], className)}
    />
  );
};
