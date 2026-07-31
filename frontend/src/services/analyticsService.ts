import { apiClient } from './apiClient';
import { CacheAnalyticsResponse } from '@/types/api';

export interface PerformanceMetricsResponse {
  cache_telemetry: {
    l1_memory_hits: number;
    l1_memory_misses: number;
    l1_hit_ratio_percent: number;
    l2_redis_hits: number;
    l2_redis_misses: number;
    l2_hit_ratio_percent: number;
  };
  pipeline_telemetry: {
    batch_requests_count: number;
    total_embeddings_generated: number;
    retry_attempts_count: number;
    stage_timings_ms: Record<string, number>;
  };
  retrieval_order_guarantee: {
    sequence: string;
    semantic_retrieval_precedes_scoring: boolean;
  };
}

export const analyticsService = {
  /**
   * Retrieve cache performance metrics, Redis stats, and hit ratios.
   */
  getCacheAnalytics: (): Promise<CacheAnalyticsResponse> => {
    return apiClient.get<CacheAnalyticsResponse>('/api/analytics/cache');
  },

  /**
   * Retrieve real-time telemetry metrics: L1/L2 cache hit ratios, pipeline stage latencies.
   */
  getPerformanceMetrics: (): Promise<PerformanceMetricsResponse> => {
    return apiClient.get<PerformanceMetricsResponse>('/api/performance/metrics');
  },

  /**
   * Invalidate multi-level LRU memory and shared Redis cache entries matching pattern.
   */
  invalidateCache: (pattern: string = '*'): Promise<{ pattern: string; cleared: boolean; message: string }> => {
    return apiClient.post<{ pattern: string; cleared: boolean; message: string }>('/api/performance/cache/invalidate', {
      pattern,
    });
  },
};

