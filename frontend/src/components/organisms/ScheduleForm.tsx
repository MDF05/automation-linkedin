import React, { useState } from 'react';
import { Button, Input, Select } from '../atoms';
import { FormField } from '../molecules';

const TASK_TYPES = [
  { value: 'post_konten', label: 'Post Konten' },
  { value: 'engage', label: 'Engage' },
  { value: 'job_hunt', label: 'Job Hunt' },
  { value: 'promosi', label: 'Promosi' },
];

const CRON_PRESETS = [
  { value: '', label: 'Custom...' },
  { value: '0 9 * * *', label: 'Setiap hari jam 09:00' },
  { value: '0 9 * * 1-5', label: 'Hari kerja jam 09:00' },
  { value: '0 */6 * * *', label: 'Setiap 6 jam' },
  { value: '0 8 * * 1', label: 'Setiap Senin jam 08:00' },
];

export interface ScheduleFormValues {
  name: string;
  task_type: string;
  cron_expression: string;
  is_active: boolean;
}

export interface ScheduleFormProps {
  initial?: Partial<ScheduleFormValues>;
  onSubmit: (values: ScheduleFormValues) => void;
  onCancel?: () => void;
  loading?: boolean;
}

export const ScheduleForm: React.FC<ScheduleFormProps> = ({
  initial,
  onSubmit,
  onCancel,
  loading,
}) => {
  const [values, setValues] = useState<ScheduleFormValues>({
    name: initial?.name ?? '',
    task_type: initial?.task_type ?? 'post_konten',
    cron_expression: initial?.cron_expression ?? '0 9 * * *',
    is_active: initial?.is_active ?? true,
  });
  const [errors, setErrors] = useState<Partial<ScheduleFormValues>>({});

  const validate = (): boolean => {
    const e: Partial<ScheduleFormValues> = {};
    if (!values.name.trim()) e.name = 'Nama wajib diisi';
    if (!values.cron_expression.trim()) e.cron_expression = 'Cron expression wajib diisi';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) onSubmit(values);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <FormField label="Nama Jadwal" htmlFor="sched-name" required error={errors.name}>
        <Input
          id="sched-name"
          value={values.name}
          onChange={(e) => setValues({ ...values, name: e.target.value })}
          placeholder="Contoh: Post Harian Pagi"
          error={errors.name}
        />
      </FormField>

      <FormField label="Tipe Tugas" htmlFor="sched-type">
        <Select
          id="sched-type"
          value={values.task_type}
          onChange={(e) => setValues({ ...values, task_type: e.target.value })}
          options={TASK_TYPES}
        />
      </FormField>

      <FormField label="Preset Jadwal" htmlFor="sched-preset">
        <Select
          id="sched-preset"
          value={CRON_PRESETS.find(p => p.value === values.cron_expression)?.value ?? ''}
          onChange={(e) => {
            if (e.target.value) setValues({ ...values, cron_expression: e.target.value });
          }}
          options={CRON_PRESETS}
        />
      </FormField>

      <FormField label="Cron Expression" htmlFor="sched-cron" error={errors.cron_expression}
        hint="Format: menit jam hari bulan hari-minggu">
        <Input
          id="sched-cron"
          value={values.cron_expression}
          onChange={(e) => setValues({ ...values, cron_expression: e.target.value })}
          placeholder="0 9 * * *"
          className="font-mono"
          error={errors.cron_expression}
        />
      </FormField>

      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
        <input
          type="checkbox"
          checked={values.is_active}
          onChange={(e) => setValues({ ...values, is_active: e.target.checked })}
          className="rounded border-gray-300"
        />
        Aktifkan jadwal
      </label>

      <div className="flex gap-3">
        <Button type="submit" variant="primary" loading={loading} disabled={loading}>
          Simpan
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Batal
          </Button>
        )}
      </div>
    </form>
  );
};
