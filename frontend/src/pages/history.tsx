/**
 * History — halaman History & Logs: riwayat semua aktivitas bot.
 * Requirements: 7.1–7.7, 11.1–11.4
 */

import React, { useEffect, useState, useCallback } from 'react';
import { AlertCircle, X } from 'lucide-react';

import { DashboardLayout } from '@/components/templates';
import { LogTable } from '@/components/organisms';
import { Button, Spinner, Badge } from '@/components/atoms';
import { getLogs, getLog, exportLogs } from '@/lib/api';
import type { BotLog } from '@/types';
import type { LogRowData } from '@/components/molecules/LogRow';

const BASE_URL =
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL
    : 'http://localhost:8000';

function botLogToRowData(log: BotLog): LogRowData {
  return {
    id: log.id,
    action: log.action,
    status: log.status,
    message: log.message,
    duration_ms: log.duration_ms,
    module: log.module,
    created_at: log.created_at,
  };
}

interface LogDetailModalProps {
  log: BotLog;
  onClose: () => void;
}

function LogDetailModal({ log, onClose }: LogDetailModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal
      aria-label="Detail log"
    >
      <div className="relative w-full max-w-2xl rounded-2xl border border-gray-200 bg-white shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 flex items-center justify-between border-b border-gray-100 bg-white px-5 py-4">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-semibold text-gray-800">Log #{log.id}</h2>
            <Badge
              label={log.status}
              color={
                log.status === 'success'
                  ? 'green'
                  : log.status === 'failed' || log.status === 'timeout'
                  ? 'red'
                  : log.status === 'running'
                  ? 'blue'
                  : 'gray'
              }
            />
            {log.module && (
              <Badge label={`Module ${log.module}`} color="blue" />
            )}
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
            aria-label="Tutup modal"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Basic info */}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div>
              <dt className="text-xs font-medium text-gray-500">Aksi</dt>
              <dd className="text-gray-800">{log.action}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-gray-500">Durasi</dt>
              <dd className="text-gray-800">
                {log.duration_ms != null ? `${log.duration_ms}ms` : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-gray-500">Waktu</dt>
              <dd className="text-gray-800">
                {new Date(log.created_at).toLocaleString('id-ID')}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-gray-500">Task ID</dt>
              <dd className="font-mono text-xs text-gray-600 break-all">{log.task_id}</dd>
            </div>
          </dl>

          {/* Message */}
          {log.message && (
            <div>
              <p className="mb-1 text-xs font-medium text-gray-500">Pesan</p>
              <p className="rounded-md bg-gray-50 p-3 text-sm text-gray-700 whitespace-pre-wrap">
                {log.message}
              </p>
            </div>
          )}

          {/* Error detail */}
          {log.error_detail && (
            <div>
              <p className="mb-1 text-xs font-medium text-red-600">Detail Error</p>
              <pre className="rounded-md bg-red-50 p-3 text-xs text-red-800 overflow-x-auto whitespace-pre-wrap">
                {log.error_detail}
              </pre>
            </div>
          )}

          {/* Stack trace */}
          {log.stack_trace && (
            <div>
              <p className="mb-1 text-xs font-medium text-gray-500">Stack Trace</p>
              <pre className="rounded-md bg-gray-50 p-3 text-xs text-gray-600 overflow-x-auto whitespace-pre-wrap max-h-48">
                {log.stack_trace}
              </pre>
            </div>
          )}

          {/* Screenshot */}
          {log.screenshot_path && (
            <div>
              <p className="mb-2 text-xs font-medium text-gray-500">Screenshot</p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`${BASE_URL}/static/${log.screenshot_path}`}
                alt="Screenshot aksi bot"
                className="rounded-lg border border-gray-200 max-h-72 w-full object-contain bg-gray-50"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function HistoryPage() {
  const [logs, setLogs] = useState<BotLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selectedLog, setSelectedLog] = useState<BotLog | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchLogs = useCallback(async (p = 1) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await getLogs({ page: p, page_size: 20 });
      setLogs(res.items);
      setTotal(res.total);
      setPage(p);
    } catch {
      setErrorMsg('Gagal memuat log. Pastikan backend berjalan.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs(1);
  }, [fetchLogs]);

  const handleRowClick = async (row: LogRowData) => {
    setLoadingDetail(true);
    try {
      const detail = await getLog(row.id);
      setSelectedLog(detail);
    } catch {
      setErrorMsg('Gagal memuat detail log.');
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleExport = async () => {
    setErrorMsg(null);
    try {
      const blob = await exportLogs();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `bot_logs_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setErrorMsg('Gagal export CSV.');
    }
  };

  const rowData: LogRowData[] = logs.map(botLogToRowData);

  return (
    <DashboardLayout title="History & Logs">
      <div className="space-y-4">
        {/* Feedback */}
        {errorMsg && (
          <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle size={16} className="shrink-0" />
            {errorMsg}
          </div>
        )}

        {loadingDetail && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Spinner size="sm" />
            Memuat detail...
          </div>
        )}

        <LogTable
          logs={rowData}
          onRowClick={handleRowClick}
          onExport={handleExport}
          loading={loading}
          total={total}
          page={page}
          onPageChange={fetchLogs}
        />
      </div>

      {/* Detail modal */}
      {selectedLog && (
        <LogDetailModal
          log={selectedLog}
          onClose={() => setSelectedLog(null)}
        />
      )}
    </DashboardLayout>
  );
}
