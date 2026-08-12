import React from 'react';
import { View, Text } from 'react-native';
import { Award, AlertTriangle, AlertCircle, CpuIcon, User, CheckCircle2, Sparkles, XCircle, Lightbulb } from 'lucide-react-native';
import { Card } from './Card';
import { Button } from './Button';
import { Badge } from './Badge';
import { VacancyMatchStatusBadge, VacancyFitScoreBreakdownCard, resolveVacancyFitScore } from './VacancyMatchStatusBadge';
import { ComponentScoreBar } from './ComponentScoreBar';
import { COLORS } from '@/constants/colors';
import { JobMatchScore } from '@/types/api';

export interface MatchAnalysisCardProps {
  bestMatch?: JobMatchScore | null;
  candidateName?: string | null;
  onReviewPress?: () => void;
  className?: string;
  testID?: string;
}

const getRetrievalBadge = (source?: string) => {
  if (!source) return null;
  const s = source.toLowerCase();
  if (s === 'both' || s === 'hybrid') return { label: 'Hybrid (Keyword + Vector)', tone: 'success' as const };
  if (s === 'vector' || s === 'pgvector') return { label: 'pgvector Match', tone: 'info' as const };
  if (s === 'keyword') return { label: 'Keyword Match', tone: 'neutral' as const };
  return { label: source, tone: 'neutral' as const };
};

export function MatchAnalysisCard({
  bestMatch,
  candidateName,
  onReviewPress,
  className = '',
  testID,
}: MatchAnalysisCardProps) {
  if (!bestMatch) {
    return (
      <Card testID={testID} className={`p-5 items-center justify-center gap-2 border-border/80 ${className}`}>
        <AlertCircle size={22} color={COLORS.textMuted} />
        <Text className="text-sm font-sans-bold text-text-primary">No Suitable Vacancy Match Found</Text>
        <Text className="text-xs font-sans text-text-muted text-center max-w-sm">
          None of the active vacancies met the minimum threshold criteria for this candidate's profile.
        </Text>
      </Card>
    );
  }

  const retrievalBadge = getRetrievalBadge(bestMatch.retrieval_source);
  const resolvedName = candidateName || (bestMatch as any).full_name || (bestMatch as any).candidate_name;

  const isDomainCapped = Boolean(
    bestMatch.domain_mismatch_capped ||
    (bestMatch.mandatory_failures || []).some((f: any) => f.requirement_id === 'req_domain_mismatch') ||
    (bestMatch.mandatory_fails || []).some((f: any) => (f.requirement && f.requirement.includes('Domain Mismatch')) || f.requirement === 'req_domain_mismatch')
  );

  const matchStatus = bestMatch.vacancy_match_status || (bestMatch as any).match_status || bestMatch.classification;
  const fitScore = resolveVacancyFitScore(bestMatch);

  return (
    <Card testID={testID} className={`border-primary/40 shadow-sm gap-3.5 ${className}`}>
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
            {isDomainCapped && (
              <Badge label="Cross-domain match — score capped" tone="warning" />
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
        <VacancyMatchStatusBadge
          status={matchStatus}
          score={fitScore}
        />
      </View>

      {/* Canonical Fit Score Breakdown if available */}
      {bestMatch.score_breakdown ? (
        <VacancyFitScoreBreakdownCard
          breakdown={bestMatch.score_breakdown}
          penalty={bestMatch.score_breakdown.hierarchy_mismatch_penalty}
          rejectionReason={bestMatch.domain_mismatch_reason || bestMatch.reason}
        />
      ) : null}

      {/* Cross-Domain Guard Explainability Banner */}
      {isDomainCapped && !bestMatch.score_breakdown && (
        <View className="bg-warning/10 border border-warning/30 rounded-md p-3 gap-1">
          <View className="flex-row items-center gap-1.5">
            <AlertTriangle size={14} color={COLORS.warning} />
            <Text className="text-xs font-sans-bold text-warning uppercase tracking-wider">
              Cross-domain match — score capped
            </Text>
          </View>
          <Text className="text-xs font-sans text-warning leading-4">
            {bestMatch.domain_mismatch_reason || "The candidate's primary background conflicts with the target vacancy department. Suitability score has been automatically capped to prevent false-positive matches."}
          </Text>
        </View>
      )}

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
        <View className="bg-info/10 border border-info/30 rounded-md p-3">
          <View className="flex-row items-center gap-1.5 mb-1">
            <Sparkles size={14} color={COLORS.info} />
            <Text className="text-xs font-sans-bold text-info">
              AI Reasoning & Synthesis:
            </Text>
          </View>
          <Text className="text-xs font-sans text-info leading-5">
            {bestMatch.llm_reason}
          </Text>
        </View>
      )}

      {/* Mandatory Failures & Missing Criteria */}
      {(() => {
        const rawFails: any[] = bestMatch.mandatory_fails || bestMatch.mandatory_failures || [];
        const failedReqs: any[] = (bestMatch.mandatory_requirements || []).filter((r: any) => r.status === 'FAILED');
        const missingCrit: string[] = bestMatch.missing_criteria || [];

        const failureList: Array<{ title: string; details: string }> = [];

        if (rawFails.length > 0) {
          rawFails.forEach((f: any) => {
            const title = typeof f === 'string' ? f : (f.requirement || f.description || f.requirement_id || 'Mandatory Requirement');
            const details = typeof f === 'string' ? '' : (f.details || f.reason || f.failure_reason || '');
            failureList.push({ title, details });
          });
        } else if (failedReqs.length > 0) {
          failedReqs.forEach((r: any) => {
            failureList.push({
              title: r.description || r.requirement_id || 'Mandatory Requirement',
              details: r.failure_reason || r.reason || '',
            });
          });
        } else if (missingCrit.length > 0) {
          missingCrit.forEach((mc: string) => {
            failureList.push({ title: 'Missing Criterion', details: mc });
          });
        }

        if (failureList.length === 0) return null;

        return (
          <View className="bg-danger/10 border border-danger/30 rounded-md p-3 gap-1.5">
            <View className="flex-row items-center gap-1.5 mb-1">
              <CpuIcon size={14} color={COLORS.danger} />
              <Text className="text-xs font-sans-bold text-danger">
                Mandatory Requirement Failures & Missing Criteria:
              </Text>
            </View>
            {failureList.map((fail, idx) => (
              <View key={idx} className="flex-row items-start gap-1">
                <Text className="text-xs font-sans-bold text-danger">•</Text>
                <Text className="text-xs font-sans-medium text-danger flex-1">
                  {fail.title}{fail.details ? `: ${fail.details}` : ''}
                </Text>
              </View>
            ))}
          </View>
        );
      })()}

      {/* Skills Analysis */}
      {(() => {
        const matched = bestMatch.matched_skills || [];
        const missing = bestMatch.missing_skills || [];
        const inferred = bestMatch.inferred_skills || [];

        if (matched.length === 0 && missing.length === 0 && inferred.length === 0) {
          return null;
        }

        return (
          <View className="gap-2 mt-1">
            {matched.length > 0 && (
              <View className="gap-1">
                <View className="flex-row items-center gap-1">
                  <CheckCircle2 size={12} color={COLORS.success} />
                  <Text className="text-xs font-sans-bold text-success">Matched Skills</Text>
                </View>
                <View className="flex-row flex-wrap gap-1.5">
                  {matched.map((s: string, i: number) => (
                    <View key={i} className="bg-success/10 border border-success/30 px-2 py-0.5 rounded-md">
                      <Text className="text-[10px] font-sans text-success">{s}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}
            
            {inferred.length > 0 && (
              <View className="gap-1">
                <View className="flex-row items-center gap-1">
                  <Sparkles size={12} color={COLORS.info} />
                  <Text className="text-xs font-sans-bold text-info">Inferred Skills</Text>
                </View>
                <View className="flex-row flex-wrap gap-1.5">
                  {inferred.map((s: string, i: number) => (
                    <View key={i} className="bg-info/10 border border-info/30 px-2 py-0.5 rounded-md">
                      <Text className="text-[10px] font-sans text-info">{s}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}

            {missing.length > 0 && (
              <View className="gap-1">
                <View className="flex-row items-center gap-1">
                  <XCircle size={12} color={COLORS.textMuted} />
                  <Text className="text-xs font-sans-bold text-text-muted">Missing Skills</Text>
                </View>
                <View className="flex-row flex-wrap gap-1.5">
                  {missing.map((s: string, i: number) => (
                    <View key={i} className="bg-surface border border-border px-2 py-0.5 rounded-md">
                      <Text className="text-[10px] font-sans text-text-muted">{s}</Text>
                    </View>
                  ))}
                </View>
              </View>
            )}
          </View>
        );
      })()}

      {/* Component Breakdown */}
      {!!bestMatch.component_scores && (
        <View className="pt-2 border-t border-border/50">
          <Text className="text-xs font-sans-bold text-text-muted mb-1">
            Sub-Score Breakdown:
          </Text>
          <ComponentScoreBar scores={bestMatch.component_scores} />
        </View>
      )}

      {/* Recommendation */}
      {!!bestMatch.recommendation && (
        <View className="bg-background p-2.5 rounded-md border border-border flex-row items-start gap-2">
          <Lightbulb size={14} color={COLORS.primary} className="mt-0.5" />
          <Text className="text-xs font-sans text-text-primary flex-1 leading-5">
            {bestMatch.recommendation}
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
