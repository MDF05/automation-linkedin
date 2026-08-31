import React from 'react';
import { clsx } from 'clsx';
import { Badge } from '../atoms';

export interface ScheduleData {
  id: number;
  name: string;
  task_type: string;
  cron_expression?: string | null;
  is_active: boolean;
  last_run?: string | null;
  next_run?: string | null;
  last_status?: string | null;
  run_count: number;
}

export interface ScheduleItemProps {
  schedule: ScheduleData;
  onToggle: (schedule: ScheduleData) => void;
  onEdit?: (schedule: ScheduleData) => void;
  onDelete?: (schedule: ScheduleData) => void;
}

const taskTypeLabel: Record<string, string> = {
  post_konten: 'Post Konten',
  engage: 'Engage',
  job_hunt: 'Job Hunt',
  promosi: 'Promosi',
};

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('id-ID', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

export const ScheduleItem: React.FC<ScheduleItemProps> = ({
  schedule,
  onToggle,
  onEdit,
  onDelete,
}) => {
  return (
    <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-white px-4 py-3 gap-4">
      {/* Toggle */}
      <button
        role="switch"
        aria-checked={schedule.is_active}
        onClick={() => onToggle(schedule)}
        className={clsx(
          'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500',
          schedule.is_active ? 'bg-blue-600' : 'bg-gray-200',
        )}
        aria-label={`Toggle jadwal ${schedule.name}`}
      >
        <span
          className={clsx(
            'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200',
            schedule.is_active ? 'translate-x-4' : 'translate-x-0',
          )}
        />
      </button>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-gray-800 truncate">{schedule.name}</span>
          <Badge
            label={taskTypeLabel[schedule.task_type] ?? schedule.task_type}
            color="blue"
          />
          {schedule.last_status === 'failed' && (
            <Badge label="Gagal" color="red" />
          )}
        </div>
        <div className="flex items-center gap-3 mt-0.5 text-xs text-gray-400">
          {schedule.cron_expression && (
            <span className="font-mono">{schedule.cron_expression}</span>
          )}
          <span>Berikutnya: {formatDate(schedule.next_run)}</span>
          <span>Terakhir: {formatDate(schedule.last_run)}</span>
          <span>{schedule.run_count}× dijalankan</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        {onEdit && (
          <button
            onClick={() => onEdit(schedule)}
            className="rounded p-1 text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
            aria-label={`Edit jadwal ${schedule.name}`}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M15.232 5.232l3.536 3.536M9 13l6.536-6.536a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-.707.464l-3 1a1 1 0 01-1.265-1.265l1-3a2 2 0 01.464-.707z" />
            </svg>
          </button>
        )}
        {onDelete && (
          <button
            onClick={() => onDelete(schedule)}
            className="rounded p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
            aria-label={`Hapus jadwal ${schedule.name}`}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3M4 7h16" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
};
