/**
 * useDeviceStatus
 * Subscribes to `device:status` WebSocket events and exposes the current
 * device state from the Zustand deviceStore.
 *
 * Requirements: 1.5
 */

import { useEffect } from 'react';
import { useDeviceStore } from '../stores/deviceStore';
import { subscribeToWsEvents } from './useWebSocket';

/**
 * Returns the current device state and a boolean indicating whether it has
 * been updated at least once since mount (so callers can distinguish "not yet
 * received" from "received but disconnected").
 */
export function useDeviceStatus() {
  const {
    connected,
    deviceId,
    model,
    androidVersion,
    linkedinInstalled,
    batteryLevel,
    status,
    lastChecked,
    updateStatus,
  } = useDeviceStore();

  useEffect(() => {
    const unsubscribe = subscribeToWsEvents((event) => {
      if (event.type !== 'device:status') return;

      const p = event.payload;
      updateStatus({
        connected: p.connected,
        deviceId: p.device_id,
        model: p.model,
        androidVersion: p.android_version,
        batteryLevel: p.battery_level,
        linkedinInstalled: p.linkedin_installed,
        status: p.status ?? (p.connected ? 'connected' : 'disconnected'),
        lastChecked: new Date(),
      });
    });

    return unsubscribe;
  }, [updateStatus]);

  return {
    connected,
    deviceId,
    model,
    androidVersion,
    linkedinInstalled,
    batteryLevel,
    status,
    lastChecked,
  };
}
