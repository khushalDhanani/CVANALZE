import { apiClient } from './apiClient';
import { CacheAnalyticsResponse } from '@/types/api';

export const analyticsService = {
  /**
   * Retrieve cache performance metrics, Redis stats, and hit ratios.
   */
  getCacheAnalytics: (): Promise<CacheAnalyticsResponse> => {
    return apiClient.get<CacheAnalyticsResponse>('/api/analytics/cache');
  },
};
