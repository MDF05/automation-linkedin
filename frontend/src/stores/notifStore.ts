import { create } from 'zustand';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number; // ms; undefined means persistent
}

interface NotifState {
  toasts: Toast[];
  addToast: (t: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

let _counter = 0;

export const useNotifStore = create<NotifState>((set) => ({
  toasts: [],

  addToast: (t) => {
    const id = `toast-${Date.now()}-${_counter++}`;
    const toast: Toast = { ...t, id };
    set((state) => ({ toasts: [...state.toasts, toast] }));

    if (t.duration !== undefined) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((item) => item.id !== id),
        }));
      }, t.duration);
    }
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));
