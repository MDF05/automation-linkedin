import React, { useState } from 'react';
import { Button, Input, Select } from '../atoms';
import { FormField } from '../molecules';

const JOB_TYPES = [
  { value: '', label: 'Semua Tipe' },
  { value: 'full-time', label: 'Full-time' },
  { value: 'part-time', label: 'Part-time' },
  { value: 'kontrak', label: 'Kontrak' },
  { value: 'freelance', label: 'Freelance' },
];

export interface JobCriteriaValues {
  titles: string;
  skills: string;
  location: string;
  min_salary: string;
  job_type: string;
}

export interface JobCriteriaFormProps {
  onSubmit: (values: JobCriteriaValues) => void;
  loading?: boolean;
}

export const JobCriteriaForm: React.FC<JobCriteriaFormProps> = ({ onSubmit, loading }) => {
  const [values, setValues] = useState<JobCriteriaValues>({
    titles: '',
    skills: '',
    location: '',
    min_salary: '',
    job_type: '',
  });
  const [errors, setErrors] = useState<Partial<JobCriteriaValues>>({});

  const validate = (): boolean => {
    const e: Partial<JobCriteriaValues> = {};
    if (!values.titles.trim()) e.titles = 'Minimal satu judul posisi';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) onSubmit(values);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <FormField label="Judul Posisi" htmlFor="job-titles" required error={errors.titles}
        hint="Pisahkan beberapa posisi dengan koma">
        <Input
          id="job-titles"
          value={values.titles}
          onChange={(e) => setValues({ ...values, titles: e.target.value })}
          placeholder="Contoh: Software Engineer, Backend Developer"
          error={errors.titles}
        />
      </FormField>

      <FormField label="Skill" htmlFor="job-skills" hint="Pisahkan dengan koma">
        <Input
          id="job-skills"
          value={values.skills}
          onChange={(e) => setValues({ ...values, skills: e.target.value })}
          placeholder="Contoh: Python, FastAPI, PostgreSQL"
        />
      </FormField>

      <div className="grid grid-cols-2 gap-3">
        <FormField label="Lokasi" htmlFor="job-location">
          <Input
            id="job-location"
            value={values.location}
            onChange={(e) => setValues({ ...values, location: e.target.value })}
            placeholder="Contoh: Jakarta atau Remote"
          />
        </FormField>

        <FormField label="Tipe Pekerjaan" htmlFor="job-type">
          <Select
            id="job-type"
            value={values.job_type}
            onChange={(e) => setValues({ ...values, job_type: e.target.value })}
            options={JOB_TYPES}
          />
        </FormField>
      </div>

      <Button type="submit" variant="primary" loading={loading} disabled={loading}>
        {loading ? 'Mencari...' : 'Mulai Cari Lowongan'}
      </Button>
    </form>
  );
};
