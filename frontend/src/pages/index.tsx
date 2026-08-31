/**
 * Dashboard Overview — halaman utama ringkasan aktivitas bot.
 * Requirements: 5.10, 7.3
 */

import React, { useEffect, useState } from 'react';
import { LayoutDashboard, FileText, MessageSquare, Briefcase, Smartphone } from 'lucide-react';

import { DashboardLayout } from '@/components/templates';
import { StatCard } from '@/components/molecules';
import { Spinner } from '@/components/atoms';
import { getPosts, getInteractions, getJobStats, getDeviceStatus } from '@/lib/api';
import type { DeviceStatus, JobStatsResponse } from '@/types';

interface DashboardStats {
  totalPosts: number;
  totalInteractions: number;
  totalApplied: number;
  deviceConnected: boolean;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const [postsRes, interactionsRes, jobStatsRes, deviceRes] = await Promise.allSettled([
          getPosts({ page_size: 1 }),
          getInteractions({ page_size: 1 }),
          getJobStats(),
          getDeviceStatus(),
        ]);

        const totalPosts =
          postsRes.status === 'fulfilled' ? postsRes.value.total : 0;
        const totalInteractions =
          interactionsRes.status === 'fulfilled' ? interactionsRes.value.total : 0;
        const totalApplied =
          jobStatsRes.status === 'fulfilled'
            ? (jobStatsRes.value as JobStatsResponse).by_status?.applied ?? 0
            : 0;
        const deviceConnected =
          deviceRes.status === 'fulfilled'
            ? (deviceRes.value as DeviceStatus).connected
            : false;

        setStats({ totalPosts, totalInteractions, totalApplied, deviceConnected });
      } catch {
        // partial failure — show what we have
        setStats({ totalPosts: 0, totalInteractions: 0, totalApplied: 0, deviceConnected: false });
      } finally {
        setLoading(false);
      }
    }

    fetchStats();
  }, []);

  return (
    <DashboardLayout title="Dashboard">
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Spinner size="lg" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Stats grid */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Total Posts"
              value={stats?.totalPosts ?? 0}
              icon={<FileText size={20} />}
            />
            <StatCard
              label="Total Interaksi"
              value={stats?.totalInteractions ?? 0}
              icon={<MessageSquare size={20} />}
            />
            <StatCard
              label="Lamaran Terkirim"
              value={stats?.totalApplied ?? 0}
              icon={<Briefcase size={20} />}
            />
            <StatCard
              label="Status HP"
              value={stats?.deviceConnected ? 'Terhubung' : 'Terputus'}
              icon={<Smartphone size={20} />}
              trend={
                stats?.deviceConnected
                  ? { label: 'Online', positive: true }
                  : { label: 'Offline', positive: false }
              }
            />
          </div>

          {/* Quick links */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <LayoutDashboard size={18} className="text-blue-600" />
              <h2 className="text-sm font-semibold text-gray-800">Mulai Cepat</h2>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { href: '/studio', label: 'Buat Konten', color: 'bg-blue-50 text-blue-700 hover:bg-blue-100' },
                { href: '/engage', label: 'Mulai Engage', color: 'bg-purple-50 text-purple-700 hover:bg-purple-100' },
                { href: '/jobs', label: 'Cari Lowongan', color: 'bg-green-50 text-green-700 hover:bg-green-100' },
                { href: '/schedule', label: 'Atur Jadwal', color: 'bg-orange-50 text-orange-700 hover:bg-orange-100' },
              ].map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className={`rounded-lg px-4 py-3 text-sm font-medium transition-colors text-center ${item.color}`}
                >
                  {item.label}
                </a>
              ))}
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
