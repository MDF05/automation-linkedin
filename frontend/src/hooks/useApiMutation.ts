/**
 * useApiMutation
 * Generic fetch wrapper for POST / PUT / DELETE requests.
 * Exposes loading and error state so callers do not need to manage them manually.
 *
 * Requirements: 1.5, 2.10
 */

import { useState, useCallback, useRef } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

export type HttpMutationMethod = 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface MutationOptions<TData, TBody> {
  /** HTTP method. Defaults to "POST". */
  method?: HttpMutationMethod;
  /** Called after a successful response. */
  onSuccess?: (data: TData) => void;
  /** Called when an error is caught (network error or non-2xx response). */
  onError?: (error: ApiMutationError) => void;
  /** Extra headers merged on top of the default Content-Type / Accept headers. */
  headers?: Record<string, string>;
  /** Transform the response body before returning / calling onSuccess. */
  transform?: (raw: unknown) => TData;
  /** If true, the request body will be sent as FormData instead of JSON. */
  asFormData?: boolean;
  /** Abort any in-flight request when a new one is fired. Defaults to true. */
  abortPrevious?: boolean;
}

export interface ApiMutationError {
  /** HTTP status code (0 for network errors). */
  status: number;
  /** Human-readable message. */
  message: string;
  /** Raw parsed response body, if available. */
  body?: unknown;
}

export interface MutationState<TData> {
  /** True while the request is in-flight. */
  isLoading: boolean;
  /** Populated after a successful response. */
  data: TData | null;
  /** Populated after an error. */
  error: ApiMutationError | null;
}

export interface MutationActions<TData, TBody> {
  /** Fire the mutation. Returns the response data or throws ApiMutationError. */
  mutate: (url: string, body?: TBody) => Promise<TData>;
  /** Reset loading / data / error state. */
  reset: () => void;
}

// ─── Default base URL ─────────────────────────────────────────────────────────

function resolveUrl(path: string): string {
  const base =
    process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
  // Allow callers to pass either an absolute URL or a relative path
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${base}${path.startsWith('/') ? path : `/${path}`}`;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * @example
 * const { mutate, isLoading, error } = useApiMutation<BotRunResponse>({
 *   method: 'POST',
 *   onSuccess: (data) => console.log('Bot started', data.task_id),
 * });
 *
 * // Later:
 * await mutate('/api/v1/bot/run', { module: 'C', config: {} });
 */
export function useApiMutation<TData = unknown, TBody = unknown>(
  options: MutationOptions<TData, TBody> = {},
): MutationState<TData> & MutationActions<TData, TBody> {
  const {
    method = 'POST',
    onSuccess,
    onError,
    headers: extraHeaders = {},
    transform,
    asFormData = false,
    abortPrevious = true,
  } = options;

  const [state, setState] = useState<MutationState<TData>>({
    isLoading: false,
    data: null,
    error: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const mutate = useCallback(
    async (url: string, body?: TBody): Promise<TData> => {
      // Cancel previous request if requested
      if (abortPrevious && abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setState({ isLoading: true, data: null, error: null });

      const resolvedUrl = resolveUrl(url);

      // Build headers & body
      let fetchBody: BodyInit | undefined;
      const fetchHeaders: Record<string, string> = {
        Accept: 'application/json',
        ...extraHeaders,
      };

      if (body !== undefined) {
        if (asFormData && typeof body === 'object' && body !== null) {
          const fd = new FormData();
          for (const [k, v] of Object.entries(body as Record<string, unknown>)) {
            if (v instanceof File || v instanceof Blob) {
              fd.append(k, v);
            } else {
              fd.append(k, String(v));
            }
          }
          fetchBody = fd;
          // Let the browser set Content-Type with boundary for FormData
        } else {
          fetchBody = JSON.stringify(body);
          fetchHeaders['Content-Type'] = 'application/json';
        }
      }

      try {
        const response = await fetch(resolvedUrl, {
          method,
          headers: fetchHeaders,
          body: fetchBody,
          signal: controller.signal,
        });

        // Parse body (try JSON, fall back to text)
        let rawBody: unknown;
        const contentType = response.headers.get('content-type') ?? '';
        if (contentType.includes('application/json')) {
          rawBody = await response.json();
        } else {
          rawBody = await response.text();
        }

        if (!response.ok) {
          const mutationError: ApiMutationError = {
            status: response.status,
            message: extractErrorMessage(rawBody, response.status),
            body: rawBody,
          };
          setState({ isLoading: false, data: null, error: mutationError });
          onError?.(mutationError);
          throw mutationError;
        }

        const data = transform ? transform(rawBody) : (rawBody as TData);
        setState({ isLoading: false, data, error: null });
        onSuccess?.(data);
        return data;
      } catch (err) {
        if ((err as { name?: string }).name === 'AbortError') {
          // Request was cancelled; do not update state
          throw err;
        }

        // Re-throw ApiMutationError (already set in state above)
        if (isApiMutationError(err)) {
          throw err;
        }

        // Network / unexpected error
        const mutationError: ApiMutationError = {
          status: 0,
          message: err instanceof Error ? err.message : 'Network error',
        };
        setState({ isLoading: false, data: null, error: mutationError });
        onError?.(mutationError);
        throw mutationError;
      }
    },
    [method, onSuccess, onError, extraHeaders, transform, asFormData, abortPrevious],
  );

  const reset = useCallback(() => {
    abortControllerRef.current?.abort();
    setState({ isLoading: false, data: null, error: null });
  }, []);

  return {
    ...state,
    mutate,
    reset,
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function isApiMutationError(value: unknown): value is ApiMutationError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'status' in value &&
    'message' in value
  );
}

function extractErrorMessage(body: unknown, status: number): string {
  if (typeof body === 'string' && body.length > 0) return body;
  if (typeof body === 'object' && body !== null) {
    const b = body as Record<string, unknown>;
    // FastAPI / project error format: { error: { message } }
    if (typeof b['error'] === 'object' && b['error'] !== null) {
      const inner = b['error'] as Record<string, unknown>;
      if (typeof inner['message'] === 'string') return inner['message'];
    }
    // FastAPI validation error: { detail: [...] | string }
    if (typeof b['detail'] === 'string') return b['detail'];
    if (Array.isArray(b['detail'])) {
      return (b['detail'] as Array<{ msg?: string; message?: string }>)
        .map((d) => d.msg ?? d.message ?? JSON.stringify(d))
        .join('; ');
    }
    // Generic message field
    if (typeof b['message'] === 'string') return b['message'];
  }
  return `Request failed with status ${status}`;
}
