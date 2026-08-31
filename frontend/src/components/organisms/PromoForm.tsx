import React, { useState } from 'react';
import { Button, Input, Select } from '../atoms';
import { FormField } from '../molecules';

const PROMO_TYPES = [
  { value: 'penawaran_spesial', label: 'Penawaran Spesial' },
  { value: 'portofolio', label: 'Portofolio' },
  { value: 'testimoni', label: 'Testimoni' },
  { value: 'pengumuman', label: 'Pengumuman' },
];

export interface PromoFormValues {
  description: string;
  promo_type: string;
  items: string;
  target_audience: string;
}

export interface PromoFormProps {
  onSubmit: (values: PromoFormValues) => void;
  loading?: boolean;
}

export const PromoForm: React.FC<PromoFormProps> = ({ onSubmit, loading }) => {
  const [values, setValues] = useState<PromoFormValues>({
    description: '',
    promo_type: 'penawaran_spesial',
    items: '',
    target_audience: '',
  });
  const [errors, setErrors] = useState<Partial<PromoFormValues>>({});

  const validate = (): boolean => {
    const e: Partial<PromoFormValues> = {};
    if (!values.description.trim()) e.description = 'Deskripsi wajib diisi';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) onSubmit(values);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <FormField label="Deskripsi Jasa/Produk" htmlFor="promo-desc" required error={errors.description}>
        <Input
          id="promo-desc"
          value={values.description}
          onChange={(e) => setValues({ ...values, description: e.target.value })}
          placeholder="Contoh: Jasa desain logo profesional"
          error={errors.description}
        />
      </FormField>

      <FormField label="Tipe Promosi" htmlFor="promo-type">
        <Select
          id="promo-type"
          value={values.promo_type}
          onChange={(e) => setValues({ ...values, promo_type: e.target.value })}
          options={PROMO_TYPES}
        />
      </FormField>

      <FormField label="Item yang Dipromosikan" htmlFor="promo-items" hint="Pisahkan dengan koma">
        <Input
          id="promo-items"
          value={values.items}
          onChange={(e) => setValues({ ...values, items: e.target.value })}
          placeholder="Contoh: Logo, Banner, Brosur"
        />
      </FormField>

      <FormField label="Target Audiens" htmlFor="promo-audience">
        <Input
          id="promo-audience"
          value={values.target_audience}
          onChange={(e) => setValues({ ...values, target_audience: e.target.value })}
          placeholder="Contoh: Startup, UMKM, Freelancer"
        />
      </FormField>

      <Button type="submit" variant="primary" loading={loading} disabled={loading}>
        {loading ? 'Generating...' : 'Generate Promosi'}
      </Button>
    </form>
  );
};
