import React from 'react';
import { View, Text, ActivityIndicator } from 'react-native';
import {
  CheckCircle2,
  Sparkles,
  Slash,
  Briefcase,
  HelpCircle,
  Clock,
  XCircle,
  AlertTriangle,
  Layers,
  ShieldAlert,
} from 'lucide-react-native';
import { Badge, Tone } from './Badge';
import { Card } from './Card';
import { COLORS } from '@/constants/colors';
import { CanonicalVacancyMatchStatus, VacancyFitScoreBreakdown } from '@/types/api';

export interface CanonicalStatusMeta {
  status: CanonicalVacancyMatchStatus;
  label: string;
  tone: Tone;
  icon: (color: string, size?: number) => React.ReactNode;
  description: string;
  isProcessing: boolean;
  isError: boolean;
}

/**
 * Normalizes any backend or legacy classification string into a CanonicalVacancyMatchStatus.
 * Backend `vacancy_match_status` is the single authoritative source of truth.
 */
export function normalizeCanonicalMatchStatus(
  rawStatus?: string | null
): CanonicalVacancyMatchStatus {
  if (!rawStatus) return 'NO_STRONG_MATCH';

  const s = String(rawStatus).trim().toUpperCase();

  if (s === 'MATCHED' || s === 'HIGH' || s === 'STRONG' || s === 'HIGHLY RECOMMENDED' || s === 'HIRE') {
    return 'MATCHED';
  }
  if (s === 'POTENTIAL_MATCH' || s === 'MEDIUM' || s === 'POTENTIAL FIT' || s === 'RECOMMENDED' || s === 'CONSIDER') {
    return 'POTENTIAL_MATCH';
  }
  if (s === 'NO_ACTIVE_VACANCIES') {
    return 'NO_ACTIVE_VACANCIES';
  }
  if (s === 'ANALYSIS_NOT_AVAILABLE' || s === 'ANALYSIS UNAVAILABLE' || s === 'N/A') {
    return 'ANALYSIS_NOT_AVAILABLE';
  }
  if (s === 'PROCESSING' || s === 'IN_PROGRESS' || s === 'ANALYZING') {
    return 'PROCESSING';
  }
  if (s === 'FAILED' || s === 'ERROR' || s === 'FAILURE' || s === 'REJECT') {
    return 'FAILED';
  }
  if (s === 'NO_STRONG_MATCH' || s === 'LOW' || s === 'NO_STRONG_VACANCY_MATCH' || s === 'NEEDS FURTHER REVIEW') {
    return 'NO_STRONG_MATCH';
  }

  return 'NO_STRONG_MATCH';
}

/**
 * Resolves standard styling, tone, icon, and human-readable HR copy for a canonical status.
 */
export function getCanonicalMatchStatusMeta(
  rawStatus?: string | null,
  score?: number | null
): CanonicalStatusMeta {
  const status = normalizeCanonicalMatchStatus(rawStatus);

  switch (status) {
    case 'MATCHED':
      return {
        status,
        label: 'MATCHED',
        tone: 'success',
        icon: (c, s = 12) => <CheckCircle2 size={s} color={c} />,
        description: 'Candidate strongly fits active vacancy requirements and hierarchy.',
        isProcessing: false,
        isError: false,
      };

    case 'POTENTIAL_MATCH':
      return {
        status,
        label: 'POTENTIAL MATCH',
        tone: 'warning',
        icon: (c, s = 12) => <Sparkles size={s} color={c} />,
        description: 'Candidate shows potential alignment with vacancy; manual review suggested.',
        isProcessing: false,
        isError: false,
      };

    case 'NO_STRONG_MATCH':
      return {
        status,
        label: 'NO STRONG MATCH',
        tone: 'neutral',
        icon: (c, s = 12) => <Slash size={s} color={c} />,
        description: 'Candidate analysis succeeded, active vacancies evaluated, but none passed fit criteria.',
        isProcessing: false,
        isError: false,
      };

    case 'NO_ACTIVE_VACANCIES':
      return {
        status,
        label: 'NO ACTIVE VACANCIES',
        tone: 'neutral',
        icon: (c, s = 12) => <Briefcase size={s} color={c} />,
        description: 'Analysis completed, but no active job openings are available in the system for evaluation.',
        isProcessing: false,
        isError: false,
      };

    case 'ANALYSIS_NOT_AVAILABLE':
      return {
        status,
        label: 'ANALYSIS UNAVAILABLE',
        tone: 'danger',
        icon: (c, s = 12) => <HelpCircle size={s} color={c} />,
        description: 'Candidate record not found or analysis payload is missing.',
        isProcessing: false,
        isError: true,
      };

    case 'PROCESSING':
      return {
        status,
        label: 'PROCESSING',
        tone: 'info',
        icon: (c, s = 12) => <Clock size={s} color={c} />,
        description: 'Candidate analysis is currently running in the background.',
        isProcessing: true,
        isError: false,
      };

    case 'FAILED':
      return {
        status,
        label: 'ANALYSIS FAILED',
        tone: 'danger',
        icon: (c, s = 12) => <XCircle size={s} color={c} />,
        description: 'Candidate processing encountered an error during evaluation.',
        isProcessing: false,
        isError: true,
      };
  }
}

interface VacancyMatchStatusBadgeProps {
  status?: string | null;
  score?: number | null;
  size?: 'sm' | 'md' | 'lg';
  showScore?: boolean;
  showIcon?: boolean;
}

export function VacancyMatchStatusBadge({
  status,
  score,
  size = 'md',
  showScore = true,
  showIcon = true,
}: VacancyMatchStatusBadgeProps) {
  const meta = getCanonicalMatchStatusMeta(status, score);

  let labelText = meta.label;
  if (showScore && score != null && !meta.isProcessing && !meta.isError && meta.status !== 'NO_ACTIVE_VACANCIES') {
    const rounded = Math.round(score * 10) / 10;
    labelText = `${rounded}% • ${meta.label}`;
  }

  const iconColor =
    meta.tone === 'success'
      ? COLORS.success
      : meta.tone === 'warning'
      ? COLORS.warning
      : meta.tone === 'danger'
      ? COLORS.danger
      : meta.tone === 'info'
      ? COLORS.info
      : COLORS.textMuted;

  return (
    <View className="flex-row items-center gap-1">
      {meta.isProcessing ? (
        <ActivityIndicator size="small" color={COLORS.info} style={{ marginRight: 2 }} />
      ) : null}
      <Badge
        label={labelText}
        tone={meta.tone}
      />
    </View>
  );
}

interface ScoreBreakdownCardProps {
  breakdown?: VacancyFitScoreBreakdown | null;
  penalty?: number | null;
  reasons?: string[] | null;
  rejectionReason?: string | null;
}

export function VacancyFitScoreBreakdownCard({
  breakdown,
  penalty,
  reasons,
  rejectionReason,
}: ScoreBreakdownCardProps) {
  if (!breakdown) return null;

  const penaltyVal = penalty || breakdown.hierarchy_mismatch_penalty || 0;
  const isValidHierarchy = breakdown.is_hierarchy_valid !== false;

  return (
    <Card className="p-3 border-border/80 bg-background/50 gap-2.5">
      <View className="flex-row items-center justify-between border-b border-border/60 pb-1.5">
        <View className="flex-row items-center gap-1.5">
          <Layers size={13} color={COLORS.primary} />
          <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">
            Canonical Fit Breakdown
          </Text>
        </View>
        <Text className="text-xs font-sans-bold text-primary">
          Overall Fit: {Math.round(breakdown.overall_fit_score * 10) / 10}%
        </Text>
      </View>

      {/* 5-Dimension Grid */}
      <View className="flex-row flex-wrap gap-2">
        <View className="flex-1 min-w-[90px] bg-surface p-1.5 rounded border border-border/40">
          <Text className="text-[9px] font-sans text-text-muted">Hierarchy (25%)</Text>
          <Text className="text-xs font-sans-bold text-text-primary">{breakdown.hierarchy_score}%</Text>
        </View>
        <View className="flex-1 min-w-[90px] bg-surface p-1.5 rounded border border-border/40">
          <Text className="text-[9px] font-sans text-text-muted">Role / Title (20%)</Text>
          <Text className="text-xs font-sans-bold text-text-primary">{breakdown.designation_role_score}%</Text>
        </View>
        <View className="flex-1 min-w-[90px] bg-surface p-1.5 rounded border border-border/40">
          <Text className="text-[9px] font-sans text-text-muted">Skills (25%)</Text>
          <Text className="text-xs font-sans-bold text-text-primary">{breakdown.skills_score}%</Text>
        </View>
        <View className="flex-1 min-w-[90px] bg-surface p-1.5 rounded border border-border/40">
          <Text className="text-[9px] font-sans text-text-muted">Experience (15%)</Text>
          <Text className="text-xs font-sans-bold text-text-primary">{breakdown.experience_score}%</Text>
        </View>
        <View className="flex-1 min-w-[90px] bg-surface p-1.5 rounded border border-border/40">
          <Text className="text-[9px] font-sans text-text-muted">Semantic (15%)</Text>
          <Text className="text-xs font-sans-bold text-text-primary">{breakdown.semantic_similarity_score}%</Text>
        </View>
      </View>

      {/* Hierarchy Mismatch & Rejection Penalty Warning */}
      {(!isValidHierarchy || penaltyVal > 0) && (
        <View className="bg-danger/10 border border-danger/30 rounded p-2 gap-1 mt-1">
          <View className="flex-row items-center gap-1.5">
            <ShieldAlert size={12} color={COLORS.danger} />
            <Text className="text-[10px] font-sans-bold text-danger uppercase tracking-wider">
              Hierarchy Mismatch Penalty (-{penaltyVal} pts)
            </Text>
          </View>
          <Text className="text-[11px] font-sans text-danger/90 leading-4">
            Candidate department or organizational hierarchy does not align with the target vacancy. Score has been penalized to prevent cross-domain mismatch.
          </Text>
        </View>
      )}

      {/* Rejection Reasons */}
      {rejectionReason && (
        <View className="bg-warning/10 border border-warning/30 rounded p-2 gap-1 mt-0.5">
          <View className="flex-row items-center gap-1.5">
            <AlertTriangle size={12} color={COLORS.warning} />
            <Text className="text-[10px] font-sans-bold text-warning uppercase tracking-wider">
              Rejection Reason
            </Text>
          </View>
          <Text className="text-[11px] font-sans text-warning/90 leading-4">
            {rejectionReason}
          </Text>
        </View>
      )}

      {/* Additional specific constraint failures */}
      {reasons && reasons.length > 0 && (
        <View className="gap-0.5 mt-0.5">
          {reasons.map((r, i) => (
            <Text key={i} className="text-[10px] font-sans text-text-muted leading-4">
              • {r}
            </Text>
          ))}
        </View>
      )}
    </Card>
  );
}
