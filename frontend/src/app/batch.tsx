import React, { useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Text,
  View,
} from 'react-native';
import { Radio, CheckCircle, Info, AlertTriangle } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { useBatchProgress } from '@/hooks/useBatchProgress';
import { usePageTitle } from '@/hooks/usePageTitle';
import { BatchCandidateResult } from '@/types/api';
import { Card, Button, SegmentedControl, EmptyState, Badge, Breadcrumbs, ErrorBanner } from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { BATCH_CANDIDATE_LIMITS } from '@/constants/limits';

export default function BatchScreen() {
  usePageTitle('Batch Candidate Matching | AIRIS');
  const [candidateLimit, setCandidateLimit] = useState<number>(10);
  const { running, progress, result, error, wsDisconnected, startBatch } = useBatchProgress();

  const handleStartBatch = () => {
    startBatch(candidateLimit);
  };

  const renderCandidateCard = ({ item }: { item: BatchCandidateResult }) => {
    const bestMatch = item.analysis?.best_match;

    return (
      <Card className="p-3 gap-2.5">
        <View className="flex-row items-start justify-between">
          <View className="flex-1 pr-2">
            <Text className="text-sm font-sans-bold text-text-primary">
              {item.candidate_name}
            </Text>
            <Text className="text-xs font-sans text-text-muted">
              Candidate ID #{item.candidate_id}
            </Text>
          </View>
          {bestMatch ? (
            <ScoreBadge
              score={bestMatch.overall_score}
              classification={bestMatch.classification}
            />
          ) : null}
        </View>

        {bestMatch ? (
          <View className="bg-background p-2.5 rounded border border-border gap-1">
            <View className="flex-row items-center justify-between">
              <Text className="text-[11px] font-sans-bold text-primary uppercase tracking-wider">
                Top Matched Vacancy
              </Text>
              {!!bestMatch.retrieval_source && (
                <Badge
                  label={
                    bestMatch.retrieval_source === 'both' || bestMatch.retrieval_source === 'hybrid'
                      ? 'Hybrid (Keyword + Vector)'
                      : bestMatch.retrieval_source === 'vector'
                        ? 'pgvector'
                        : 'Keyword'
                  }
                  tone={
                    bestMatch.retrieval_source === 'both' || bestMatch.retrieval_source === 'hybrid'
                      ? 'success'
                      : bestMatch.retrieval_source === 'vector'
                        ? 'info'
                        : 'neutral'
                      }
                />
              )}
            </View>
            <Text className="text-xs font-sans-bold text-text-primary">
              {bestMatch.job_title}
            </Text>
            <Text className="text-xs font-sans text-text-muted italic">
              "{bestMatch.ranking_reason}"
            </Text>
          </View>
        ) : (
          <Text className="text-xs font-sans text-text-faint italic">
            No suitable vacancy matches found.
          </Text>
        )}
      </Card>
    );
  };

  const renderHeader = () => (
    <View className="gap-3 pb-2">
      {/* Background execution persistence note */}
      <View className="bg-info/10 border border-info/30 rounded-md p-2.5 flex-row items-center gap-2">
        <Info size={16} color={COLORS.info} />
        <Text className="text-xs font-sans text-info flex-1">
          Batch candidate processing continues on the backend server if you navigate away from this screen.
        </Text>
      </View>

      {/* Limit Selector Card */}
      <Card className="gap-3">
        <Text className="text-xs font-sans-bold text-text-primary">
          Select Maximum Candidates to Process:
        </Text>
        <SegmentedControl
          options={BATCH_CANDIDATE_LIMITS.map((num) => ({
            value: num,
            label: String(num),
            accessibilityLabel: `Limit ${num}`,
          }))}
          value={candidateLimit}
          onChange={(val) => setCandidateLimit(val as number)}
          disabled={running}
        />

        <Button
          label={running ? 'Processing Batch Candidates...' : 'Start Batch Processing'}
          onPress={handleStartBatch}
          loading={running}
          disabled={running}
          size="md"
        />
      </Card>

      {/* Standard Error Banner */}
      {error ? <ErrorBanner title="Batch Processing Error" message={error} /> : null}

      {/* Live Progress Box */}
      {running && (
        <Card className="border-primary/40 gap-2 shadow-sm">
          <View className="flex-row justify-between items-center">
            <View className="flex-row items-center gap-1.5">
              <Radio size={14} color={COLORS.primary} />
              <Text className="text-[11px] font-sans-bold text-primary uppercase tracking-wider">
                Live Pipeline Progress
              </Text>
            </View>
            <ActivityIndicator size="small" color={COLORS.primary} />
          </View>

          <Text className="text-sm font-sans-semibold text-text-primary">
            {progress?.message || progress?.status || 'Processing candidates...'}
          </Text>

          {progress?.total && progress.total > 0 ? (
            <View className="w-full bg-border h-2 rounded-full overflow-hidden mt-1">
              <View
                className="bg-primary h-full rounded-full"
                style={{
                  width: `${Math.round(((progress.processed || 0) / progress.total) * 100)}%`,
                }}
              />
            </View>
          ) : null}

          {wsDisconnected && (
            <View className="bg-warning/10 border border-warning/30 rounded p-2 mt-1 flex-row items-center gap-1.5">
              <AlertTriangle size={14} color={COLORS.warning} />
              <Text className="text-[11px] font-sans text-warning flex-1">
                Live progress stream disconnected; batch job is still running on server...
              </Text>
            </View>
          )}
        </Card>
      )}

      {/* Success Notification */}
      {result && (
        <Card className="bg-success/10 border-success/30 flex-row items-center gap-1.5 p-3">
          <CheckCircle size={14} color={COLORS.success} />
          <Text className="text-xs font-sans-bold text-success flex-1">
            {result.message}
          </Text>
        </Card>
      )}

      {/* Results Header */}
      {result && (
        <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider pt-1">
          Batch Match Results ({result.matches?.length || 0})
        </Text>
      )}
    </View>
  );

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Batch Processing' }]} />

      {/* Sticky PageHeader */}
      <View className="px-3 py-2.5 bg-surface border-b border-border">
        <Text className="text-base font-sans-bold text-text-primary">Batch Candidate Matching</Text>
        <Text className="text-[11px] font-sans text-text-muted">
          Batch process un-evaluated active candidates against all active vacancies with live WebSocket progress.
        </Text>
      </View>

      {/* Primary FlatList Scroller */}
      <FlatList
        data={result?.matches || []}
        keyExtractor={(item, index) =>
          item?.candidate_id ? String(item.candidate_id) : `candidate-${index}`
        }
        renderItem={renderCandidateCard}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={
          !result && !running ? (
            <View className="mt-4">
              <EmptyState
                title="Ready to Process"
                subtitle="Select candidate limit and start batch processing"
              />
            </View>
          ) : result && (!result.matches || result.matches.length === 0) ? (
            <View className="mt-4">
              <EmptyState
                title="No Matches Found"
                subtitle="No candidates met the threshold criteria for active vacancies"
              />
            </View>
          ) : null
        }
        contentContainerStyle={{ padding: 12, gap: 10 }}
        showsVerticalScrollIndicator={false}
      />
    </SafeAreaView>
  );
}
