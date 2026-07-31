import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { Database, FileText, CheckCircle2, ChevronDown, ChevronUp, UserCheck, Sparkles, MessageSquare } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { matchService } from '@/services/matchService';
import { TrainingExample } from '@/types/api';
import { Card, Button, Badge, EmptyState } from '@/components/ui';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { COLORS } from '@/constants/colors';

export default function TrainingDataScreen() {
  const [examples, setExamples] = useState<TrainingExample[]>([]);
  const [count, setCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchTrainingData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await matchService.getTrainingData(100);
      setExamples(res.examples || []);
      setCount(res.count || 0);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch HR training data examples.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrainingData();
  }, []);

  const renderTrainingItem = ({ item, index }: { item: TrainingExample; index: number }) => {
    const isExpanded = expandedId === `${item.scan_id}-${index}`;
    const formattedTime = item.timestamp
      ? new Date(item.timestamp).toLocaleString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: 'numeric',
          minute: '2-digit',
        })
      : 'Recently';

    return (
      <Card className="mb-3 p-0 overflow-hidden">
        <Pressable
          onPress={() => setExpandedId(isExpanded ? null : `${item.scan_id}-${index}`)}
          className="p-3 bg-surface active:bg-background flex-row items-center justify-between"
        >
          <View className="flex-1 pr-2">
            <View className="flex-row items-center gap-2 mb-1 flex-wrap">
              <Text className="text-xs font-sans-bold text-primary">
                Scan #{item.scan_id}
              </Text>
              <Text className="text-[11px] font-sans text-text-muted">
                Job ID #{item.job_id}
              </Text>
              <Text className="text-[11px] font-sans text-text-faint">• {formattedTime}</Text>
            </View>

            <View className="flex-row items-center gap-3 mt-1 flex-wrap">
              <View className="flex-row items-center gap-1.5">
                <Text className="text-xs font-sans-medium text-text-muted">Rule Score:</Text>
                <ScoreBadge score={item.original_score} classification={item.original_classification} />
              </View>
              <Text className="text-xs font-sans text-text-faint">➜</Text>
              <View className="flex-row items-center gap-1.5">
                <Text className="text-xs font-sans-bold text-success">HR Corrected:</Text>
                <ScoreBadge score={item.hr_corrected_score} classification={item.hr_corrected_classification} />
              </View>
            </View>
          </View>

          {isExpanded ? (
            <ChevronUp size={18} color={COLORS.textMuted} />
          ) : (
            <ChevronDown size={18} color={COLORS.textMuted} />
          )}
        </Pressable>

        {isExpanded && (
          <View className="p-3 border-t border-border bg-background gap-3">
            {/* HR Feedback Notes */}
            {item.hr_feedback ? (
              <View className="bg-success/10 border border-success/30 p-2.5 rounded-md gap-1">
                <View className="flex-row items-center gap-1.5">
                  <MessageSquare size={13} color={COLORS.success} />
                  <Text className="text-xs font-sans-bold text-success">HR Correction Notes:</Text>
                </View>
                <Text className="text-xs font-sans text-text-primary">
                  "{item.hr_feedback}"
                </Text>
              </View>
            ) : null}

            {/* Original LLM Reasoning */}
            {item.original_llm_analysis?.llm_reason ? (
              <View className="gap-1">
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                  Original LLM Reasoning Synthesis:
                </Text>
                <Text className="text-xs font-sans text-text-primary bg-surface p-2.5 rounded border border-border">
                  {item.original_llm_analysis.llm_reason}
                </Text>
              </View>
            ) : null}

            {/* Inferred Skills */}
            {item.original_llm_analysis?.inferred_skills?.length > 0 && (
              <View className="gap-1">
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                  Inferred Skills:
                </Text>
                <View className="flex-row flex-wrap gap-1.5">
                  {item.original_llm_analysis.inferred_skills.map((skill, sIdx) => (
                    <Badge key={sIdx} label={skill} tone="neutral" />
                  ))}
                </View>
              </View>
            )}

            {/* Extracted CV Text snippet */}
            {item.cv_text ? (
              <View className="gap-1">
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                  Extracted CV Text Snippet:
                </Text>
                <Text className="text-[11px] font-mono text-text-primary bg-surface p-2.5 rounded border border-border" numberOfLines={6}>
                  {item.cv_text}
                </Text>
              </View>
            ) : null}
          </View>
        )}
      </Card>
    );
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      {/* Sticky Header */}
      <View className="flex-row items-center justify-between px-3 py-2 bg-surface border-b border-border">
        <View className="flex-row items-center gap-2">
          <Database size={18} color={COLORS.primary} />
          <View>
            <Text className="text-base font-sans-bold text-text-primary">HR Training Data Manager</Text>
            <Text className="text-[11px] font-sans text-text-muted">
              {count} collected HR correction examples for fine-tuning & model alignment
            </Text>
          </View>
        </View>
        <Button
          label="Refresh"
          variant="secondary"
          size="sm"
          onPress={fetchTrainingData}
          disabled={loading}
        />
      </View>

      <View className="flex-1 px-3 pt-3">
        {loading ? (
          <View className="flex-1 justify-center items-center py-16">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">
              Loading HR feedback training dataset...
            </Text>
          </View>
        ) : error ? (
          <Card className="bg-danger/10 border-danger/30 p-4">
            <Text className="text-xs font-sans-semibold text-danger">{error}</Text>
            <View className="mt-2 self-start">
              <Button label="Try Refreshing" variant="ghost" onPress={fetchTrainingData} />
            </View>
          </Card>
        ) : (
          <FlatList
            data={examples}
            keyExtractor={(item, index) => `${item.scan_id}-${index}`}
            renderItem={renderTrainingItem}
            contentContainerStyle={{ paddingBottom: 24 }}
            onRefresh={fetchTrainingData}
            refreshing={loading}
            ListEmptyComponent={
              <EmptyState
                title="No Training Data Collected Yet"
                subtitle="Submit HR reviews on candidate profiles to build fine-tuning dataset examples."
              />
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}
