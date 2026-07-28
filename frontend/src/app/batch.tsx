import React, { useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { useBatchProgress } from '@/hooks/useBatchProgress';
import { BatchCandidateResult } from '@/types/api';
import { Card, Button, DenseRow } from '@/components/ui';

export default function BatchScreen() {
  const [candidateLimit, setCandidateLimit] = useState<number>(10);
  const { running, progress, result, error, startBatch } = useBatchProgress();

  const handleStartBatch = () => {
    startBatch(candidateLimit);
  };

  const renderCandidateCard = ({ item }: { item: BatchCandidateResult }) => {
    const bestMatch = item.analysis?.best_match;

    return (
      <Card className="mb-3 p-0 overflow-hidden">
        <DenseRow
          title={item.candidate_name}
          subtitle={`Candidate ID #${item.candidate_id}`}
          trailing={
            bestMatch ? (
              <ScoreBadge
                score={bestMatch.overall_score}
                classification={bestMatch.classification}
              />
            ) : undefined
          }
        />

        <View className="px-3 pb-3">
          {bestMatch ? (
            <View className="bg-background p-3 rounded-md border border-border mt-2">
              <Text className="text-[10px] font-sans-bold text-primary uppercase tracking-wider mb-0.5">
                Top Matched Vacancy
              </Text>
              <Text className="text-sm font-sans-bold text-text-primary mb-1">
                {bestMatch.job_title}
              </Text>
              <Text className="text-xs font-sans text-text-muted italic">
                "{bestMatch.ranking_reason}"
              </Text>
            </View>
          ) : (
            <Text className="text-xs font-sans text-text-faint italic mt-2">
              No suitable vacancy matches found.
            </Text>
          )}
        </View>
      </Card>
    );
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      <ScrollView className="flex-1 px-3 py-4">
        {/* Header */}
        <View className="mb-4">
          <Text className="text-xl font-sans-bold text-text-primary mb-1">
            Batch Candidate Matching
          </Text>
          <Text className="text-xs font-sans text-text-muted">
            Batch process un-evaluated active candidates against all active vacancies with live WebSocket progress.
          </Text>
        </View>

        {/* Limit Selector */}
        <Card className="mb-4 gap-3">
          <Text className="text-xs font-sans-bold text-text-primary">
            Select Maximum Candidates to Process:
          </Text>
          <View className="flex-row gap-2">
            {[5, 10, 20, 30].map((num) => (
              <Pressable
                key={num}
                onPress={() => setCandidateLimit(num)}
                disabled={running}
                hitSlop={8}
                className={`flex-1 py-2.5 rounded-md border items-center ${
                  candidateLimit === num
                    ? 'bg-primary border-primary active:bg-primary-dark'
                    : 'bg-surface border-border active:bg-background'
                }`}
              >
                <Text
                  className={`text-xs font-sans-bold ${
                    candidateLimit === num ? 'text-text-inverse' : 'text-text-primary'
                  }`}
                >
                  {num}
                </Text>
              </Pressable>
            ))}
          </View>

          <Button
            label={running ? 'Processing Batch Candidates...' : 'Start Batch Processing'}
            onPress={handleStartBatch}
            loading={running}
            disabled={running}
            size="md"
          />
        </Card>

        {/* Error Notice */}
        {error && (
          <Card className="bg-danger/10 border-danger/30 mb-4 p-3">
            <Text className="text-xs font-sans-medium text-danger">{error}</Text>
          </Card>
        )}

        {/* Live Progress Box */}
        {running && (
          <Card className="border-primary/40 mb-4 gap-2 shadow-sm">
            <View className="flex-row justify-between items-center">
              <View className="flex-row items-center gap-1.5">
                <Feather name="radio" size={14} color="#4F46E5" />
                <Text className="text-xs font-sans-bold text-primary uppercase tracking-wider">
                  Live Pipeline Progress
                </Text>
              </View>
              <ActivityIndicator size="small" color="#4F46E5" />
            </View>

            <Text className="text-sm font-sans-semibold text-text-primary">
              {progress?.message || progress?.status || 'Processing candidates...'}
            </Text>

            {progress?.total && progress.total > 0 && (
              <View className="w-full bg-border h-2 rounded-full overflow-hidden mt-1">
                <View
                  className="bg-primary h-full rounded-full"
                  style={{
                    width: `${Math.round(
                      ((progress.processed || 0) / progress.total) * 100
                    )}%`,
                  }}
                />
              </View>
            )}
          </Card>
        )}

        {/* Results Section */}
        {result && (
          <View className="mb-6 gap-3">
            <Card className="bg-success/10 border-success/30 flex-row items-center gap-1.5 p-3">
              <Feather name="check-circle" size={14} color="#16A34A" />
              <Text className="text-xs font-sans-bold text-success">
                {result.message}
              </Text>
            </Card>

            <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider">
              Batch Match Results ({result.matches?.length || 0})
            </Text>

            <FlatList
              data={result.matches}
              keyExtractor={(item, index) => (item?.candidate_id ? String(item.candidate_id) : `candidate-${index}`)}
              renderItem={renderCandidateCard}
              scrollEnabled={false}
            />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
