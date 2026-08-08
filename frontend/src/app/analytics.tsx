import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { BarChart3, CpuIcon, Database, HardDrive, RefreshCw, Zap, CheckCircle2, ShieldCheck, AlertCircle, X } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { analyticsService, PerformanceMetricsResponse } from '@/services/analyticsService';
import { usePageTitle } from '@/hooks/usePageTitle';
import { CacheAnalyticsResponse } from '@/types/api';
import { Card, Button, Badge, StatCard, DenseRow, Breadcrumbs } from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { PERFORMANCE_SLO } from '@/constants/slo';
import { vectorDbService } from '@/services/vectorDbService';
import { candidateService } from '@/services/candidateService';
import { VectorDbStatusResponse, TalentPoolsResponse } from '@/types/api';
import { useRouter } from 'expo-router';

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
  const [endpointErrors, setEndpointErrors] = useState<{ cache?: string; perf?: string; vector?: string; pools?: string }>({});
  const [clearing, setClearing] = useState<boolean>(false);
  const [purgeModalVisible, setPurgeModalVisible] = useState<boolean>(false);
  const [noticeMsg, setNoticeMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [vectorStatus, setVectorStatus] = useState<VectorDbStatusResponse | null>(null);
  const [talentPools, setTalentPools] = useState<TalentPoolsResponse | null>(null);
  const [syncingVectorDb, setSyncingVectorDb] = useState(false);
  const router = useRouter();

  const fetchTelemetry = async () => {
    setLoading(true);
    setError(null);
    const errors: { cache?: string; perf?: string; vector?: string; pools?: string } = {};

    try {
      const results = await Promise.allSettled([
        analyticsService.getCacheAnalytics(),
        analyticsService.getPerformanceMetrics(),
        vectorDbService.getStatus(),
        candidateService.getTalentPools(),
      ]);

      if (results[0].status === 'fulfilled') {
        setCacheAnalytics(results[0].value);
      } else {
        setCacheAnalytics(null);
        errors.cache = results[0].reason?.message || 'Cache telemetry unavailable';
      }

      if (results[1].status === 'fulfilled') {
        setPerformanceMetrics(results[1].value);
      } else {
        setPerformanceMetrics(null);
        errors.perf = results[1].reason?.message || 'Pipeline metrics unavailable';
      }

      if (results[2].status === 'fulfilled') {
        setVectorStatus(results[2].value);
      } else {
        setVectorStatus(null);
        errors.vector = results[2].reason?.message || 'Vector DB status unavailable';
      }

      if (results[3].status === 'fulfilled') {
        setTalentPools(results[3].value);
      } else {
        setTalentPools(null);
        errors.pools = results[3].reason?.message || 'Talent pools unavailable';
      }

      setEndpointErrors(errors);

      // If all 4 subsystems failed, present page-level error
      if (Object.keys(errors).length === 4) {
        setError('All telemetry and observability subsystems are currently unreachable.');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch telemetry metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
  }, []);

  const handleConfirmPurge = async () => {
    setClearing(true);
    setNoticeMsg(null);
    try {
      const res = await analyticsService.invalidateCache('*');
      setNoticeMsg({ type: 'success', text: res.message || 'Cache purged and invalidated successfully.' });
      setPurgeModalVisible(false);
      fetchTelemetry();
    } catch (err: any) {
      setNoticeMsg({ type: 'error', text: err.message || 'Cache purge failed.' });
      setPurgeModalVisible(false);
    } finally {
      setClearing(false);
      setTimeout(() => setNoticeMsg(null), 4500);
    }
  };

  const handleSyncVectorDb = async () => {
    setSyncingVectorDb(true);
    setNoticeMsg(null);
    try {
      const res = await vectorDbService.syncEmbeddings();
      setNoticeMsg({ type: 'success', text: res.message || 'Vector DB sync initiated.' });
    } catch (err: any) {
      setNoticeMsg({ type: 'error', text: err.message || 'Failed to sync Vector DB.' });
    } finally {
      setSyncingVectorDb(false);
      setTimeout(() => setNoticeMsg(null), 4500);
    }
  };

  const globalMetrics = cacheAnalytics?.global_metrics;
  const cacheTelemetry = performanceMetrics?.cache_telemetry;
  const pipelineTelemetry = performanceMetrics?.pipeline_telemetry;
  const redisStats = cacheAnalytics?.system_stats?.redis;

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Analytics & Telemetry' }]} />

      {/* Responsive Stacked Header */}
      <View className="flex-col sm:flex-row items-start sm:items-center justify-between px-3 py-2.5 bg-surface border-b border-border gap-3">
        <View className="flex-row items-center gap-2">
          <BarChart3 size={18} color={COLORS.primary} />
          <View>
            <Text className="text-base font-sans-bold text-text-primary">Analytics & Telemetry</Text>
            <Text className="text-[11px] font-sans text-text-muted">
              Real-time Observability: L1/L2 Cache Ratios & Pipeline Stage Latencies
            </Text>
          </View>
        </View>
        <View className="flex-row items-center gap-2 self-stretch sm:self-auto justify-end">
          <Button
            label="Purge All Cache"
            variant="destructive"
            size="sm"
            onPress={() => setPurgeModalVisible(true)}
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

      {/* Purge Confirmation Modal */}
      <Modal
        visible={purgeModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setPurgeModalVisible(false)}
      >
        <View className="flex-1 bg-black/60 items-center justify-center p-4">
          <Card className="w-full max-w-md bg-surface p-5 border border-border gap-4 shadow-xl">
            <View className="flex-row justify-between items-center border-b border-border pb-3">
              <View className="flex-row items-center gap-2">
                <AlertCircle size={18} color={COLORS.danger} />
                <Text className="text-base font-sans-bold text-text-primary">Confirm Cache Invalidation</Text>
              </View>
              <Pressable
                onPress={() => setPurgeModalVisible(false)}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                accessibilityRole="button"
                accessibilityLabel="Close confirmation modal"
              >
                <X size={18} color={COLORS.textMuted} />
              </Pressable>
            </View>

            <Text className="text-xs font-sans text-text-muted leading-5">
              Are you sure you want to purge all application caches? This action will:
            </Text>
            <View className="gap-1.5 pl-2 border-l-2 border-danger/30">
              <Text className="text-xs font-sans text-text-primary">• Flush all L1 In-Memory and L2 Redis cached entries</Text>
              <Text className="text-xs font-sans text-text-primary">• Invalidate parsed candidate models and embeddings</Text>
              <Text className="text-xs font-sans text-text-primary">• Cause brief latency while cache layers rehydrate</Text>
            </View>

            <View className="flex-row justify-end gap-2 pt-2 border-t border-border">
              <Button
                label="Cancel"
                variant="ghost"
                onPress={() => setPurgeModalVisible(false)}
                disabled={clearing}
              />
              <Button
                label={clearing ? 'Purging...' : 'Confirm Purge'}
                variant="destructive"
                onPress={handleConfirmPurge}
                loading={clearing}
                disabled={clearing}
              />
            </View>
          </Card>
        </View>
      </Modal>

      <ScrollView className="flex-1 px-3 py-4">
        {noticeMsg && (
          <Card
            className={`border flex-row items-center justify-center gap-1.5 mb-4 p-3 ${
              noticeMsg.type === 'error' ? 'bg-danger/10 border-danger/30' : 'bg-success/10 border-success/30'
            }`}
          >
            {noticeMsg.type === 'error' ? (
              <AlertCircle size={14} color={COLORS.danger} />
            ) : (
              <CheckCircle2 size={14} color={COLORS.success} />
            )}
            <Text
              className={`text-xs font-sans-semibold ${
                noticeMsg.type === 'error' ? 'text-danger' : 'text-success'
              }`}
            >
              {noticeMsg.text}
            </Text>
          </Card>
        )}

        {loading ? (
          <View className="py-16 items-center">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">
              Loading system telemetry & performance metrics...
            </Text>
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
            <View className="flex-row flex-wrap gap-3">
              <StatCard
                label="Overall Hit Ratio"
                value={
                  endpointErrors.cache
                    ? '— (Unavailable)'
                    : globalMetrics
                    ? `${(globalMetrics.overall_hit_ratio * 100).toFixed(1)}%`
                    : '—'
                }
                sublabel={endpointErrors.cache ? 'Source offline' : 'Global Caching Efficiency'}
                tone={
                  endpointErrors.cache
                    ? 'danger'
                    : globalMetrics && globalMetrics.overall_hit_ratio >= PERFORMANCE_SLO.hitRatio.targetPercent
                    ? 'success'
                    : 'info'
                }
              />
              <StatCard
                label="LLM Calls Prevented"
                value={endpointErrors.cache ? '—' : globalMetrics?.llm_calls_prevented ?? 0}
                sublabel={endpointErrors.cache ? 'Telemetry offline' : 'Bypassed via Local Cache'}
                tone={endpointErrors.cache ? 'neutral' : 'success'}
              />
              <StatCard
                label="DB Queries Bypassed"
                value={endpointErrors.cache ? '—' : globalMetrics?.db_queries_prevented ?? 0}
                sublabel={endpointErrors.cache ? 'Telemetry offline' : 'In-Memory Cache Hits'}
                tone={endpointErrors.cache ? 'neutral' : 'info'}
              />
              <StatCard
                label="Embeddings Generated"
                value={endpointErrors.perf ? '—' : pipelineTelemetry?.total_embeddings_generated ?? 0}
                sublabel={
                  endpointErrors.perf
                    ? 'Telemetry offline'
                    : `${pipelineTelemetry?.batch_requests_count || 0} Batch Operations`
                }
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
                {endpointErrors.perf ? (
                  <Badge label="Unavailable" tone="danger" />
                ) : (
                  <Badge label="L1/L2 Multi-Tier" tone="info" />
                )}
              </View>

              {endpointErrors.perf ? (
                <View className="p-3 bg-danger/5 border border-danger/20 rounded-md">
                  <Text className="text-xs font-sans text-danger">
                    Cache telemetry unavailable: {endpointErrors.perf}
                  </Text>
                </View>
              ) : (
                <View className="flex-row flex-wrap gap-3">
                  {/* L1 Memory Cache */}
                  <View className="flex-1 min-w-[280px] bg-background p-3 rounded-md border border-border gap-1.5">
                    <View className="flex-row justify-between items-center">
                      <Text className="text-xs font-sans-bold text-primary">L1 In-Memory LRU Cache</Text>
                      <Badge label={`${cacheTelemetry?.l1_hit_ratio_percent || 0}% Hit`} tone="success" />
                    </View>
                    <Text className="text-xs font-sans text-text-muted">
                      Sub-millisecond latency store (Max capacity: 5,000 objects)
                    </Text>
                    <View className="flex-row justify-between pt-1 border-t border-border/60 mt-1">
                      <Text className="text-[11px] font-sans text-text-muted">
                        Hits: <Text className="font-sans-bold text-text-primary">{cacheTelemetry?.l1_memory_hits ?? 0}</Text>
                      </Text>
                      <Text className="text-[11px] font-sans text-text-muted">
                        Misses: <Text className="font-sans-bold text-text-primary">{cacheTelemetry?.l1_memory_misses ?? 0}</Text>
                      </Text>
                    </View>
                  </View>

                  {/* L2 Redis Shared Cache */}
                  <View className="flex-1 min-w-[280px] bg-background p-3 rounded-md border border-border gap-1.5">
                    <View className="flex-row justify-between items-center">
                      <Text className="text-xs font-sans-bold text-info">L2 Redis Shared Cache</Text>
                      <Badge label={`${cacheTelemetry?.l2_hit_ratio_percent || 0}% Hit`} tone="info" />
                    </View>
                    <Text className="text-xs font-sans text-text-muted">
                      Persistent cache store ({redisStats?.used_memory_human || 'Active'}, {redisStats?.total_keys ?? 0} keys)
                    </Text>
                    <View className="flex-row justify-between pt-1 border-t border-border/60 mt-1">
                      <Text className="text-[11px] font-sans text-text-muted">
                        Hits: <Text className="font-sans-bold text-text-primary">{cacheTelemetry?.l2_redis_hits ?? 0}</Text>
                      </Text>
                      <Text className="text-[11px] font-sans text-text-muted">
                        Misses: <Text className="font-sans-bold text-text-primary">{cacheTelemetry?.l2_redis_misses ?? 0}</Text>
                      </Text>
                    </View>
                  </View>
                </View>
              )}
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
                {endpointErrors.perf ? (
                  <Badge label="Offline" tone="warning" />
                ) : (
                  <Badge label="Observability" tone="warning" />
                )}
              </View>

              {endpointErrors.perf ? (
                <View className="p-3 bg-warning/5 border border-warning/20 rounded-md">
                  <Text className="text-xs font-sans text-warning">
                    Pipeline stage latencies unavailable: {endpointErrors.perf}
                  </Text>
                </View>
              ) : (
                <View className="gap-2">
                  {Object.entries(pipelineTelemetry?.stage_timings_ms || {}).map(([key, timing]) => {
                    const label = STAGE_LABELS[key] || key;
                    const timingNum = Number(timing) || 0;
                    let barColor = 'bg-success';
                    if (timingNum > PERFORMANCE_SLO.stageLatency.warningMs) barColor = 'bg-danger';
                    else if (timingNum > PERFORMANCE_SLO.stageLatency.optimalMs) barColor = 'bg-warning';

                    return (
                      <View key={key} className="bg-background p-2.5 rounded-md border border-border gap-1">
                        <View className="flex-row justify-between items-center">
                          <Text className="text-xs font-sans-medium text-text-primary">{label}</Text>
                          <Text className="text-xs font-sans-mono font-bold text-primary">{timingNum.toFixed(1)} ms</Text>
                        </View>
                        <View className="h-1.5 w-full bg-border rounded-full overflow-hidden">
                          <View
                            className={`h-full rounded-full ${barColor}`}
                            style={{
                              width: `${Math.min(
                                100,
                                Math.max(5, (timingNum / PERFORMANCE_SLO.stageLatency.maxScaleMs) * 100)
                              )}%`,
                            }}
                          />
                        </View>
                      </View>
                    );
                  })}
                </View>
              )}
            </Card>

            {/* Pipeline Execution Order Guarantee Box */}
            <Card className="bg-info/10 border-info/30 gap-2">
              <View className="flex-row items-center justify-between">
                <View className="flex-row items-center gap-2">
                  <ShieldCheck size={16} color={COLORS.info} />
                  <Text className="text-xs font-sans-bold text-info uppercase tracking-wider">
                    Pipeline Execution Invariant
                  </Text>
                </View>
                <Badge label="Architectural Guarantee" tone="info" />
              </View>
              <Text className="text-xs font-sans text-info leading-5">
                {performanceMetrics?.retrieval_order_guarantee?.sequence ||
                  'Architectural Invariant: Semantic vector retrieval strictly precedes the rule-based candidate scoring engine.'}
              </Text>
            </Card>

            {/* Vector DB Status Panel */}
            <Card className="gap-3">
              <View className="flex-row items-center justify-between border-b border-border pb-2">
                <View className="flex-row items-center gap-2">
                  <Database size={16} color={COLORS.success} />
                  <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
                    Vector Database (pgvector)
                  </Text>
                </View>
                {endpointErrors.vector ? (
                  <Badge label="Unavailable" tone="danger" />
                ) : (
                  <Badge
                    label={vectorStatus?.pgvector_enabled ? 'Enabled' : 'Disabled'}
                    tone={vectorStatus?.pgvector_enabled ? 'success' : 'neutral'}
                  />
                )}
              </View>

              {endpointErrors.vector ? (
                <View className="p-3 bg-danger/5 border border-danger/20 rounded-md">
                  <Text className="text-xs font-sans text-danger">
                    Vector database status unavailable: {endpointErrors.vector}
                  </Text>
                </View>
              ) : (
                <>
                  <View className="flex-row flex-wrap gap-3">
                    <View className="flex-1 min-w-[130px] md:min-w-[150px] bg-background border border-border rounded p-2">
                      <Text className="text-[10px] font-sans-bold text-text-muted uppercase">Status</Text>
                      <Text className="text-xs font-sans-medium text-text-primary mt-1">
                        {vectorStatus?.pg_database_connected ? 'Connected' : 'Disconnected'}
                      </Text>
                    </View>
                    <View className="flex-1 min-w-[130px] md:min-w-[150px] bg-background border border-border rounded p-2">
                      <Text className="text-[10px] font-sans-bold text-text-muted uppercase">Model</Text>
                      <Text className="text-xs font-sans-medium text-text-primary mt-1">
                        {vectorStatus?.embedding_model || 'Unknown'}
                      </Text>
                    </View>
                    <View className="flex-1 min-w-[130px] md:min-w-[150px] bg-background border border-border rounded p-2">
                      <Text className="text-[10px] font-sans-bold text-text-muted uppercase">Candidate Vectors</Text>
                      <Text className="text-xs font-sans-medium text-text-primary mt-1">
                        {vectorStatus?.candidate_embeddings_count ?? 0}
                      </Text>
                    </View>
                    <View className="flex-1 min-w-[130px] md:min-w-[150px] bg-background border border-border rounded p-2">
                      <Text className="text-[10px] font-sans-bold text-text-muted uppercase">Vacancy Vectors</Text>
                      <Text className="text-xs font-sans-medium text-text-primary mt-1">
                        {vectorStatus?.vacancy_embeddings_count ?? 0}
                      </Text>
                    </View>
                  </View>

                  <View className="flex-row justify-end mt-2">
                    <Button
                      label="Sync Embeddings"
                      icon={<RefreshCw size={14} color="white" />}
                      onPress={handleSyncVectorDb}
                      loading={syncingVectorDb}
                      disabled={syncingVectorDb}
                      size="sm"
                    />
                  </View>
                </>
              )}
            </Card>

            {/* Talent Pools Panel */}
            <Card className="gap-3">
              <View className="flex-row items-center justify-between border-b border-border pb-2">
                <View className="flex-row items-center gap-2">
                  <HardDrive size={16} color={COLORS.info} />
                  <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
                    Internal Talent Pools
                  </Text>
                </View>
                {endpointErrors.pools ? (
                  <Badge label="Unavailable" tone="danger" />
                ) : (
                  <Badge label={`${talentPools?.total_pools ?? 0} Active Pools`} tone="info" />
                )}
              </View>

              {endpointErrors.pools ? (
                <View className="p-3 bg-danger/5 border border-danger/20 rounded-md">
                  <Text className="text-xs font-sans text-danger">
                    Talent pools telemetry unavailable: {endpointErrors.pools}
                  </Text>
                </View>
              ) : (
                <View className="gap-2">
                  {!talentPools?.talent_pools || talentPools.talent_pools.length === 0 ? (
                    <Text className="text-xs text-text-muted">No talent pools generated yet.</Text>
                  ) : (
                    talentPools.talent_pools.map((pool, idx) => (
                      <View key={idx} className="bg-surface border border-border rounded p-3 gap-2">
                        <View className="flex-row justify-between items-center">
                          <Text className="text-xs font-sans-bold text-text-primary">{pool.pool_name}</Text>
                          <Badge label={`${pool.candidate_count} Candidates`} tone="neutral" />
                        </View>
                        <View className="flex-row flex-wrap gap-2">
                          {pool.sample_candidates.map((cand, cidx) => (
                            <View
                              key={cidx}
                              className="bg-background border border-border rounded px-2 py-1 flex-row items-center gap-1.5"
                            >
                              <Text
                                className="text-[11px] font-sans-medium text-primary cursor-pointer"
                                onPress={() => router.push(`/candidates/${encodeURIComponent(cand.candidate_id)}` as any)}
                              >
                                {cand.full_name}
                              </Text>
                              <Text className="text-[10px] text-text-muted border-l border-border pl-1.5">
                                {cand.experience_years ? `${cand.experience_years}y` : 'N/A'}
                              </Text>
                            </View>
                          ))}
                        </View>
                      </View>
                    ))
                  )}
                </View>
              )}
            </Card>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
