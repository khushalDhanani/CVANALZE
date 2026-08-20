import { Platform } from 'react-native';
import { parsePositiveInteger, resolveApiBaseUrl } from '@/utils/runtimeConfig';

const development = typeof __DEV__ !== 'undefined'
  ? __DEV__
  : process.env.NODE_ENV !== 'production';

export const API_CONFIG = {
  BASE_URL: resolveApiBaseUrl(process.env.EXPO_PUBLIC_API_URL, Platform.OS, development),
  TIMEOUT_MS: parsePositiveInteger(process.env.EXPO_PUBLIC_API_TIMEOUT_MS, 60000),
  POLL_INTERVAL_MS: parsePositiveInteger(process.env.EXPO_PUBLIC_POLL_INTERVAL_MS, 3000),
  MAX_POLL_RETRIES: parsePositiveInteger(process.env.EXPO_PUBLIC_MAX_POLL_RETRIES, 1200),
};

export function applyServerPollingCapabilities(intervalMs: number, maxAttempts: number): void {
  if (!process.env.EXPO_PUBLIC_POLL_INTERVAL_MS) {
    API_CONFIG.POLL_INTERVAL_MS = parsePositiveInteger(String(intervalMs), API_CONFIG.POLL_INTERVAL_MS);
  }
  if (!process.env.EXPO_PUBLIC_MAX_POLL_RETRIES) {
    API_CONFIG.MAX_POLL_RETRIES = parsePositiveInteger(String(maxAttempts), API_CONFIG.MAX_POLL_RETRIES);
  }
}
