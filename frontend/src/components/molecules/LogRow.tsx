import React from 'react';
import { Badge } from '../atoms';

export interface LogRowData {
  id: number;
  action: string;
  status: 'success' | 'failed' | 'running' | 'skipped' | 'timeout';
  message?: string | null;
  duration_ms?: number | null;
  module?: string | null;
  created_at: string;
}

export interface LogRowProps {
  log: LogRowData;
  onClick?: (log: LogRowData) => void;
}

const statusColor: Record<LogRowData['status'], 'green' | 'red' | 'blue' | 'gray' | 'yellow'> = {
  success: 'green',
  failed: 'red',
  running: 'blue',
  skipped: 'yellow',
  timeout: 'red',
};

function formatDuration(ms?: number | null): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('id-ID', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

export const LogRow: React.FC<LogRowProps> = ({ log, onClick }) => {
  return (
    <tr
      className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
      onClick={() => onClick?.(log)}
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick?.(log)}
      aria-label={`Log ${log.id}: ${log.action} — ${log.status}`}
    >
      <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
        {formatDate(log.created_at)}
      </td>
      <td className="px-4 py-3 text-sm font-medium text-gray-700 max-w-xs truncate">
        {log.action}
        {log.module && (
          <span className="ml-1.5 text-xs text-gray-400">[{log.module}]</span>
        )}
      </td>
      <td className="px-4 py-3">
        <Badge label={log.status} color={statusColor[log.status]} />
      </td>
      <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
        {formatDuration(log.duration_ms)}
      </td>
      <td className="px-4 py-3 text-sm text-gray-500 max-w-xs truncate">
        {log.message ?? '—'}
      </td>
    </tr>
  );
};
