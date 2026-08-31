// ─── Settings Types ───────────────────────────────────────────────────────────

export type AIProvider = 'deepseek' | 'groq' | 'chatgpt_web' | 'claude_web' | 'perplexity_web';

export interface AIUsageLimits {
  deepseek: number;
  groq: number;
  chatgpt_web: number;
  claude_web: number;
  perplexity_web: number;
}

export interface AntiBanLimits {
  posts_per_day: number;
  comments_per_day: number;
  applies_per_day: number;
}

export interface AntiBanDelays {
  tap_min_ms: number;
  tap_max_ms: number;
  nav_min_ms: number;
  nav_max_ms: number;
}

export interface SettingEntry<T = unknown> {
  key: string;
  value: T;
  description: string | null;
  updated_at: string; // ISO datetime
}

export interface SettingsResponse {
  ai_provider_chain: SettingEntry<AIProvider[]>;
  ai_usage_limits: SettingEntry<AIUsageLimits>;
  anti_ban_limits: SettingEntry<AntiBanLimits>;
  anti_ban_delays: SettingEntry<AntiBanDelays>;
  content_language: SettingEntry<string>;
  cv_path: SettingEntry<string | null>;
  screenshot_enabled: SettingEntry<boolean>;
}

export interface SettingsPutPayload {
  ai_provider_chain?: AIProvider[];
  ai_usage_limits?: Partial<AIUsageLimits>;
  anti_ban_limits?: Partial<AntiBanLimits>;
  anti_ban_delays?: Partial<AntiBanDelays>;
  content_language?: string;
  cv_path?: string | null;
  screenshot_enabled?: boolean;
}

// ─── Validation Error (422) ───────────────────────────────────────────────────

export interface ValidationErrorDetail {
  field: string;
  message: string;
  given?: unknown;
}

export interface ValidationErrorResponse {
  detail: ValidationErrorDetail[];
}

// ─── Generic API Error ────────────────────────────────────────────────────────

export interface ApiErrorResponse {
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  detail?: ValidationErrorDetail[] | string;
}

// ─── Device ──────────────────────────────────────────────────────────────────

export type DeviceConnectionStatus = 'connected' | 'disconnected' | 'unauthorized' | 'offline';

export interface DeviceStatus {
  connected: boolean;
  device_id: string | null;
  model: string | null;
  android_version: string | null;
  battery_level: number | null;
  linkedin_installed: boolean;
  status: DeviceConnectionStatus;
}

export interface ScreenshotResponse {
  path: string;
  url: string;
  captured_at: string; // ISO datetime
}

// ─── Content / Posts ─────────────────────────────────────────────────────────

export type PostStatus = 'draft' | 'scheduled' | 'posted' | 'failed';
export type ContentType =
  | 'storytelling'
  | 'tips_list'
  | 'pertanyaan'
  | 'kutipan'
  | 'video_script'
  | 'thread'
  | 'promo'
  | 'promo_portofolio'
  | 'promo_testimoni';
export type ContentTone = 'professional' | 'casual' | 'inspirational' | 'educational' | 'humorous';

export interface Post {
  id: number;
  title: string | null;
  content: string;
  content_type: ContentType;
  tone: string | null;
  status: PostStatus;
  image_url: string | null;
  is_thread: boolean;
  thread_parts: string[] | null;
  thread_count: number;
  scheduled_at: string | null; // ISO datetime
  posted_at: string | null;   // ISO datetime
  likes: number;
  comments: number;
  shares: number;
  ai_provider_used: string | null;
  prompt_used: string | null;
  search_references: unknown | null;
  linkedin_post_id: string | null;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

export interface GenerateContentRequest {
  content_type: ContentType;
  tone?: ContentTone;
  topic?: string;
  keywords?: string[];
  language?: string;
  include_image?: boolean;
}

export interface GenerateContentResponse {
  variants: Post[];
  provider_used: string;
  tokens_used: number;
}

export interface CreatePostRequest {
  content: string;
  content_type: ContentType;
  tone?: string;
  title?: string;
  image_url?: string;
  is_thread?: boolean;
  thread_parts?: string[];
  scheduled_at?: string;
}

export interface UpdatePostRequest {
  content?: string;
  tone?: string;
  title?: string;
  image_url?: string;
  status?: PostStatus;
  scheduled_at?: string | null;
}

export interface PublishPostResponse {
  success: boolean;
  linkedin_post_id: string | null;
  posted_at: string | null;
  message: string;
}

export interface GenerateImageRequest {
  prompt: string;
  style?: string;
  width?: number;
  height?: number;
}

export interface GenerateImageResponse {
  image_url: string;
  provider_used: string;
  prompt_used: string;
}

export interface PostListResponse {
  items: Post[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Engage / Interactions ────────────────────────────────────────────────────

export type InteractionActionType = 'comment' | 'react' | 'share' | 'connect';
export type InteractionStatus = 'success' | 'failed' | 'skipped';

export interface Interaction {
  id: number;
  target_post_url: string;
  target_author: string | null;
  target_post_text: string | null;
  action_type: InteractionActionType;
  content_sent: string | null;
  status: InteractionStatus;
  skip_reason: string | null;
  ai_provider_used: string | null;
  screenshot_path: string | null;
  created_at: string; // ISO datetime
}

export interface StartEngageRequest {
  topic_filters?: string[];
  max_interactions?: number;
  action_types?: InteractionActionType[];
}

export interface EngageSessionResponse {
  session_id: string;
  status: 'started' | 'running' | 'stopped';
  message: string;
}

export interface InteractionListResponse {
  items: Interaction[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Jobs / Job Hunter ────────────────────────────────────────────────────────

export type JobStatus =
  | 'found'
  | 'applied'
  | 'skipped'
  | 'rejected'
  | 'interview'
  | 'offer'
  | 'skipped_incomplete_form'
  | 'skipped_no_easy_apply';

export interface JobApplication {
  id: number;
  job_title: string;
  company: string;
  location: string | null;
  salary_range: string | null;
  job_url: string;
  status: JobStatus;
  has_easy_apply: boolean;
  job_type: string | null;
  applied_at: string | null; // ISO datetime
  notes: string | null;
  form_fields_filled: unknown | null;
  search_session_id: string | null;
  screenshot_path: string | null;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

export interface JobSearchRequest {
  keywords: string[];
  location?: string;
  job_type?: string;
  easy_apply_only?: boolean;
  max_applications?: number;
}

export interface JobSearchResponse {
  session_id: string;
  status: 'started' | 'running';
  message: string;
}

export interface JobApplicationListResponse {
  items: JobApplication[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobReportResponse {
  session_id: string;
  total_found: number;
  total_applied: number;
  total_skipped: number;
  total_failed: number;
  duration_seconds: number | null;
  applications: JobApplication[];
}

export interface JobStatsResponse {
  total: number;
  by_status: Record<JobStatus, number>;
  this_week: number;
  today: number;
}

// ─── Schedules ────────────────────────────────────────────────────────────────

export type ScheduleTaskType = 'post_konten' | 'engage' | 'job_hunt' | 'promosi';

export interface Schedule {
  id: number;
  name: string;
  task_type: ScheduleTaskType;
  cron_expression: string | null;
  scheduled_once_at: string | null; // ISO datetime
  is_active: boolean;
  last_run: string | null;   // ISO datetime
  last_status: string | null;
  next_run: string | null;   // ISO datetime
  retry_count: number;
  max_retries: number;
  config_json: Record<string, unknown>;
  run_count: number;
  failure_count: number;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

export interface CreateScheduleRequest {
  name: string;
  task_type: ScheduleTaskType;
  cron_expression?: string;
  scheduled_once_at?: string;
  config_json?: Record<string, unknown>;
  max_retries?: number;
}

export interface UpdateScheduleRequest {
  name?: string;
  cron_expression?: string | null;
  scheduled_once_at?: string | null;
  config_json?: Record<string, unknown>;
  max_retries?: number;
}

export interface ToggleScheduleResponse {
  id: number;
  is_active: boolean;
  next_run: string | null;
}

// ─── Bot Logs ─────────────────────────────────────────────────────────────────

export type BotLogAction =
  | 'generate_content' | 'search_reference' | 'generate_image'
  | 'open_linkedin' | 'navigate_post' | 'type_content' | 'upload_image'
  | 'publish_post' | 'screenshot' | 'scroll_feed' | 'read_ocr'
  | 'generate_comment' | 'post_comment' | 'open_jobs' | 'search_jobs'
  | 'extract_jobs' | 'easy_apply' | 'fill_form' | 'open_ai_web'
  | 'paste_prompt' | 'copy_response' | 'detect_captcha'
  | 'idle_wait' | 'anti_ban_delay';

export type BotLogStatus = 'success' | 'failed' | 'running' | 'skipped' | 'timeout';

export interface BotLog {
  id: number;
  post_id: number | null;
  task_id: string;
  action: BotLogAction;
  status: BotLogStatus;
  message: string | null;
  error_detail: string | null;
  stack_trace: string | null;
  screenshot_path: string | null;
  duration_ms: number | null;
  module: 'A' | 'B' | 'C' | 'D' | null;
  metadata: Record<string, unknown> | null;
  created_at: string; // ISO datetime
}

export interface BotLogListResponse {
  items: BotLog[];
  total: number;
  page: number;
  page_size: number;
}

// ─── AI Usage ─────────────────────────────────────────────────────────────────

export interface AiUsageEntry {
  id: number;
  provider: AIProvider;
  prompt_tokens: number;
  completion_tokens: number;
  cost_estimate: number;
  module: 'A' | 'B' | 'C' | 'D' | null;
  task_id: string | null;
  success: boolean;
  error_message: string | null;
  latency_ms: number | null;
  created_at: string; // ISO datetime
}

export interface AiUsageProviderSummary {
  provider: AIProvider;
  total_calls: number;
  successful_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost_estimate: number;
}

export interface AiUsageResponse {
  period_days: number;
  total_cost: number;
  total_calls: number;
  by_provider: AiUsageProviderSummary[];
}
