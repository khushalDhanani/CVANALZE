import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { BarChart3, CpuIcon, Database, HardDrive, RefreshCw, Zap, CheckCircle2, ShieldCheck } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { analyticsService, PerformanceMetricsResponse } from '@/services/analyticsService';
import { usePageTitle } from '@/hooks/usePageTitle';
import { CacheAnalyticsResponse } from '@/types/api';
import { Card, Button, Badge, StatCard, DenseRow, Breadcrumbs } from '@/components/ui';
import { COLORS } from '@/constants/colors';

const STAGE_LABELS: Record<string, string> = {
  stage1_resume_profiling: 'Stage 1: Resume Layout Profiling',
  stage2_embedding_generation: 'Stage 2: Embedding Generation',
  stage3_vector_retrieval: 'Stage 3: pgvector Retrieval',
  stage4_prefilter_fusion: 'Stage 4: Prefilter & Reciprocal Rank Fusion',
  stage5_confidence_gate: 'Stage 5: Confidence Gating',
  stage6_llm_evaluation: 'Stage 6: LLM Reasoning Evaluation',
  stage7_scoring_engine: 'Stage 7: Rule-Based Scoring Engine',
  stage8_final_ranking: 'Stage 8: Final Candidate Ranking',
};

export default function AnalyticsScreen() {
  usePageTitle('Analytics & Telemetry | AIRIS');
  const [cacheAnalytics, setCacheAnalytics] = useState<CacheAnalyticsResponse | null>(null);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetricsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [clearing, setClearing] = useState<boolean>(false);
  const [noticeMsg, setNoticeMsg] = useState<string | null>(null);

  const fetchTelemetry = async () => {
    setLoading(true);
    setError(null);
    try {
      const [cacheRes, perfRes] = await Promise.all([
        analyticsService.getCacheAnalytics().catch(() => null),
        analyticsService.getPerformanceMetrics().catch(() => null),
      ]);
      setCacheAnalytics(cacheRes);
      setPerformanceMetrics(perfRes);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch telemetry metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
  }, []);

  const handleInvalidateCache = async () => {
    setClearing(true);
    setNoticeMsg(null);
    try {
      const res = await analyticsService.invalidateCache('*');
      setNoticeMsg(res.message || 'Cache invalidated successfully!');
      fetchTelemetry();
    } catch (err: any) {
      setNoticeMsg(err.message || 'Cache invalidation failed.');
    } finally {
      setClearing(false);
      setTimeout(() => setNoticeMsg(null), 4000);
    }
  };

  const globalMetrics = cacheAnalytics?.global_metrics;
  const cacheTelemetry = performanceMetrics?.cache_telemetry;
  const pipelineTelemetry = performanceMetrics?.pipeline_telemetry;
  const redisStats = cacheAnalytics?.system_stats?.redis;

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Analytics & Telemetry' }]} />
      {/* Sticky Header */}
      <View className="flex-row items-center justify-between px-3 py-2 bg-surface border-b border-border">
        <View className="flex-row items-center gap-2">
          <BarChart3 size={18} color={COLORS.primary} />
          <View>
            <Text className="text-base font-sans-bold text-text-primary">Analytics & Telemetry</Text>
            <Text className="text-[11px] font-sans text-text-muted">
              Real-time Observability: L1/L2 Cache Ratios & Pipeline Stage Latencies
            </Text>
          </View>
        </View>
        <View className="flex-row items-center gap-2">
          <Button
            label={clearing ? 'Clearing...' : 'Purge All Cache'}
            variant="secondary"
            size="sm"
            onPress={handleInvalidateCache}
            loading={clearing}
            disabled={clearing}
          />
          <Button
            label="Refresh"
            variant="ghost"
            size="sm"
            onPress={fetchTelemetry}
            disabled={loading}
          />
        </View>
      </View>

      <ScrollView className="flex-1 px-3 py-4">
        {noticeMsg && (
          <Card className="bg-success/10 border-success/30 flex-row items-center justify-center gap-1.5 mb-4 p-3">
            <CheckCircle2 size={14} color={COLORS.success} />
            <Text className="text-xs font-sans-semibold text-success">
              {noticeMsg}
            </Text>
          </Card>
        )}

        {loading ? (
          <View className="py-16 items-center">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">Loading system telemetry & performance metrics...</Text>
          </View>
        ) : error ? (
          <Card className="bg-danger/10 border-danger/30 p-4">
            <Text className="text-xs font-sans-semibold text-danger">{error}</Text>
            <View className="mt-2 self-start">
              <Button label="Try Again" variant="ghost" onPress={fetchTelemetry} />
            </View>
          </Card>
        ) : (
          <View className="gap-4 pb-8">
            {/* Quick Metrics Grid */}
            <View className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard
                label="Overall Hit Ratio"
                value={globalMetrics ? `${(globalMetrics.overall_hit_ratio * 100).toFixed(1)}%` : 'N/A'}
                sublabel="Global Caching Efficiency"
                tone={globalMetrics && globalMetrics.overall_hit_ratio >= 0.7 ? 'success' : 'info'}
              />
              <StatCard
                label="LLM Calls Prevented"
                value={globalMetrics?.llm_calls_prevented ?? 0}
                sublabel="Bypassed via Local Cache"
                tone="success"
              />
              <StatCard
                label="DB Queries Bypassed"
                value={globalMetrics?.db_queries_prevented ?? 0}
                sublabel="In-Memory Cache Hits"
                tone="info"
              />
              <StatCard
                label="Embeddings Generated"
                value={pipelineTelemetry?.total_embeddings_generated ?? 0}
                sublabel={`${pipelineTelemetry?.batch_requests_count || 0} Batch Operations`}
                tone="neutral"
              />
            </View>

            {/* Multi-Level Cache Telemetry Card */}
            <Card className="gap-3">
              <View className="flex-row items-center justify-between border-b border-border pb-2">
                <View className="flex-row items-center gap-2">
                  <CpuIcon size={16} color={COLORS.primary} />
                  <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
                    Multi-Level Cache Telemetry (L1 Memory / L2 Redis)
                  </Text>
                </View>
                <Badge label="L1/L2 Multi-Tier" tone="info" />
              </View>

              <View className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* L1 Memory Cache */}
                <View className="bg-background p-3 rounded-md border border-border gap-1.5">
                  <View className="flex-row justify-between items-center">
                    <Text className="text-xs font-sans-bold text-primary">L1 In-Memory LRU Cache</Text>
                    <Badge label={`${cacheTelemetry?.l1_hit_ratio_percent || 0}% Hit`} tone="success" />
                  </View>
                  <Text className="text-xs font-sans text-text-muted">
                    Sub-millisecond latency store (Max capacity: 5,000 objects)
                  </Text>
                  <View className="flex-row justify-between pt-1 border-t border-border/60 mt-1">
                    <Text className="text-[11px] font-sans text-text-muted">
                      Hits: <Text className="font-sans-bold text-text-primary">{cacheTelemetry?.l1_memory_hits || 0}</Text>
                    </Text>
                    <Text className="text-[11px] font-sans text-text-muted">
                      Misses: <Text className="font-sans-bold text-text-primary">{cacheTelemetry?.l1_memory_misses || 0}</Text>
                    </Text>
                  </View>
                </View>

                {/* L2 Redis Shared Cache */}
                <View className="bg-background p-3 rounded-md border border-border gap-1.5">
                  <View className="flex-row justify-between items-center">
                    <Text className="text-xs font-sans-bold text-info">L2 Redis Shared Cache</Text>
                    <Badge label={`${cacheTelemetry?.l2_hit_ratio_percent || 0}% Hit`} tone="info" />
                  </View>
                  <Text className="text-xs font-sans text-text-muted">
                    Persistent cache store ({redisStats?.used_memory_human || 'Active'}, {redisStats?.total_keys || 0} keys)
                  </Text>
                  <View className="flex-row justify-between pt-1 border-t border-border/60 mt-1">
                    <Text className="text-[11px] font-sans text-text-muted">
                      Hits: <Text className="font-sans-bold text-text-primary">{cacheTelemetry?.l2_redis_hits || 0}</Text>
                    </Text>
                    <Text className="text-[11px] font-sans text-text-muted">
                      Misses: <Text className="font-sans-bold text-text-primary">{cacheTelemetry?.l2_redis_misses || 0}</Text>
                    </Text>
                  </View>
                </View>
              </View>
            </Card>

            {/* 8-Stage Pipeline Stage Execution Latencies */}
            <Card className="gap-3">
              <View className="flex-row items-center justify-between border-b border-border pb-2">
                <View className="flex-row items-center gap-2">
                  <Zap size={16} color={COLORS.warning} />
                  <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
                    8-Stage Pipeline Stage Latencies (ms)
                  </Text>
                </View>
                <Badge label="Observability" tone="warning" />
              </View>

              <View className="gap-2">
                {Object.entries(pipelineTelemetry?.stage_timings_ms || {}).map(([key, timing]) => {
                  const label = STAGE_LABELS[key] || key;
                  const timingNum = Number(timing) || 0;
                  let barColor = 'bg-success';
                  if (timingNum > 300) barColor = 'bg-danger';
                  else if (timingNum > 100) barColor = 'bg-warning';

                  return (
                    <View key={key} className="bg-background p-2.5 rounded-md border border-border gap-1">
                      <View className="flex-row justify-between items-center">
                        <Text className="text-xs font-sans-medium text-text-primary">{label}</Text>
                        <Text className="text-xs font-sans-mono font-bold text-primary">{timingNum.toFixed(1)} ms</Text>
                      </View>
                      <View className="h-1.5 w-full bg-border rounded-full overflow-hidden">
                        <View
                          className={`h-full rounded-full ${barColor}`}
                          style={{ width: `${Math.min(100, Math.max(5, (timingNum / 500) * 100))}%` }}
                        />
                      </View>
                    </View>
                  );
                })}
              </View>
            </Card>

            {/* Pipeline Execution Order Guarantee Box */}
            <Card className="bg-info/10 border-info/30 gap-2">
              <View className="flex-row items-center gap-2">
                <ShieldCheck size={16} color={COLORS.info} />
                <Text className="text-xs font-sans-bold text-info uppercase tracking-wider">
                  Pipeline Execution Order Guarantee
                </Text>
              </View>
              <Text className="text-xs font-sans text-info leading-5">
                {performanceMetrics?.retrieval_order_guarantee?.sequence || 'Semantic retrieval strictly precedes rule scoring engine.'}
              </Text>
            </Card>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
