import React from 'react';
import { StatusDot, Button } from '../atoms';

export interface DeviceStatus {
  connected: boolean;
  device_id?: string | null;
  model?: string | null;
  linkedin_installed?: boolean;
}

export interface DeviceStatusBarProps {
  status: DeviceStatus;
  onReconnect?: () => void;
}

export const DeviceStatusBar: React.FC<DeviceStatusBarProps> = ({ status, onReconnect }) => {
  const dotStatus = status.connected
    ? status.linkedin_installed ? 'online' : 'warning'
    : 'offline';

  const label = status.connected
    ? status.linkedin_installed
      ? `${status.model ?? status.device_id ?? 'HP'} — LinkedIn Siap`
      : `${status.model ?? status.device_id ?? 'HP'} — LinkedIn Tidak Ditemukan`
    : 'HP Tidak Terhubung';

  return (
    <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-2 shadow-sm">
      <StatusDot status={dotStatus} />
      <span className="text-sm text-gray-700 flex-1">{label}</span>
      {!status.connected && onReconnect && (
        <Button variant="ghost" size="sm" onClick={onReconnect}>
          Reconnect
        </Button>
      )}
    </div>
  );
};
