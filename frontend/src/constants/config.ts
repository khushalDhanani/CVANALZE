import { Platform } from 'react-native';

const getDefaultApiUrl = (): string => {
  if (process.env.EXPO_PUBLIC_API_URL) {
    return process.env.EXPO_PUBLIC_API_URL;
  }
  if (Platform.OS === 'android') {
    return 'http://10.0.2.2:8000';
  }
  return 'http://localhost:8000';
};

export const API_CONFIG = {
  BASE_URL: getDefaultApiUrl(),
  TIMEOUT_MS: 30000,
  POLL_INTERVAL_MS: 3000,
  MAX_POLL_RETRIES: 250,
};
