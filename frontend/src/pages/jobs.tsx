/**
 * Jobs — halaman Job Hunter (Module D): cari & lamar lowongan otomatis.
 * Requirements: 5.1–5.10
 */

import React, { useEffect, useState, useCallback } from 'react';
import { AlertCircle, CheckCircle2, BarChart2 } from 'lucide-react';

import { DashboardLayout } from '@/components/templates';
import { JobCriteriaForm } from '@/components/organisms';
import { JobCard, StatCard } from '@/components/molecules';
import { Button, Spinner, Badge } from '@/components/atoms';
import { searchJobs, getJobApplications, getJobStats, exportJobApplications } from '@/lib/api';
import type { JobApplication, JobStatsResponse } from '@/types';
import type { JobCriteriaValues } from '@/components/organisms/JobCriteriaForm';

export default function JobsPage() {
  const [searching, setSearching] = useState(false);
  const [applications, setApplications] = useState<JobApplication[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [stats, setStats] = useState<JobStatsResponse | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchJobs = useCallback(
    async (p = 1, status = statusFilter) => {
      setLoadingData(true);
      try {
        const res = await getJobApplications({
          page: p,
          page_size: 20,
          status: status || undefined,
        });
        setApplications(res.items);
        setTotal(res.total);
        setPage(p);
      } catch {
        // silent
      } finally {
        setLoadingData(false);
      }
    },
    [statusFilter],
  );

  const fetchStats = useCallback(async () => {
    try {
      const s = await getJobStats();
      setStats(s);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchJobs(1);
    fetchStats();
  }, [fetchJobs, fetchStats]);

  const handleSearch = async (values: JobCriteriaValues) => {
    setSearching(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const keywords = values.titles
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      await searchJobs({
        keywords,
        location: values.location || undefined,
        job_type: values.job_type || undefined,
      });
      setSuccessMsg('Job hunting dimulai! Bot sedang mencari lowongan.');
      // Refresh data after a moment
      setTimeout(() => {
        fetchJobs(1);
        fetchStats();
      }, 2000);
    } catch {
      setErrorMsg('Gagal memulai job hunting. Pastikan HP terhubung.');
    } finally {
      setSearching(false);
    }
  };

  const handleExport = async () => {
    try {
      const blob = await exportJobApplications();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `job_applications_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setErrorMsg('Gagal export CSV.');
    }
  };

  const STATUS_FILTERS = [
    { value: '', label: 'Semua' },
    { value: 'found', label: 'Found' },
    { value: 'applied', label: 'Applied' },
    { value: 'skipped', label: 'Skipped' },
    { value: 'rejected', label: 'Rejected' },
    { value: 'interview', label: 'Interview' },
    { value: 'offer', label: 'Offer' },
  ];

  return (
    <DashboardLayout title="Job Hunter">
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
        {stats && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard
              label="Total Ditemukan"
              value={stats.by_status?.found ?? 0}
              icon={<BarChart2 size={18} />}
            />
            <StatCard
              label="Terlamar"
              value={stats.by_status?.applied ?? 0}
            />
            <StatCard
              label="Dilewati"
              value={stats.by_status?.skipped ?? 0}
            />
            <StatCard
              label="Minggu Ini"
              value={stats.this_week}
            />
          </div>
        )}

        {/* Search form */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-gray-800">Kriteria Pencarian</h2>
          <JobCriteriaForm onSubmit={handleSearch} loading={searching} />
        </div>

        {/* Applications list */}
        <div className="space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-sm font-semibold text-gray-800">Lowongan</h2>
              <span className="text-xs text-gray-400">({total})</span>
            </div>
            <div className="flex items-center gap-2">
              {/* Status filter pills */}
              <div className="flex gap-1 flex-wrap">
                {STATUS_FILTERS.map((f) => (
                  <button
                    key={f.value}
                    onClick={() => {
                      setStatusFilter(f.value);
                      fetchJobs(1, f.value);
                    }}
                    className={`rounded-full px-3 py-0.5 text-xs font-medium transition-colors ${
                      statusFilter === f.value
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
              <Button variant="secondary" size="sm" onClick={handleExport}>
                Export CSV
              </Button>
            </div>
          </div>

          {loadingData ? (
            <div className="flex h-32 items-center justify-center">
              <Spinner size="md" />
            </div>
          ) : applications.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white p-8 text-center text-sm text-gray-400">
              Belum ada lowongan. Mulai cari dengan form di atas.
            </div>
          ) : (
            <div className="space-y-2">
              {applications.map((job) => (
                <JobCard
                  key={job.id}
                  job={{
                    id: job.id,
                    job_title: job.job_title,
                    company: job.company,
                    location: job.location,
                    job_type: job.job_type,
                    status: job.status,
                    has_easy_apply: job.has_easy_apply,
                    applied_at: job.applied_at,
                  }}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {total > 20 && (
            <div className="flex items-center justify-between text-sm text-gray-500">
              <span>Total: {total} lowongan</span>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => fetchJobs(page - 1)}
                >
                  Prev
                </Button>
                <span className="flex items-center px-2">Hal {page}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={page * 20 >= total}
                  onClick={() => fetchJobs(page + 1)}
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
