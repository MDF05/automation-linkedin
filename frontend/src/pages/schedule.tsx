/**
 * Schedule — halaman Penjadwalan Otomatis.
 * Requirements: 6.1–6.7
 */

import React, { useEffect, useState, useCallback } from 'react';
import { Plus, AlertCircle, CheckCircle2, Calendar } from 'lucide-react';

import { DashboardLayout } from '@/components/templates';
import { ScheduleForm } from '@/components/organisms';
import { ScheduleItem } from '@/components/molecules';
import { Button, Spinner } from '@/components/atoms';
import {
  getSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  toggleSchedule,
} from '@/lib/api';
import type { Schedule, CreateScheduleRequest, UpdateScheduleRequest } from '@/types';
import type { ScheduleData } from '@/components/molecules/ScheduleItem';
import type { ScheduleFormValues } from '@/components/organisms/ScheduleForm';

function scheduleToData(s: Schedule): ScheduleData {
  return {
    id: s.id,
    name: s.name,
    task_type: s.task_type,
    cron_expression: s.cron_expression,
    is_active: s.is_active,
    last_run: s.last_run,
    next_run: s.next_run,
    last_status: s.last_status,
    run_count: s.run_count,
  };
}

export default function SchedulePage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editTarget, setEditTarget] = useState<Schedule | null>(null);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchSchedules = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getSchedules();
      setSchedules(data);
    } catch {
      setErrorMsg('Gagal memuat jadwal. Pastikan backend berjalan.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSchedules();
  }, [fetchSchedules]);

  const handleCreate = async (values: ScheduleFormValues) => {
    setSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const payload: CreateScheduleRequest = {
        name: values.name,
        task_type: values.task_type as Schedule['task_type'],
        cron_expression: values.cron_expression,
      };
      const created = await createSchedule(payload);
      setSchedules((prev) => [created, ...prev]);
      setShowForm(false);
      setSuccessMsg('Jadwal berhasil dibuat!');
    } catch {
      setErrorMsg('Gagal membuat jadwal.');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = async (values: ScheduleFormValues) => {
    if (!editTarget) return;
    setSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const payload: UpdateScheduleRequest = {
        name: values.name,
        cron_expression: values.cron_expression,
      };
      const updated = await updateSchedule(editTarget.id, payload);
      setSchedules((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setEditTarget(null);
      setShowForm(false);
      setSuccessMsg('Jadwal berhasil diperbarui!');
    } catch {
      setErrorMsg('Gagal memperbarui jadwal.');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (schedule: ScheduleData) => {
    setErrorMsg(null);
    try {
      const res = await toggleSchedule(schedule.id);
      setSchedules((prev) =>
        prev.map((s) =>
          s.id === schedule.id
            ? { ...s, is_active: res.is_active, next_run: res.next_run }
            : s,
        ),
      );
    } catch {
      setErrorMsg('Gagal mengubah status jadwal.');
    }
  };

  const handleDelete = async (schedule: ScheduleData) => {
    if (!confirm(`Hapus jadwal "${schedule.name}"?`)) return;
    setErrorMsg(null);
    try {
      await deleteSchedule(schedule.id);
      setSchedules((prev) => prev.filter((s) => s.id !== schedule.id));
      setSuccessMsg('Jadwal berhasil dihapus.');
    } catch {
      setErrorMsg('Gagal menghapus jadwal.');
    }
  };

  const handleOpenEdit = (schedule: ScheduleData) => {
    const full = schedules.find((s) => s.id === schedule.id);
    if (full) {
      setEditTarget(full);
      setShowForm(true);
    }
  };

  const editInitial: Partial<ScheduleFormValues> | undefined = editTarget
    ? {
        name: editTarget.name,
        task_type: editTarget.task_type,
        cron_expression: editTarget.cron_expression ?? '0 9 * * *',
        is_active: editTarget.is_active,
      }
    : undefined;

  const activeCount = schedules.filter((s) => s.is_active).length;

  return (
    <DashboardLayout title="Scheduler">
      <div className="space-y-6">
        {/* Feedback */}
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

        {/* Header with summary */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Calendar size={20} className="text-blue-600" />
            <div>
              <h2 className="text-sm font-semibold text-gray-800">Jadwal Terdaftar</h2>
              <p className="text-xs text-gray-500">
                {schedules.length} total • {activeCount} aktif
              </p>
            </div>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              setEditTarget(null);
              setShowForm((v) => !v);
            }}
          >
            <Plus size={14} />
            Tambah Jadwal
          </Button>
        </div>

        {/* Create / Edit form */}
        {showForm && (
          <div className="rounded-xl border border-blue-100 bg-blue-50 p-5 shadow-sm">
            <h3 className="mb-4 text-sm font-semibold text-blue-800">
              {editTarget ? 'Edit Jadwal' : 'Jadwal Baru'}
            </h3>
            <ScheduleForm
              initial={editInitial}
              onSubmit={editTarget ? handleEdit : handleCreate}
              onCancel={() => {
                setShowForm(false);
                setEditTarget(null);
              }}
              loading={saving}
            />
          </div>
        )}

        {/* Schedule list */}
        {loading ? (
          <div className="flex h-48 items-center justify-center">
            <Spinner size="lg" />
          </div>
        ) : schedules.length === 0 ? (
          <div className="rounded-xl border border-gray-200 bg-white p-8 text-center text-sm text-gray-400">
            Belum ada jadwal. Klik "Tambah Jadwal" untuk memulai.
          </div>
        ) : (
          <div className="space-y-2">
            {schedules.map((s) => (
              <ScheduleItem
                key={s.id}
                schedule={scheduleToData(s)}
                onToggle={handleToggle}
                onEdit={handleOpenEdit}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
