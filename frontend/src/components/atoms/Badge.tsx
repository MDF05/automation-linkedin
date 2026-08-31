import React from 'react';
import { clsx } from 'clsx';

export interface BadgeProps {
  color?: 'green' | 'red' | 'yellow' | 'blue' | 'gray';
  label: string;
  className?: string;
}

const colorClasses: Record<NonNullable<BadgeProps['color']>, string> = {
  green: 'bg-green-100 text-green-800',
  red: 'bg-red-100 text-red-800',
  yellow: 'bg-yellow-100 text-yellow-800',
  blue: 'bg-blue-100 text-blue-800',
  gray: 'bg-gray-100 text-gray-700',
};

export const Badge: React.FC<BadgeProps> = ({ color = 'gray', label, className }) => {
  return (
    <span
      className={clsx(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        colorClasses[color],
        className,
      )}
    >
      {label}
    </span>
  );
};
