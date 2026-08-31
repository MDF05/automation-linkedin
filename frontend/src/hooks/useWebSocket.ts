/**
 * useWebSocket
 * Manages a persistent WebSocket connection to the backend (/ws endpoint).
 * Handles automatic reconnection with exponential back-off and exposes
 * an event stream that other hooks can subscribe to.
 *
 * Requirements: 1.5, 2.10
 */

import { useEffect, useRef, useCallback } from 'react';
import { useBotStore } from '../stores/botStore';
import { useDeviceStore } from '../stores/deviceStore';
import { useNotifStore } from '../stores/notifStore';
import type { BotStep } from '../stores/botStore';

// ─── WebSocket event shapes ───────────────────────────────────────────────────

interface DeviceStatusPayload {
  connected: boolean;
  device_id: string | null;
  model: string | null;
  android_version: string | null;
  battery_level: number | null;
  linkedin_installed: boolean;
  status?: 'connected' | 'disconnected' | 'unauthorized' | 'offline';
}

interface BotStartedPayload {
  module: 'A' | 'B' | 'C' | 'D';
  task_id: string;
  started_at: string;
}

interface BotStepPayload extends BotStep {
  task_id: string;
}

interface BotCompletedPayload {
  task_id: string;
  module: string;
  duration_ms: number;
  result_summary: string;
}

interface BotErrorPayload {
  task_id: string;
  error: string;
  step: string;
  screenshot_path: string | null;
}

interface BotStoppedPayload {
  task_id: string;
  reason: string;
}

interface AiUsageWarningPayload {
  provider: string;
  usage_percent: number;
  threshold: number;
}

interface CaptchaDetectedPayload {
  screenshot_path: string | null;
  timestamp: string;
}

interface SchedulerTriggeredPayload {
  schedule_id: number;
  task_type: string;
}

interface LogNewPayload {
  log_entry: Record<string, unknown>;
}

type WsEvent =
  | { type: 'device:status'; payload: DeviceStatusPayload }
  | { type: 'bot:started'; payload: BotStartedPayload }
  | { type: 'bot:step'; payload: BotStepPayload }
  | { type: 'bot:completed'; payload: BotCompletedPayload }
  | { type: 'bot:error'; payload: BotErrorPayload }
  | { type: 'bot:stopped'; payload: BotStoppedPayload }
  | { type: 'log:new'; payload: LogNewPayload }
  | { type: 'ai:usage_warning'; payload: AiUsageWarningPayload }
  | { type: 'captcha:detected'; payload: CaptchaDetectedPayload }
  | { type: 'scheduler:triggered'; payload: SchedulerTriggeredPayload };

export type WsEventListener = (event: WsEvent) => void;

// ─── Event bus (module-level singleton) ──────────────────────────────────────

const listeners = new Set<WsEventListener>();

/** Subscribe to raw WebSocket events. Returns an unsubscribe function. */
export function subscribeToWsEvents(listener: WsEventListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function emitEvent(event: WsEvent) {
  listeners.forEach((fn) => fn(event));
}

// ─── Reconnect config ─────────────────────────────────────────────────────────

const INITIAL_DELAY_MS = 1_000;
const MAX_DELAY_MS = 30_000;
const BACKOFF_MULTIPLIER = 2;

// ─── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Mount once near the root of the app (e.g., _app.tsx or a layout component).
 * Sets up the WebSocket connection and dispatches events to Zustand stores and
 * the shared event bus.
 */
export function useWebSocket() {
  const { setRunning, addStep, setError, reset } = useBotStore();
  const updateDevice = useDeviceStore((s) => s.updateStatus);
  const addToast = useNotifStore((s) => s.addToast);

  const wsRef = useRef<WebSocket | null>(null);
  const retryDelayRef = useRef(INITIAL_DELAY_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    const url =
      process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000/ws';

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      // Reset back-off on successful connection
      retryDelayRef.current = INITIAL_DELAY_MS;
      // Ask the server to subscribe us to device events
      ws.send(JSON.stringify({ type: 'subscribe:device', payload: {} }));
    };

    ws.onmessage = ({ data }: MessageEvent<string>) => {
      let event: WsEvent;
      try {
        event = JSON.parse(data) as WsEvent;
      } catch {
        console.warn('[useWebSocket] Could not parse message:', data);
        return;
      }

      // Dispatch to stores
      switch (event.type) {
        case 'device:status':
          updateDevice({
            connected: event.payload.connected,
            deviceId: event.payload.device_id,
            model: event.payload.model,
            androidVersion: event.payload.android_version,
            batteryLevel: event.payload.battery_level,
            linkedinInstalled: event.payload.linkedin_installed,
            status: event.payload.status ?? (event.payload.connected ? 'connected' : 'disconnected'),
            lastChecked: new Date(),
          });
          break;

        case 'bot:started':
          setRunning(true, event.payload.module, event.payload.task_id);
          break;

        case 'bot:step':
          addStep({
            step: event.payload.step,
            message: event.payload.message,
            status: event.payload.status,
            timestamp: event.payload.timestamp,
          });
          break;

        case 'bot:completed':
          setRunning(false);
          addToast({ type: 'success', message: 'Bot selesai' });
          break;

        case 'bot:error':
          setError(event.payload.error);
          addToast({ type: 'error', message: event.payload.error });
          break;

        case 'bot:stopped':
          setRunning(false);
          addToast({ type: 'info', message: `Bot dihentikan: ${event.payload.reason}` });
          break;

        case 'ai:usage_warning':
          addToast({
            type: 'warning',
            message: `${event.payload.provider}: ${event.payload.usage_percent.toFixed(1)}% quota`,
          });
          break;

        case 'captcha:detected':
          addToast({ type: 'error', message: 'CAPTCHA terdeteksi! Bot dihentikan.' });
          break;

        case 'scheduler:triggered':
          addToast({
            type: 'info',
            message: `Jadwal #${event.payload.schedule_id} (${event.payload.task_type}) dijalankan`,
            duration: 5_000,
          });
          break;

        default:
          break;
      }

      // Fan out to external listeners
      emitEvent(event);
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;

      const delay = retryDelayRef.current;
      retryDelayRef.current = Math.min(delay * BACKOFF_MULTIPLIER, MAX_DELAY_MS);

      reconnectTimerRef.current = setTimeout(() => {
        if (!unmountedRef.current) connect();
      }, delay);
    };

    ws.onerror = () => {
      // onclose will fire after onerror; reconnect logic lives there
      ws.close();
    };
  }, [setRunning, addStep, setError, reset, updateDevice, addToast]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  /** Manually send a message to the server (fire-and-forget). */
  const send = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    const ws = wsRef.current;
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload }));
    }
  }, []);

  return { send };
}
