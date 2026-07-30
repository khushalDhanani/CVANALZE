import React from 'react';
import { View, Text } from 'react-native';
import { Award, AlertTriangle, CpuIcon, User } from 'lucide-react-native';
import { Card } from './Card';
import { Button } from './Button';
import { Badge } from './Badge';
import { ScoreBadge } from './ScoreBadge';
import { ComponentScoreBar } from './ComponentScoreBar';
import { COLORS } from '@/constants/colors';
import { JobMatchScore, MandatoryFailure } from '@/types/api';

interface MatchAnalysisCardProps {
  bestMatch: JobMatchScore | any;
  candidateName?: string | null;
  onReviewPress?: () => void;
}

const getRetrievalBadge = (source?: string) => {
  if (!source) return null;
  const s = source.toLowerCase();
  if (s === 'both' || s === 'hybrid') return { label: 'Hybrid (Keyword + Vector)', tone: 'success' as const };
  if (s === 'vector' || s === 'pgvector') return { label: 'pgvector Match', tone: 'info' as const };
  if (s === 'keyword') return { label: 'Keyword Match', tone: 'neutral' as const };
  return { label: source, tone: 'neutral' as const };
};

export function MatchAnalysisCard({ bestMatch, candidateName, onReviewPress }: MatchAnalysisCardProps) {
  if (!bestMatch) return null;
  const retrievalBadge = getRetrievalBadge(bestMatch.retrieval_source);
  const resolvedName = candidateName || bestMatch.full_name || bestMatch.candidate_name;

  return (
    <Card className="border-primary/40 shadow-sm gap-3">
      {!!resolvedName && (
        <View className="flex-row items-center gap-2 pb-2 border-b border-border/50">
          <View className="w-6 h-6 rounded-full bg-primary/10 items-center justify-center">
            <User size={14} color={COLORS.primary} />
          </View>
          <View className="flex-1">
            <Text className="text-xs font-sans-medium text-text-muted uppercase tracking-wider">Candidate</Text>
            <Text className="text-sm font-sans-bold text-text-primary">{resolvedName}</Text>
          </View>
        </View>
      )}
      <View className="flex-row justify-between items-start">
        <View className="flex-1 pr-2">
          <View className="flex-row items-center gap-2 mb-1 flex-wrap">
            <View className="flex-row items-center gap-1">
              <Award size={14} color={COLORS.primary} />
              <Text className="text-xs font-sans-bold text-primary uppercase tracking-wider">
                Best Matched Job
              </Text>
            </View>
            {retrievalBadge && (
              <Badge label={retrievalBadge.label} tone={retrievalBadge.tone} />
            )}
          </View>
          <Text className="text-lg font-sans-bold text-text-primary">
            {bestMatch.job_title}
          </Text>
          {!!bestMatch.department_name && (
            <Text className="text-xs font-sans-medium text-text-muted">
              Dept: {bestMatch.department_name}
            </Text>
          )}
        </View>
        <ScoreBadge
          score={bestMatch.overall_score || bestMatch.score || 0}
          classification={bestMatch.classification || 'LOW'}
        />
      </View>

      {/* Ranking reason */}
      {!!bestMatch.ranking_reason && (
        <View className="bg-background p-2.5 rounded-md border border-border">
          <Text className="text-xs font-sans text-text-muted italic">
            "{bestMatch.ranking_reason}"
          </Text>
        </View>
      )}

      {/* LLM Reason if available */}
      {!!bestMatch.llm_reason && (
        <Card className="bg-info/10 border-info/30 p-3">
          <View className="flex-row items-center gap-1.5 mb-1">
            <AlertTriangle size={14} color={COLORS.info} />
            <Text className="text-xs font-sans-bold text-info">
              LLM Reasoning & Synthesis:
            </Text>
          </View>
          <Text className="text-xs font-sans text-info">
            {bestMatch.llm_reason}
          </Text>
        </Card>
      )}

      {/* Mandatory Failures */}
      {bestMatch.mandatory_fails && bestMatch.mandatory_fails.length > 0 && (
        <Card className="bg-danger/10 border-danger/30 p-3">
          <View className="flex-row items-center gap-1.5 mb-1">
            <CpuIcon size={14} color={COLORS.danger} />
            <Text className="text-xs font-sans-bold text-danger">
              Mandatory Requirement Failures:
            </Text>
          </View>
          {bestMatch.mandatory_fails.map((fail: MandatoryFailure, idx: number) => (
            <Text key={idx} className="text-xs font-sans-medium text-danger">
              • {fail.requirement}: {fail.details}
            </Text>
          ))}
        </Card>
      )}

      {/* Component Breakdown */}
      {!!bestMatch.component_scores && (
        <View>
          <Text className="text-xs font-sans-bold text-text-muted mb-1">
            Sub-Score Breakdown:
          </Text>
          <ComponentScoreBar scores={bestMatch.component_scores} />
        </View>
      )}

      {/* Recommendation */}
      {!!bestMatch.recommendation && (
        <View className="bg-background p-2.5 rounded-md border border-border">
          <Text className="text-xs font-sans text-text-primary">
            💡 {bestMatch.recommendation}
          </Text>
        </View>
      )}

      {/* HR Feedback Trigger */}
      {onReviewPress && (
        <Button
          label="Submit HR Review & Correction"
          variant="secondary"
          onPress={onReviewPress}
          size="sm"
        />
      )}
    </Card>
  );
}
