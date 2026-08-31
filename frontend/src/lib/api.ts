import type {
  // Settings
  SettingsResponse,
  SettingsPutPayload,
  // Device
  DeviceStatus,
  ScreenshotResponse,
  // Content / Posts
  GenerateContentRequest,
  GenerateContentResponse,
  CreatePostRequest,
  UpdatePostRequest,
  Post,
  PostListResponse,
  PublishPostResponse,
  GenerateImageRequest,
  GenerateImageResponse,
  // Engage
  StartEngageRequest,
  EngageSessionResponse,
  InteractionListResponse,
  // Jobs
  JobSearchRequest,
  JobSearchResponse,
  JobApplicationListResponse,
  JobReportResponse,
  JobStatsResponse,
  // Schedules
  Schedule,
  CreateScheduleRequest,
  UpdateScheduleRequest,
  ToggleScheduleResponse,
  // Logs
  BotLog,
  BotLogListResponse,
  // AI Usage
  AiUsageResponse,
  // Errors
  ValidationErrorResponse,
} from '@/types';

// NEXT_PUBLIC_API_URL is inlined by Next.js at build time; accessed via globalThis.process.env
const BASE_URL: string = (() => {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const env = (globalThis as any).process?.env as Record<string, string | undefined> | undefined;
    return env?.['NEXT_PUBLIC_API_URL'] ?? 'http://localhost:8000';
  } catch {
    return 'http://localhost:8000';
  }
})();

// ─── HTTP helpers ─────────────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body);
  }

  return res.json() as Promise<T>;
}

/**
 * Like `request`, but returns a raw Blob (for CSV/binary downloads).
 * Throws ApiError on non-2xx.
 */
async function requestBlob(
  path: string,
  options?: RequestInit,
): Promise<Blob> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { ...options?.headers },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body);
  }

  return res.blob();
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`HTTP ${status}`);
    this.name = 'ApiError';
  }

  /** Returns parsed 422 validation errors, or null for other error types. */
  getValidationErrors(): ValidationErrorResponse | null {
    if (this.status === 422) {
      const body = this.body as ValidationErrorResponse;
      if (body && Array.isArray(body.detail)) {
        return body;
      }
    }
    return null;
  }
}

// ─── Query param builder ──────────────────────────────────────────────────────

type QueryParams = Record<string, string | number | boolean | undefined | null>;

function buildQuery(params: QueryParams): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null,
  );
  if (entries.length === 0) return '';
  const qs = entries
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&');
  return `?${qs}`;
}

// ─── Settings API ─────────────────────────────────────────────────────────────

export async function getSettings(): Promise<SettingsResponse> {
  return request<SettingsResponse>('/api/settings');
}

export async function putSettings(payload: SettingsPutPayload): Promise<SettingsResponse> {
  return request<SettingsResponse>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

// ─── Device API ───────────────────────────────────────────────────────────────

export async function getDeviceStatus(): Promise<DeviceStatus> {
  return request<DeviceStatus>('/api/device/status');
}

export async function postDeviceScreenshot(): Promise<ScreenshotResponse> {
  return request<ScreenshotResponse>('/api/device/screenshot', {
    method: 'POST',
  });
}

// ─── Content / Posts API ──────────────────────────────────────────────────────

export async function generateContent(
  payload: GenerateContentRequest,
): Promise<GenerateContentResponse> {
  return request<GenerateContentResponse>('/api/content/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createPost(payload: CreatePostRequest): Promise<Post> {
  return request<Post>('/api/content/posts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export type GetPostsParams = QueryParams & {
  status?: string;
  content_type?: string;
  page?: number;
  page_size?: number;
};

export async function getPosts(params: GetPostsParams = {}): Promise<PostListResponse> {
  return request<PostListResponse>(`/api/content/posts${buildQuery(params)}`);
}

export async function getPost(id: number): Promise<Post> {
  return request<Post>(`/api/content/posts/${id}`);
}

export async function updatePost(id: number, payload: UpdatePostRequest): Promise<Post> {
  return request<Post>(`/api/content/posts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function publishPost(id: number): Promise<PublishPostResponse> {
  return request<PublishPostResponse>(`/api/content/posts/${id}/publish`, {
    method: 'POST',
  });
}

export async function generateImage(
  payload: GenerateImageRequest,
): Promise<GenerateImageResponse> {
  return request<GenerateImageResponse>('/api/content/image/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function exportPosts(): Promise<Blob> {
  return requestBlob('/api/content/posts/export');
}

// ─── Engage API ───────────────────────────────────────────────────────────────

export async function startEngage(
  payload: StartEngageRequest = {},
): Promise<EngageSessionResponse> {
  return request<EngageSessionResponse>('/api/engage/start', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function stopEngage(): Promise<EngageSessionResponse> {
  return request<EngageSessionResponse>('/api/engage/stop', {
    method: 'POST',
  });
}

export type GetInteractionsParams = QueryParams & {
  status?: string;
  action_type?: string;
  page?: number;
  page_size?: number;
};

export async function getInteractions(
  params: GetInteractionsParams = {},
): Promise<InteractionListResponse> {
  return request<InteractionListResponse>(`/api/engage/interactions${buildQuery(params)}`);
}

export async function exportInteractions(): Promise<Blob> {
  return requestBlob('/api/engage/interactions/export');
}

// ─── Jobs API ─────────────────────────────────────────────────────────────────

export async function searchJobs(payload: JobSearchRequest): Promise<JobSearchResponse> {
  return request<JobSearchResponse>('/api/jobs/search', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export type GetJobApplicationsParams = QueryParams & {
  status?: string;
  page?: number;
  page_size?: number;
};

export async function getJobApplications(
  params: GetJobApplicationsParams = {},
): Promise<JobApplicationListResponse> {
  return request<JobApplicationListResponse>(
    `/api/jobs/applications${buildQuery(params)}`,
  );
}

export async function getJobReport(sessionId: string): Promise<JobReportResponse> {
  return request<JobReportResponse>(`/api/jobs/report/${sessionId}`);
}

export async function getJobStats(): Promise<JobStatsResponse> {
  return request<JobStatsResponse>('/api/jobs/stats');
}

export async function exportJobApplications(): Promise<Blob> {
  return requestBlob('/api/jobs/applications/export');
}

// ─── Schedules API ────────────────────────────────────────────────────────────

export async function getSchedules(): Promise<Schedule[]> {
  return request<Schedule[]>('/api/schedules');
}

export async function createSchedule(payload: CreateScheduleRequest): Promise<Schedule> {
  return request<Schedule>('/api/schedules', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateSchedule(
  id: number,
  payload: UpdateScheduleRequest,
): Promise<Schedule> {
  return request<Schedule>(`/api/schedules/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteSchedule(id: number): Promise<void> {
  return request<void>(`/api/schedules/${id}`, { method: 'DELETE' });
}

export async function toggleSchedule(id: number): Promise<ToggleScheduleResponse> {
  return request<ToggleScheduleResponse>(`/api/schedules/${id}/toggle`, {
    method: 'POST',
  });
}

// ─── Logs API ─────────────────────────────────────────────────────────────────

export type GetLogsParams = QueryParams & {
  status?: string;
  action?: string;
  module?: 'A' | 'B' | 'C' | 'D';
  date_from?: string; // ISO date
  date_to?: string;   // ISO date
  page?: number;
  page_size?: number;
};

export async function getLogs(params: GetLogsParams = {}): Promise<BotLogListResponse> {
  return request<BotLogListResponse>(`/api/logs${buildQuery(params)}`);
}

export async function getLog(id: number): Promise<BotLog> {
  return request<BotLog>(`/api/logs/${id}`);
}

export async function exportLogs(): Promise<Blob> {
  return requestBlob('/api/logs/export');
}

// ─── AI Usage API ─────────────────────────────────────────────────────────────

export type GetAiUsageParams = QueryParams & {
  period_days?: number;
};

export async function getAiUsage(
  params: GetAiUsageParams = {},
): Promise<AiUsageResponse> {
  return request<AiUsageResponse>(`/api/ai/usage${buildQuery(params)}`);
}
