// Barrel export for custom hooks

export { useWebSocket, subscribeToWsEvents } from './useWebSocket';
export type { WsEventListener } from './useWebSocket';

export { useDeviceStatus } from './useDeviceStatus';

export { useBotProgress } from './useBotProgress';
export type { BotProgressState } from './useBotProgress';

export { useApiMutation } from './useApiMutation';
export type {
  HttpMutationMethod,
  MutationOptions,
  ApiMutationError,
  MutationState,
  MutationActions,
} from './useApiMutation';
