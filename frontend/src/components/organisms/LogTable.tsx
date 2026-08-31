import React, { useState } from 'react';
import { Select, Button, Input } from '../atoms';
import { LogRow, LogRowData } from '../molecules';
import { FormField } from '../molecules';

export interface LogTableProps {
  logs: LogRowData[];
  onRowClick?: (log: LogRowData) => void;
  onExport?: () => void;
  loading?: boolean;
  total?: number;
  page?: number;
  onPageChange?: (page: number) => void;
}

const STATUS_OPTIONS = [
  { value: '', label: 'Semua Status' },
  { value: 'success', label: 'Success' },
  { value: 'failed', label: 'Failed' },
  { value: 'running', label: 'Running' },
  { value: 'skipped', label: 'Skipped' },
  { value: 'timeout', label: 'Timeout' },
];

export interface LogFilters {
  status: string;
  date_from: string;
  date_to: string;
}

export const LogTable: React.FC<LogTableProps> = ({
  logs,
  onRowClick,
  onExport,
  loading,
  total = 0,
  page = 1,
  onPageChange,
}) => {
  const [filters, setFilters] = useState<LogFilters>({
    status: '',
    date_from: '',
    date_to: '',
  });

  return (
    <div className="flex flex-col gap-4">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-40">
          <FormField label="Status" htmlFor="log-status">
            <Select
              id="log-status"
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              options={STATUS_OPTIONS}
            />
          </FormField>
        </div>
        <div className="w-44">
          <FormField label="Dari" htmlFor="log-from">
            <Input
              id="log-from"
              type="date"
              value={filters.date_from}
              onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
            />
          </FormField>
        </div>
        <div className="w-44">
          <FormField label="Sampai" htmlFor="log-to">
            <Input
              id="log-to"
              type="date"
              value={filters.date_to}
              onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
            />
          </FormField>
        </div>
        {onExport && (
          <Button variant="secondary" size="sm" onClick={onExport}>
            Export CSV
          </Button>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full text-left">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Waktu</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Durasi</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Pesan</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">
                  Memuat...
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400">
                  Tidak ada log
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <LogRow key={log.id} log={log} onClick={onRowClick} />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 0 && onPageChange && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>Total: {total} entri</span>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
            >
              Prev
            </Button>
            <span className="flex items-center px-2">Hal {page}</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
