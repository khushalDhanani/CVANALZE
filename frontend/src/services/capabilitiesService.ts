import { apiClient } from './apiClient';
import type { ApplicationCapabilities } from '@/types/capabilities';

export const capabilitiesService = {
  get: (): Promise<ApplicationCapabilities> =>
    apiClient.get<ApplicationCapabilities>('/api/config/capabilities'),
};
