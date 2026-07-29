import React from 'react';
import { View, Text } from 'react-native';
import { Award, AlertTriangle, CpuIcon } from 'lucide-react-native';
import { Card } from './Card';
import { Button } from './Button';
import { ScoreBadge } from './ScoreBadge';
import { ComponentScoreBar } from './ComponentScoreBar';
import { COLORS } from '@/constants/colors';
import { JobMatchScore, MandatoryFailure } from '@/types/api';

interface MatchAnalysisCardProps {
  bestMatch: JobMatchScore | any;
  onReviewPress?: () => void;
}

export function MatchAnalysisCard({ bestMatch, onReviewPress }: MatchAnalysisCardProps) {
  if (!bestMatch) return null;
  return (
    <Card className="border-primary/40 shadow-sm gap-3">
      <View className="flex-row justify-between items-start">
        <View className="flex-1 pr-2">
          <View className="flex-row items-center gap-1 mb-1">
            <Award size={14} color={COLORS.primary} />
            <Text className="text-xs font-sans-bold text-primary uppercase tracking-wider">
              Best Matched Job
            </Text>
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
