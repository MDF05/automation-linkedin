/**
 * Engage — halaman untuk Module C: Auto Interaksi dengan Audiens.
 * Requirements: 4.1–4.10
 */

import React, { useEffect, useState, useCallback } from 'react';
import { Play, Square, AlertCircle, CheckCircle2 } from 'lucide-react';

import { DashboardLayout } from '@/components/templates';
import { StatCard } from '@/components/molecules';
import { Button, Input, Spinner, Badge } from '@/components/atoms';
import { startEngage, stopEngage, getInteractions, exportInteractions } from '@/lib/api';
import { useBotProgress } from '@/hooks';
import type { Interaction } from '@/types';

export default function EngagePage() {
  const [sessionStatus, setSessionStatus] = useState<'idle' | 'running' | 'stopped'>('idle');
  const [topicFilter, setTopicFilter] = useState('');
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loadingData, setLoadingData] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const { isRunning, steps, error: botError, currentModule } = useBotProgress();

  const fetchInteractions = useCallback(async (p = 1) => {
    setLoadingData(true);
    try {
      const res = await getInteractions({ page: p, page_size: 20 });
      setInteractions(res.items);
      setTotal(res.total);
      setPage(p);
    } catch {
      // silent
    } finally {
      setLoadingData(false);
    }
  }, []);

  useEffect(() => {
    fetchInteractions(1);
  }, [fetchInteractions]);

  const handleStart = async () => {
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const topicFilters = topicFilter
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      await startEngage({ topic_filters: topicFilters.length > 0 ? topicFilters : undefined });
      setSessionStatus('running');
      setSuccessMsg('Sesi Engage dimulai! Bot sedang berjalan.');
    } catch {
      setErrorMsg('Gagal memulai sesi Engage. Pastikan HP terhubung.');
    }
  };

  const handleStop = async () => {
    setErrorMsg(null);
    try {
      await stopEngage();
      setSessionStatus('stopped');
      setSuccessMsg('Sesi Engage dihentikan.');
      // Refresh interactions
      await fetchInteractions(1);
    } catch {
      setErrorMsg('Gagal menghentikan sesi.');
    }
  };

  const handleExport = async () => {
    try {
      const blob = await exportInteractions();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `interactions_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setErrorMsg('Gagal export CSV.');
    }
  };

  const isSessionRunning = isRunning && currentModule === 'C';
  const todayInteractions = interactions.filter(
    (i) => new Date(i.created_at).toDateString() === new Date().toDateString(),
  ).length;

  return (
    <DashboardLayout title="Engage">
      <div className="space-y-6">
        {/* Feedback banners */}
        {errorMsg && (
          <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle size={16} className="shrink-0" />
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
            <CheckCircle2 size={16} className="shrink-0" />
            {successMsg}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <StatCard label="Total Interaksi" value={total} />
          <StatCard label="Interaksi Hari Ini" value={todayInteractions} />
          <StatCard
            label="Status Sesi"
            value={isSessionRunning ? 'Berjalan' : 'Tidak Aktif'}
            trend={
              isSessionRunning
                ? { label: 'Running', positive: true }
                : undefined
            }
          />
        </div>

        {/* Controls */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-4">
          <h2 className="text-sm font-semibold text-gray-800">Kontrol Sesi Engage</h2>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="mb-1 block text-xs font-medium text-gray-600">
                Filter Topik (opsional, pisahkan koma)
              </label>
              <Input
                value={topicFilter}
                onChange={(e) => setTopicFilter(e.target.value)}
                placeholder="Contoh: Python, AI, Startup"
                disabled={isSessionRunning}
              />
            </div>

            {!isSessionRunning ? (
              <Button
                variant="primary"
                onClick={handleStart}
                className="shrink-0"
              >
                <Play size={16} />
                Mulai Engage
              </Button>
            ) : (
              <Button
                variant="danger"
                onClick={handleStop}
                className="shrink-0"
              >
                <Square size={16} />
                Hentikan
              </Button>
            )}
          </div>

          {/* Live progress */}
          {isSessionRunning && (
            <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 space-y-1">
              <div className="flex items-center gap-2">
                <Spinner size="sm" />
                <span className="text-sm font-medium text-blue-800">Sesi berjalan...</span>
              </div>
              {steps.slice(-5).map((step, i) => (
                <p key={i} className="text-xs text-blue-700 pl-6">
                  {step.message}
                </p>
              ))}
            </div>
          )}

          {botError && (
            <div className="flex items-center gap-2 rounded-lg border border-red-100 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle size={14} className="shrink-0" />
              {botError}
            </div>
          )}
        </div>

        {/* Interactions log */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-800">Riwayat Interaksi</h2>
            <Button variant="secondary" size="sm" onClick={handleExport}>
              Export CSV
            </Button>
          </div>

          {loadingData ? (
            <div className="flex h-32 items-center justify-center">
              <Spinner size="md" />
            </div>
          ) : interactions.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white p-8 text-center text-sm text-gray-400">
              Belum ada interaksi tercatat.
            </div>
          ) : (
            <div className="rounded-xl border border-gray-200 bg-white divide-y divide-gray-100">
              {interactions.map((i) => (
                <div key={i.id} className="flex items-start gap-3 px-4 py-3">
                  <Badge
                    label={i.status}
                    color={
                      i.status === 'success'
                        ? 'green'
                        : i.status === 'failed'
                        ? 'red'
                        : 'gray'
                    }
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-700 truncate">
                      {i.content_sent ?? i.skip_reason ?? '—'}
                    </p>
                    <p className="text-xs text-gray-400">
                      {i.target_author ?? 'Unknown'} •{' '}
                      {new Date(i.created_at).toLocaleString('id-ID')}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {total > 20 && (
            <div className="flex items-center justify-between text-sm text-gray-500">
              <span>Total: {total} interaksi</span>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => fetchInteractions(page - 1)}
                >
                  Prev
                </Button>
                <span className="flex items-center px-2">Hal {page}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={page * 20 >= total}
                  onClick={() => fetchInteractions(page + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
