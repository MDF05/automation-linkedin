import { create } from 'zustand';
import type { DeviceConnectionStatus } from '../types';

interface DeviceState {
  connected: boolean;
  deviceId: string | null;
  model: string | null;
  androidVersion: string | null;
  linkedinInstalled: boolean;
  batteryLevel: number | null;
  status: DeviceConnectionStatus;
  lastChecked: Date | null;
  updateStatus: (s: Partial<Omit<DeviceState, 'updateStatus'>>) => void;
}

export const useDeviceStore = create<DeviceState>((set) => ({
  connected: false,
  deviceId: null,
  model: null,
  androidVersion: null,
  linkedinInstalled: false,
  batteryLevel: null,
  status: 'disconnected',
  lastChecked: null,

  updateStatus: (s) => set((state) => ({ ...state, ...s })),
}));
