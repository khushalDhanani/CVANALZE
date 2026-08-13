import React from 'react';
import { Text, View } from 'react-native';
import type { EnrichedJobEvaluation } from '@/types/api';
import { getVacancyEnrichmentPresentation } from '@/utils/vacancyEnrichment';
import { Badge } from './Badge';

interface VacancyEnrichmentPanelProps {
  match: Partial<EnrichedJobEvaluation>;
  showDecisionMetadata?: boolean;
}

export function VacancyEnrichmentPanel({ match, showDecisionMetadata = true }: VacancyEnrichmentPanelProps) {
  const { reasoning, recommendation, inferredSkills, qualityFlags, evidence, metadata } = getVacancyEnrichmentPresentation(match);

  if (!reasoning && !recommendation && inferredSkills.length === 0 && qualityFlags.length === 0 && evidence.length === 0 && metadata.length === 0) return null;

  return (
    <View className="gap-2 mt-1">
      {reasoning ? (
        <View className="p-2 border rounded bg-primary/5 border-primary/10">
          <Text className="mb-1 text-xs leading-4 text-text-primary font-sans-bold">AI Match Rationale</Text>
          <Text className="text-xs leading-4 text-text-primary">{reasoning}</Text>
        </View>
      ) : null}
      {showDecisionMetadata && recommendation ? (
        <View className="p-2 border rounded bg-background border-border">
          <Text className="mb-1 text-xs leading-4 text-text-primary font-sans-bold">Recommendation</Text>
          <Text className="text-xs leading-4 text-text-primary">{recommendation}</Text>
        </View>
      ) : null}
      {inferredSkills.length > 0 ? (
        <View className="gap-1">
          <Text className="text-[11px] font-sans-bold text-text-muted uppercase">Additional Skills Identified</Text>
          <View className="flex-row flex-wrap gap-1">{inferredSkills.map((skill, index) => <Badge key={`${skill}-${index}`} label={skill} tone="info" />)}</View>
        </View>
      ) : null}
      {showDecisionMetadata && metadata.length > 0 ? <Text className="text-[11px] leading-4 text-text-muted">{metadata.join(' • ')}</Text> : null}
      {showDecisionMetadata && qualityFlags.length > 0 ? (
        <View className="flex-row flex-wrap gap-1">{qualityFlags.map((flag, index) => <Badge key={`${flag}-${index}`} label={flag} tone="warning" />)}</View>
      ) : null}
      {evidence.length > 0 ? (
        <View className="gap-1 p-2 border rounded bg-background border-border">
          <Text className="text-[11px] font-sans-bold text-text-muted uppercase">Grounded Evidence</Text>
          {evidence.slice(0, 5).map(({ label, evidence: item }, index) => (
            <View key={`${label}-${index}`} className="gap-0.5">
              <Text className="text-[11px] font-sans-bold text-text-primary">{label}</Text>
              {item.cv_evidence ? <Text className="text-[11px] leading-4 text-text-primary">CV: {item.cv_evidence}</Text> : null}
              {item.vacancy_evidence ? <Text className="text-[11px] leading-4 text-text-muted">Vacancy: {item.vacancy_evidence}</Text> : null}
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}
