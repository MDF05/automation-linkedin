import React from 'react';
import { clsx } from 'clsx';
import { Badge } from '../atoms';

export interface StatCardProps {
  label: string;
  value: string | number;
  /** Optional trend indicator shown as a badge */
  trend?: { label: string; positive?: boolean };
  /** Optional icon element rendered above the value */
  icon?: React.ReactNode;
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  trend,
  icon,
  className,
}) => {
  return (
    <div
      className={clsx(
        'flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-5 shadow-sm',
        className,
      )}
    >
      {icon && <div className="text-gray-400">{icon}</div>}
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {trend && (
        <Badge
          label={trend.label}
          color={trend.positive ? 'green' : 'red'}
        />
      )}
    </div>
  );
};
