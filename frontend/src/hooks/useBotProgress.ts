/**
 * useBotProgress
 * Subscribes to bot_* WebSocket events and exposes the current bot execution
 * state (running status, module, steps, errors) from the Zustand botStore.
 *
 * Requirements: 2.10
 */

import { useEffect } from 'react';
import { useBotStore } from '../stores/botStore';
import { subscribeToWsEvents } from './useWebSocket';
import type { BotModule, BotStep } from '../stores/botStore';

export interface BotProgressState {
  /** Whether a bot task is currently executing. */
  isRunning: boolean;
  /** Active bot module (A = Content, B = Promo, C = Engage, D = Job Hunter). */
  currentModule: BotModule | null;
  /** UUID of the running task, set by the backend on bot:started. */
  taskId: string | null;
  /** Ordered list of execution steps received so far. */
  steps: BotStep[];
  /** Last error message (cleared when a new task starts). */
  error: string | null;
  /** Reset state — useful when navigating away from the progress panel. */
  reset: () => void;
}

/**
 * Subscribes to bot lifecycle events from WebSocket and surfaces the current
 * progress state. Intended for use in progress panels / dashboards.
 */
export function useBotProgress(): BotProgressState {
  const { isRunning, currentModule, taskId, steps, error, setRunning, addStep, setError, reset } =
    useBotStore();

  useEffect(() => {
    const unsubscribe = subscribeToWsEvents((event) => {
      switch (event.type) {
        case 'bot:started':
          // Clear previous steps/error when a new task begins
          reset();
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
          break;

        case 'bot:error':
          setError(event.payload.error);
          setRunning(false);
          break;

        case 'bot:stopped':
          setRunning(false);
          break;

        default:
          break;
      }
    });

    return unsubscribe;
  }, [setRunning, addStep, setError, reset]);

  return { isRunning, currentModule, taskId, steps, error, reset };
}
