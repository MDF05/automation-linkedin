import React, { useState } from 'react';
import { Button, Input, Select, Spinner } from '../atoms';
import { FormField } from '../molecules';

const CONTENT_TYPES = [
  { value: 'storytelling', label: 'Storytelling' },
  { value: 'tips_list', label: 'Tips List' },
  { value: 'pertanyaan', label: 'Pertanyaan' },
  { value: 'kutipan', label: 'Kutipan' },
  { value: 'video_script', label: 'Video Script' },
  { value: 'thread', label: 'Thread' },
];

const TONES = [
  { value: 'profesional', label: 'Profesional' },
  { value: 'kasual', label: 'Kasual' },
  { value: 'inspiratif', label: 'Inspiratif' },
  { value: 'edukasi', label: 'Edukasi' },
];

const LENGTHS = [
  { value: 'pendek', label: 'Pendek (~300 karakter)' },
  { value: 'sedang', label: 'Sedang (~1000 karakter)' },
  { value: 'panjang', label: 'Panjang (~2500 karakter)' },
];

export interface ContentFormValues {
  topic: string;
  description: string;
  content_type: string;
  tone: string;
  length: string;
  generate_image: boolean;
}

export interface ContentFormProps {
  onSubmit: (values: ContentFormValues) => void;
  loading?: boolean;
}

export const ContentForm: React.FC<ContentFormProps> = ({ onSubmit, loading }) => {
  const [values, setValues] = useState<ContentFormValues>({
    topic: '',
    description: '',
    content_type: 'storytelling',
    tone: 'profesional',
    length: 'sedang',
    generate_image: false,
  });
  const [errors, setErrors] = useState<Partial<ContentFormValues>>({});

  const validate = (): boolean => {
    const newErrors: Partial<ContentFormValues> = {};
    if (!values.topic.trim()) newErrors.topic = 'Topik wajib diisi';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) onSubmit(values);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <FormField label="Topik / Judul" htmlFor="topic" required error={errors.topic}>
        <Input
          id="topic"
          value={values.topic}
          onChange={(e) => setValues({ ...values, topic: e.target.value })}
          placeholder="Contoh: Produktivitas Remote Work"
          error={errors.topic}
        />
      </FormField>

      <FormField label="Deskripsi Ide" htmlFor="description">
        <Input
          id="description"
          value={values.description}
          onChange={(e) => setValues({ ...values, description: e.target.value })}
          placeholder="Opsional: detail tambahan untuk AI"
        />
      </FormField>

      <div className="grid grid-cols-3 gap-3">
        <FormField label="Tipe Konten" htmlFor="content_type">
          <Select
            id="content_type"
            value={values.content_type}
            onChange={(e) => setValues({ ...values, content_type: e.target.value })}
            options={CONTENT_TYPES}
          />
        </FormField>

        <FormField label="Tone" htmlFor="tone">
          <Select
            id="tone"
            value={values.tone}
            onChange={(e) => setValues({ ...values, tone: e.target.value })}
            options={TONES}
          />
        </FormField>

        <FormField label="Panjang" htmlFor="length">
          <Select
            id="length"
            value={values.length}
            onChange={(e) => setValues({ ...values, length: e.target.value })}
            options={LENGTHS}
          />
        </FormField>
      </div>

      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
        <input
          type="checkbox"
          checked={values.generate_image}
          onChange={(e) => setValues({ ...values, generate_image: e.target.checked })}
          className="rounded border-gray-300"
        />
        Generate gambar (Ideogram)
      </label>

      <Button type="submit" variant="primary" loading={loading} disabled={loading}>
        {loading ? 'Generating...' : 'Generate Konten'}
      </Button>
    </form>
  );
};
