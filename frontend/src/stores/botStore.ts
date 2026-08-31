import { create } from 'zustand';

export type BotModule = 'A' | 'B' | 'C' | 'D';

export interface BotStep {
  step: string;
  message: string;
  status: 'running' | 'success' | 'failed' | 'skipped';
  timestamp: string;
}

interface BotState {
  isRunning: boolean;
  currentModule: BotModule | null;
  taskId: string | null;
  steps: BotStep[];
  error: string | null;
  setRunning: (running: boolean, module?: BotModule, taskId?: string) => void;
  addStep: (step: BotStep) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useBotStore = create<BotState>((set) => ({
  isRunning: false,
  currentModule: null,
  taskId: null,
  steps: [],
  error: null,

  setRunning: (running, module, taskId) =>
    set({
      isRunning: running,
      currentModule: module ?? null,
      taskId: taskId ?? null,
    }),

  addStep: (step) =>
    set((state) => ({ steps: [...state.steps, step] })),

  setError: (error) => set({ error }),

  reset: () =>
    set({
      isRunning: false,
      currentModule: null,
      taskId: null,
      steps: [],
      error: null,
    }),
}));
