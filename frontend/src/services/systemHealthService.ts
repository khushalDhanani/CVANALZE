import type { SystemHealthResponse } from '@/types/api';
import { ApiError, apiClient } from './apiClient';

const isSystemHealthResponse = (value: unknown): value is SystemHealthResponse => {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const payload = value as Partial<SystemHealthResponse>;
  return typeof payload.status === 'string'
    && typeof payload.version === 'string'
    && typeof payload.database === 'string'
    && typeof payload.ollama_llm === 'string';
};

export const getDegradedSystemHealth = (error: unknown): SystemHealthResponse | null => {
  if (error instanceof ApiError && error.status === 503 && isSystemHealthResponse(error.data)) {
    return error.data;
  }
  return null;
};

export const systemHealthService = {
  getHealth: async (): Promise<SystemHealthResponse> => {
    try {
      return await apiClient.get<SystemHealthResponse>('/health');
    } catch (error) {
      const degradedHealth = getDegradedSystemHealth(error);
      if (degradedHealth) {
        return degradedHealth;
      }
      throw error;
    }
  },
};
