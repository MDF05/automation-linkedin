/**
 * Settings page — halaman konfigurasi sistem.
 * Requirements: 12.1–12.5
 *
 * - Form konfigurasi: provider AI, batas harian, delay range, path CV (Req 12.1)
 * - Validasi sisi client sebelum submit (Req 12.3)
 * - Tampilkan field error dari 422 response (Req 12.3)
 * - Tampilkan updated_at timestamp per setting (Req 12.5)
 */

import React, { useCallback, useEffect, useState } from 'react';
import { format, parseISO } from 'date-fns';
import { AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';

import { DashboardLayout } from '@/components/templates';
import { Button, Input, Select, Spinner } from '@/components/atoms';
import { FormField } from '@/components/molecules';
import { getSettings, putSettings, ApiError } from '@/lib/api';
import type {
  AIProvider,
  AntiBanDelays,
  AntiBanLimits,
  SettingsResponse,
} from '@/types';

// ─── Constants ────────────────────────────────────────────────────────────────

const AI_PROVIDER_OPTIONS: { value: AIProvider; label: string }[] = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'groq', label: 'Groq' },
  { value: 'chatgpt_web', label: 'ChatGPT Web' },
  { value: 'claude_web', label: 'Claude Web' },
  { value: 'perplexity_web', label: 'Perplexity Web' },
];

const LANGUAGE_OPTIONS = [
  { value: 'indonesia', label: 'Bahasa Indonesia' },
  { value: 'english', label: 'English' },
];

// ─── Form state shape ─────────────────────────────────────────────────────────

interface SettingsFormValues {
  // ai_provider_chain: ordered list; shown as ordered text input
  ai_provider_chain_raw: string; // comma-separated order, e.g. "deepseek,groq"
  // ai_usage_limits
  limit_deepseek: string;
  limit_groq: string;
  limit_chatgpt_web: string;
  limit_claude_web: string;
  limit_perplexity_web: string;
  // anti_ban_limits
  posts_per_day: string;
  comments_per_day: string;
  applies_per_day: string;
  // anti_ban_delays
  tap_min_ms: string;
  tap_max_ms: string;
  nav_min_ms: string;
  nav_max_ms: string;
  // other
  content_language: string;
  cv_path: string;
  screenshot_enabled: string; // "true" | "false"
}

type FieldErrors = Partial<Record<keyof SettingsFormValues | string, string>>;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTimestamp(iso: string): string {
  try {
    return format(parseISO(iso), 'dd MMM yyyy, HH:mm');
  } catch {
    return iso;
  }
}

function settingsToForm(data: SettingsResponse): SettingsFormValues {
  const chain = data.ai_provider_chain?.value ?? [];
  const limits = data.ai_usage_limits?.value ?? {};
  const banLimits = data.anti_ban_limits?.value ?? ({} as AntiBanLimits);
  const banDelays = data.anti_ban_delays?.value ?? ({} as AntiBanDelays);

  return {
    ai_provider_chain_raw: chain.join(', '),
    limit_deepseek: String(limits.deepseek ?? 500000),
    limit_groq: String(limits.groq ?? 30000),
    limit_chatgpt_web: String(limits.chatgpt_web ?? 100),
    limit_claude_web: String(limits.claude_web ?? 50),
    limit_perplexity_web: String(limits.perplexity_web ?? 50),
    posts_per_day: String(banLimits.posts_per_day ?? 3),
    comments_per_day: String(banLimits.comments_per_day ?? 15),
    applies_per_day: String(banLimits.applies_per_day ?? 20),
    tap_min_ms: String(banDelays.tap_min_ms ?? 1000),
    tap_max_ms: String(banDelays.tap_max_ms ?? 3000),
    nav_min_ms: String(banDelays.nav_min_ms ?? 2000),
    nav_max_ms: String(banDelays.nav_max_ms ?? 5000),
    content_language: data.content_language?.value ?? 'indonesia',
    cv_path: data.cv_path?.value ?? '',
    screenshot_enabled: String(data.screenshot_enabled?.value ?? true),
  };
}

// ─── Client-side validation ───────────────────────────────────────────────────

function validateForm(values: SettingsFormValues): FieldErrors {
  const errors: FieldErrors = {};

  // ai_provider_chain
  const chain = values.ai_provider_chain_raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  if (chain.length === 0) {
    errors.ai_provider_chain_raw = 'Urutan provider tidak boleh kosong';
  } else {
    const validProviders = AI_PROVIDER_OPTIONS.map((p) => p.value);
    const invalid = chain.filter((p) => !validProviders.includes(p as AIProvider));
    if (invalid.length > 0) {
      errors.ai_provider_chain_raw = `Provider tidak dikenal: ${invalid.join(', ')}`;
    }
  }

  // usage limits — must be positive integers
  const limitFields: Array<[keyof SettingsFormValues, string]> = [
    ['limit_deepseek', 'Batas token DeepSeek'],
    ['limit_groq', 'Batas token Groq'],
    ['limit_chatgpt_web', 'Batas ChatGPT Web'],
    ['limit_claude_web', 'Batas Claude Web'],
    ['limit_perplexity_web', 'Batas Perplexity Web'],
  ];
  for (const [field, label] of limitFields) {
    const val = parseInt(values[field], 10);
    if (isNaN(val) || val <= 0) {
      errors[field] = `${label} harus bilangan positif`;
    }
  }

  // anti_ban_limits
  const dailyFields: Array<[keyof SettingsFormValues, string]> = [
    ['posts_per_day', 'Batas post/hari'],
    ['comments_per_day', 'Batas komentar/hari'],
    ['applies_per_day', 'Batas lamaran/hari'],
  ];
  for (const [field, label] of dailyFields) {
    const val = parseInt(values[field], 10);
    if (isNaN(val) || val <= 0) {
      errors[field] = `${label} harus bilangan positif`;
    }
  }

  // anti_ban_delays — min < max
  const tapMin = parseInt(values.tap_min_ms, 10);
  const tapMax = parseInt(values.tap_max_ms, 10);
  if (isNaN(tapMin) || tapMin <= 0) {
    errors.tap_min_ms = 'Tap min delay harus bilangan positif';
  }
  if (isNaN(tapMax) || tapMax <= 0) {
    errors.tap_max_ms = 'Tap max delay harus bilangan positif';
  }
  if (!errors.tap_min_ms && !errors.tap_max_ms && tapMin >= tapMax) {
    errors.tap_min_ms = 'Tap min delay harus lebih kecil dari tap max delay';
  }

  const navMin = parseInt(values.nav_min_ms, 10);
  const navMax = parseInt(values.nav_max_ms, 10);
  if (isNaN(navMin) || navMin <= 0) {
    errors.nav_min_ms = 'Nav min delay harus bilangan positif';
  }
  if (isNaN(navMax) || navMax <= 0) {
    errors.nav_max_ms = 'Nav max delay harus bilangan positif';
  }
  if (!errors.nav_min_ms && !errors.nav_max_ms && navMin >= navMax) {
    errors.nav_min_ms = 'Nav min delay harus lebih kecil dari nav max delay';
  }

  return errors;
}

// Map 422 backend field paths to form field keys
function mapBackendField(backendField: string): string {
  const fieldMap: Record<string, string> = {
    'anti_ban_delays.tap_min_ms': 'tap_min_ms',
    'anti_ban_delays.tap_max_ms': 'tap_max_ms',
    'anti_ban_delays.nav_min_ms': 'nav_min_ms',
    'anti_ban_delays.nav_max_ms': 'nav_max_ms',
    'anti_ban_limits.posts_per_day': 'posts_per_day',
    'anti_ban_limits.comments_per_day': 'comments_per_day',
    'anti_ban_limits.applies_per_day': 'applies_per_day',
    'ai_usage_limits.deepseek': 'limit_deepseek',
    'ai_usage_limits.groq': 'limit_groq',
    'ai_usage_limits.chatgpt_web': 'limit_chatgpt_web',
    'ai_usage_limits.claude_web': 'limit_claude_web',
    'ai_usage_limits.perplexity_web': 'limit_perplexity_web',
    ai_provider_chain: 'ai_provider_chain_raw',
  };
  return fieldMap[backendField] ?? backendField;
}

// ─── Sub-sections ─────────────────────────────────────────────────────────────

interface SectionProps {
  title: string;
  updatedAt?: string | null;
  children: React.ReactNode;
}

const Section: React.FC<SectionProps> = ({ title, updatedAt, children }) => (
  <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
    <div className="mb-4 flex items-start justify-between gap-2">
      <h2 className="text-sm font-semibold text-gray-800">{title}</h2>
      {updatedAt && (
        <span className="shrink-0 text-xs text-gray-400">
          Diubah: {formatTimestamp(updatedAt)}
        </span>
      )}
    </div>
    <div className="space-y-4">{children}</div>
  </section>
);

// ─── Settings Page ────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [values, setValues] = useState<SettingsFormValues | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // ── Load settings ──────────────────────────────────────────────────────────
  const loadSettings = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const data = await getSettings();
      setSettings(data);
      setValues(settingsToForm(data));
    } catch {
      setFetchError('Gagal memuat konfigurasi. Pastikan backend berjalan.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  // ── Field change helper ────────────────────────────────────────────────────
  const handleChange = useCallback(
    (field: keyof SettingsFormValues) =>
      (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        setValues((prev) => prev && { ...prev, [field]: e.target.value });
        // Clear field error on change
        setFieldErrors((prev) => {
          const next = { ...prev };
          delete next[field];
          return next;
        });
        setSuccessMsg(null);
      },
    [],
  );

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!values) return;

    // Client-side validation
    const errors = validateForm(values);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setSaving(true);
    setFieldErrors({});
    setSuccessMsg(null);

    try {
      const chain = values.ai_provider_chain_raw
        .split(',')
        .map((s) => s.trim().toLowerCase() as AIProvider)
        .filter(Boolean);

      const payload = {
        ai_provider_chain: chain,
        ai_usage_limits: {
          deepseek: parseInt(values.limit_deepseek, 10),
          groq: parseInt(values.limit_groq, 10),
          chatgpt_web: parseInt(values.limit_chatgpt_web, 10),
          claude_web: parseInt(values.limit_claude_web, 10),
          perplexity_web: parseInt(values.limit_perplexity_web, 10),
        },
        anti_ban_limits: {
          posts_per_day: parseInt(values.posts_per_day, 10),
          comments_per_day: parseInt(values.comments_per_day, 10),
          applies_per_day: parseInt(values.applies_per_day, 10),
        },
        anti_ban_delays: {
          tap_min_ms: parseInt(values.tap_min_ms, 10),
          tap_max_ms: parseInt(values.tap_max_ms, 10),
          nav_min_ms: parseInt(values.nav_min_ms, 10),
          nav_max_ms: parseInt(values.nav_max_ms, 10),
        },
        content_language: values.content_language,
        cv_path: values.cv_path || null,
        screenshot_enabled: values.screenshot_enabled === 'true',
      };

      const updated = await putSettings(payload);
      setSettings(updated);
      setValues(settingsToForm(updated));
      setSuccessMsg('Konfigurasi berhasil disimpan.');
    } catch (err) {
      if (err instanceof ApiError) {
        const validationErrors = err.getValidationErrors();
        if (validationErrors) {
          // Map backend 422 errors to form fields
          const mapped: FieldErrors = {};
          for (const detail of validationErrors.detail) {
            const formField = mapBackendField(detail.field);
            mapped[formField] = detail.message;
          }
          setFieldErrors(mapped);
        } else {
          setFetchError('Gagal menyimpan konfigurasi. Silakan coba lagi.');
        }
      } else {
        setFetchError('Terjadi kesalahan. Silakan coba lagi.');
      }
    } finally {
      setSaving(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <DashboardLayout title="Settings">
        <div className="flex h-64 items-center justify-center">
          <Spinner size="lg" />
        </div>
      </DashboardLayout>
    );
  }

  if (fetchError && !values) {
    return (
      <DashboardLayout title="Settings">
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <AlertCircle className="h-10 w-10 text-red-400" />
          <p className="text-sm text-gray-600">{fetchError}</p>
          <Button variant="secondary" onClick={loadSettings}>
            <RefreshCw size={14} /> Coba lagi
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  if (!values || !settings) return null;

  return (
    <DashboardLayout title="Settings">
      <form onSubmit={handleSubmit} noValidate aria-label="Formulir konfigurasi sistem">
        <div className="mx-auto max-w-2xl space-y-6">
          {/* Global feedback banners */}
          {fetchError && (
            <div role="alert" className="flex items-center gap-2 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700 border border-red-200">
              <AlertCircle size={16} className="shrink-0" />
              {fetchError}
            </div>
          )}
          {successMsg && (
            <div role="status" className="flex items-center gap-2 rounded-md bg-green-50 px-4 py-3 text-sm text-green-700 border border-green-200">
              <CheckCircle2 size={16} className="shrink-0" />
              {successMsg}
            </div>
          )}

          {/* ── AI Provider Chain ── */}
          <Section
            title="Provider AI"
            updatedAt={settings.ai_provider_chain?.updated_at}
          >
            <FormField
              label="Urutan Provider (pisahkan dengan koma)"
              htmlFor="ai_provider_chain"
              error={fieldErrors.ai_provider_chain_raw}
              hint={`Contoh: deepseek, groq, chatgpt_web — opsi valid: ${AI_PROVIDER_OPTIONS.map((p) => p.value).join(', ')}`}
              required
            >
              <Input
                id="ai_provider_chain"
                value={values.ai_provider_chain_raw}
                onChange={handleChange('ai_provider_chain_raw')}
                placeholder="deepseek, groq, chatgpt_web"
                error={fieldErrors.ai_provider_chain_raw}
              />
            </FormField>

            <div className="grid grid-cols-2 gap-3">
              {(
                [
                  ['limit_deepseek', 'Batas token DeepSeek'],
                  ['limit_groq', 'Batas token Groq'],
                  ['limit_chatgpt_web', 'Batas request ChatGPT Web'],
                  ['limit_claude_web', 'Batas request Claude Web'],
                  ['limit_perplexity_web', 'Batas request Perplexity Web'],
                ] as Array<[keyof SettingsFormValues, string]>
              ).map(([field, label]) => (
                <FormField
                  key={field}
                  label={label}
                  htmlFor={field}
                  error={fieldErrors[field]}
                  required
                >
                  <Input
                    id={field}
                    type="number"
                    min="1"
                    value={values[field]}
                    onChange={handleChange(field)}
                    error={fieldErrors[field]}
                  />
                </FormField>
              ))}
            </div>
            {settings.ai_usage_limits?.updated_at && (
              <p className="text-right text-xs text-gray-400">
                Batas penggunaan diubah: {formatTimestamp(settings.ai_usage_limits.updated_at)}
              </p>
            )}
          </Section>

          {/* ── Anti-Ban Limits ── */}
          <Section
            title="Batas Harian (Anti-Ban)"
            updatedAt={settings.anti_ban_limits?.updated_at}
          >
            <div className="grid grid-cols-3 gap-3">
              <FormField
                label="Post/hari"
                htmlFor="posts_per_day"
                error={fieldErrors.posts_per_day}
                required
              >
                <Input
                  id="posts_per_day"
                  type="number"
                  min="1"
                  value={values.posts_per_day}
                  onChange={handleChange('posts_per_day')}
                  error={fieldErrors.posts_per_day}
                />
              </FormField>
              <FormField
                label="Komentar/hari"
                htmlFor="comments_per_day"
                error={fieldErrors.comments_per_day}
                required
              >
                <Input
                  id="comments_per_day"
                  type="number"
                  min="1"
                  value={values.comments_per_day}
                  onChange={handleChange('comments_per_day')}
                  error={fieldErrors.comments_per_day}
                />
              </FormField>
              <FormField
                label="Lamaran/hari"
                htmlFor="applies_per_day"
                error={fieldErrors.applies_per_day}
                required
              >
                <Input
                  id="applies_per_day"
                  type="number"
                  min="1"
                  value={values.applies_per_day}
                  onChange={handleChange('applies_per_day')}
                  error={fieldErrors.applies_per_day}
                />
              </FormField>
            </div>
          </Section>

          {/* ── Anti-Ban Delays ── */}
          <Section
            title="Range Delay ADB (Anti-Ban)"
            updatedAt={settings.anti_ban_delays?.updated_at}
          >
            <div className="grid grid-cols-2 gap-3">
              <FormField
                label="Tap min (ms)"
                htmlFor="tap_min_ms"
                error={fieldErrors.tap_min_ms}
                required
              >
                <Input
                  id="tap_min_ms"
                  type="number"
                  min="100"
                  value={values.tap_min_ms}
                  onChange={handleChange('tap_min_ms')}
                  error={fieldErrors.tap_min_ms}
                />
              </FormField>
              <FormField
                label="Tap max (ms)"
                htmlFor="tap_max_ms"
                error={fieldErrors.tap_max_ms}
                required
              >
                <Input
                  id="tap_max_ms"
                  type="number"
                  min="100"
                  value={values.tap_max_ms}
                  onChange={handleChange('tap_max_ms')}
                  error={fieldErrors.tap_max_ms}
                />
              </FormField>
              <FormField
                label="Navigasi min (ms)"
                htmlFor="nav_min_ms"
                error={fieldErrors.nav_min_ms}
                required
              >
                <Input
                  id="nav_min_ms"
                  type="number"
                  min="100"
                  value={values.nav_min_ms}
                  onChange={handleChange('nav_min_ms')}
                  error={fieldErrors.nav_min_ms}
                />
              </FormField>
              <FormField
                label="Navigasi max (ms)"
                htmlFor="nav_max_ms"
                error={fieldErrors.nav_max_ms}
                required
              >
                <Input
                  id="nav_max_ms"
                  type="number"
                  min="100"
                  value={values.nav_max_ms}
                  onChange={handleChange('nav_max_ms')}
                  error={fieldErrors.nav_max_ms}
                />
              </FormField>
            </div>
          </Section>

          {/* ── Path CV & Language & Screenshot ── */}
          <Section
            title="Preferensi Umum"
            updatedAt={settings.cv_path?.updated_at ?? settings.content_language?.updated_at}
          >
            <FormField
              label="Path CV (untuk auto apply)"
              htmlFor="cv_path"
              error={fieldErrors.cv_path}
              hint="Path absolut ke file CV (.pdf atau .docx), maks 5 MB"
            >
              <Input
                id="cv_path"
                type="text"
                value={values.cv_path}
                onChange={handleChange('cv_path')}
                placeholder="/home/user/cv.pdf"
                error={fieldErrors.cv_path}
              />
            </FormField>

            <FormField
              label="Bahasa konten default"
              htmlFor="content_language"
              error={fieldErrors.content_language}
              required
            >
              <Select
                id="content_language"
                options={LANGUAGE_OPTIONS}
                value={values.content_language}
                onChange={handleChange('content_language')}
                error={fieldErrors.content_language}
              />
            </FormField>

            <FormField
              label="Screenshot setiap aksi bot"
              htmlFor="screenshot_enabled"
              error={fieldErrors.screenshot_enabled}
            >
              <Select
                id="screenshot_enabled"
                options={[
                  { value: 'true', label: 'Aktif' },
                  { value: 'false', label: 'Nonaktif' },
                ]}
                value={values.screenshot_enabled}
                onChange={handleChange('screenshot_enabled')}
                error={fieldErrors.screenshot_enabled}
              />
            </FormField>

            {settings.screenshot_enabled?.updated_at && (
              <p className="text-right text-xs text-gray-400">
                Screenshot setting diubah:{' '}
                {formatTimestamp(settings.screenshot_enabled.updated_at)}
              </p>
            )}
          </Section>

          {/* ── Submit ── */}
          <div className="flex justify-end gap-3 pb-8">
            <Button
              type="button"
              variant="secondary"
              onClick={loadSettings}
              disabled={saving}
            >
              <RefreshCw size={14} /> Reset
            </Button>
            <Button type="submit" variant="primary" loading={saving}>
              Simpan Konfigurasi
            </Button>
          </div>
        </div>
      </form>
    </DashboardLayout>
  );
}
