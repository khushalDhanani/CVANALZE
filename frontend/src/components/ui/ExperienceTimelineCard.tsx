import React, { useState } from 'react';
import { View, Text, Pressable } from 'react-native';
import { Briefcase, AlertTriangle, Clock, CheckCircle2, Info, Calendar, ShieldAlert, ChevronDown, ChevronUp, Layers, GitCommit, ArrowRight } from 'lucide-react-native';
import { Card } from './Card';
import { Badge } from './Badge';
import { COLORS } from '@/constants/colors';
import {
  CanonicalJobItem,
  ChildAssignmentItem,
  ConcurrentRoleClusterItem,
  ExperienceGapAnalysisData,
  ExperienceGapItem,
  ExperienceTimelineNodeItem,
  ExperienceTimelineSummaryItem,
  TimelineEventItem,
} from '@/types/api';

export type {
  CanonicalJobItem,
  ChildAssignmentItem,
  ConcurrentRoleClusterItem,
  ExperienceGapAnalysisData,
  ExperienceGapItem,
  ExperienceTimelineNodeItem,
  ExperienceTimelineSummaryItem,
  TimelineEventItem,
};

interface ExperienceTimelineCardProps {
  analysis?: ExperienceGapAnalysisData | any | null;
  experienceAssessment?: string | null;
  totalExperienceYears?: number | null;
  candidateData?: any | null;
}

export const ExperienceTimelineCard: React.FC<ExperienceTimelineCardProps> = ({
  analysis,
  experienceAssessment,
  totalExperienceYears,
  candidateData,
}) => {
  const [showUndated, setShowUndated] = useState(false);

  if (!analysis && !experienceAssessment && !candidateData) return null;

  const summary = analysis?.summary;
  const events = analysis?.timeline_events || [];
  const undated = analysis?.undated_nodes || [];
  const canonicalJobs = analysis?.canonical_jobs || [];
  const hrIndicators = analysis?.hr_review_indicators || [];
  const hrObs = summary?.hr_observations || [];

  const rawState =
    candidateData?.experience_state ||
    candidateData?.experience_summary?.experience_state ||
    candidateData?.validation_status ||
    summary?.validation_status;

  const resolveCanonicalExperienceYears = (): number | null => {
    if (typeof totalExperienceYears === 'number' && !isNaN(totalExperienceYears)) {
      return totalExperienceYears;
    }

    const sources = [candidateData, analysis];
    for (const src of sources) {
      if (!src || typeof src !== 'object') continue;

      if (typeof src.experience_years === 'number' && !isNaN(src.experience_years)) {
        return src.experience_years;
      }
      if (typeof src.total_experience_years === 'number' && !isNaN(src.total_experience_years)) {
        return src.total_experience_years;
      }
      if (typeof src.authoritative_years === 'number' && !isNaN(src.authoritative_years)) {
        return src.authoritative_years;
      }

      const expSum = src.experience_summary;
      if (expSum && typeof expSum === 'object') {
        if (typeof expSum.authoritative_years === 'number' && !isNaN(expSum.authoritative_years)) {
          return expSum.authoritative_years;
        }
        if (typeof expSum.experience_years === 'number' && !isNaN(expSum.experience_years)) {
          return expSum.experience_years;
        }
        if (typeof expSum.stated_years === 'number' && !isNaN(expSum.stated_years)) {
          return expSum.stated_years;
        }
      }

      const qMetrics = src.quality_metrics;
      if (qMetrics && typeof qMetrics === 'object' && typeof qMetrics.experience_years === 'number' && !isNaN(qMetrics.experience_years)) {
        return qMetrics.experience_years;
      }
    }

    if (typeof summary?.total_verified_years === 'number' && !isNaN(summary.total_verified_years)) {
      return summary.total_verified_years;
    }

    return null;
  };

  const canonicalYears = resolveCanonicalExperienceYears();

  const experienceState =
    rawState ||
    (canonicalYears !== null && canonicalYears > 0 ? 'CALCULATED' : (canonicalYears === 0 ? 'ZERO_CONFIRMED' : 'UNKNOWN'));

  const formatDisplayExperience = (years: number | null): string => {
    const rawGross =
      candidateData?.gross_display ||
      candidateData?.experience_summary?.gross_display ||
      summary?.gross_display;

    if (rawGross && rawGross.trim().length > 0) {
      return rawGross;
    }

    if (experienceState === 'UNKNOWN') {
      return 'Experience Present (Dates Unparseable)';
    }

    if (years === null || years === undefined) {
      return 'N/A';
    }

    if (years === 0 || experienceState === 'ZERO_CONFIRMED') {
      return '0 years 0 months';
    }

    const totalMonths = Math.round(years * 12);
    const yearsPart = Math.floor(totalMonths / 12);
    const monthsPart = totalMonths % 12;
    return `${yearsPart} year${yearsPart !== 1 ? 's' : ''} ${monthsPart} month${monthsPart !== 1 ? 's' : ''}`;
  };

  const experienceDisplayText = formatDisplayExperience(canonicalYears);


  const formatEmpType = (type: string) => {
    if (!type) return 'Full-Time';
    switch (type.toLowerCase()) {
      case 'full_time':
        return 'Full-Time';
      case 'part_time':
        return 'Part-Time';
      case 'contract':
        return 'Contract';
      case 'freelance':
        return 'Freelance';
      case 'internship':
        return 'Internship';
      case 'consulting':
        return 'Consulting';
      case 'self_employed':
        return 'Self-Employed';
      default:
        return type.replace('_', ' ').toUpperCase();
    }
  };

  const formatAssignmentType = (type: string) => {
    switch (type.toUpperCase()) {
      case 'DEPUTATION':
        return 'Deputation';
      case 'PROMOTION':
        return 'Promotion';
      case 'TRANSFER':
        return 'Internal Transfer';
      case 'INTERNAL_ASSIGNMENT':
        return 'Internal Assignment';
      case 'SUB_ROLE':
        return 'Sub-Role';
      default:
        return type.replace('_', ' ');
    }
  };

  const getGapStyling = (gap: ExperienceGapItem) => {
    const status = gap.coverage_status;
    const dur = gap.duration_months;

    if (status === 'UNEXPLAINED' && dur >= 3.0) {
      return {
        cardClass: 'bg-danger/10 border-l-4 border-l-danger border-danger/30',
        iconColor: COLORS.danger,
        badgeLabel: `Unexplained Gap (${dur} mo)`,
        badgeTone: 'danger' as const,
      };
    }
    if (status === 'UNEXPLAINED' || status === 'TIMELINE_UNCERTAINTY') {
      return {
        cardClass: 'bg-warning/10 border-l-4 border-l-warning border-warning/30',
        iconColor: COLORS.warning,
        badgeLabel: status === 'TIMELINE_UNCERTAINTY' ? 'Timeline Uncertain' : `Short Gap (${dur} mo)`,
        badgeTone: 'warning' as const,
      };
    }
    if (status === 'EDUCATION_COVERED') {
      return {
        cardClass: 'bg-info/10 border-l-4 border-l-info border-info/30',
        iconColor: COLORS.info,
        badgeLabel: 'Education Period',
        badgeTone: 'info' as const,
      };
    }
    if (status === 'FREELANCE_COVERED' || status === 'CONTRACT_COVERED') {
      return {
        cardClass: 'bg-success/10 border-l-4 border-l-success border-success/30',
        iconColor: COLORS.success,
        badgeLabel: status === 'FREELANCE_COVERED' ? 'Covered by Freelance' : 'Covered by Contract',
        badgeTone: 'success' as const,
      };
    }
    return {
      cardClass: 'bg-background border-l-4 border-l-border border-border',
      iconColor: COLORS.textMuted,
      badgeLabel: 'Career Transition',
      badgeTone: 'neutral' as const,
    };
  };

  const renderChildAssignment = (asg: ChildAssignmentItem, idx?: number) => (
    <View key={asg.assignment_id || `asg-${idx}`} className="p-2 bg-background/80 border border-border/60 rounded my-1 pl-3 border-l-2 border-l-info">
      <View className="flex-row justify-between items-center mb-1">
        <View className="flex-row items-center gap-1 flex-1 pr-2">
          <GitCommit size={11} color={COLORS.info} />
          <Text className="text-[11px] font-sans-bold text-text-primary">
            {asg.title_or_subrole}
          </Text>
        </View>
        <Badge label={formatAssignmentType(asg.assignment_type)} tone="info" />
      </View>
      <Text className="text-[10px] font-sans text-text-muted">
        {asg.start_date || 'N/A'} → {asg.is_current ? 'Present' : asg.end_date || 'N/A'}
      </Text>
      {asg.details && asg.details.length > 0 && (
        <View className="mt-1 gap-0.5">
          {asg.details.slice(0, 2).map((d, idx) => (
            <Text key={idx} className="text-[10px] font-sans text-text-muted leading-3" numberOfLines={2}>
              • {d}
            </Text>
          ))}
        </View>
      )}
    </View>
  );

  const renderRoleNode = (node: ExperienceTimelineNodeItem, isNested = false, overrideKey?: string | number) => {
    // Find canonical job matching this node if available to display nested child assignments
    const canonJob = canonicalJobs.find((cj: CanonicalJobItem) => cj.job_id === node.record_id || cj.parent_company === node.company);
    const childAssignments = canonJob?.child_assignments || [];

    return (
      <View
        key={overrideKey || node.record_id}
        className={`p-2.5 rounded border ${
          isNested ? 'bg-background/80 border-border/60 my-1' : 'bg-background border-border my-1.5'
        }`}
      >
        <View className="flex-row justify-between items-center mb-1">
          <View className="flex-row items-center gap-1.5 flex-1 pr-2">
            <Briefcase size={12} color={COLORS.info} />
            <Text className="text-xs font-sans-bold text-text-primary leading-4">
              {node.job_title}
            </Text>
          </View>
          <Badge label={formatEmpType(node.employment_type)} tone="neutral" />
        </View>

        <Text className="text-xs font-sans text-text-muted">
          {node.company} • {node.start_date || 'N/A'} → {node.is_current ? 'Present' : node.end_date || 'N/A'}
          {node.duration_months > 0 ? ` (${node.duration_months} mo)` : ''}
        </Text>

        {node.responsibilities && node.responsibilities.length > 0 && (
          <View className="mt-1 pt-1 border-t border-border/40 gap-0.5">
            {node.responsibilities.slice(0, 2).map((resp, idx) => (
              <Text key={idx} className="text-[11px] font-sans text-text-muted leading-3.5" numberOfLines={2}>
                • {resp}
              </Text>
            ))}
          </View>
        )}

        {/* Render nested child assignments (Deputation / Promotion / Sub-role) if present */}
        {childAssignments.length > 0 && (
          <View className="mt-2 pt-1.5 border-t border-border/40 gap-1">
            <Text className="text-[10px] font-sans-bold text-text-muted uppercase">
              Internal Assignments & Sub-Roles ({childAssignments.length})
            </Text>
            {childAssignments.map((asg: any, idx: number) => renderChildAssignment(asg, idx))}
          </View>
        )}
      </View>
    );
  };

  const renderCanonicalJob = (cj: CanonicalJobItem, idx?: number) => (
    <View key={cj.job_id || `cj-${idx}`} className="p-2.5 bg-background border border-border rounded my-1.5">
      <View className="flex-row justify-between items-center mb-1">
        <View className="flex-row items-center gap-1.5 flex-1 pr-2">
          <Briefcase size={12} color={COLORS.info} />
          <Text className="text-xs font-sans-bold text-text-primary leading-4">
            {cj.primary_title}
          </Text>
        </View>
        <Badge label={formatEmpType(cj.employment_type)} tone="neutral" />
      </View>

      <Text className="text-xs font-sans text-text-muted">
        {cj.parent_company} • {cj.start_date || 'N/A'} → {cj.is_current ? 'Present' : cj.end_date || 'N/A'}
        {cj.duration_months > 0 ? ` (${cj.duration_months} mo)` : ''}
      </Text>

      {cj.responsibilities && cj.responsibilities.length > 0 && (
        <View className="mt-1 pt-1 border-t border-border/40 gap-0.5">
          {cj.responsibilities.slice(0, 2).map((resp, idx) => (
            <Text key={idx} className="text-[11px] font-sans text-text-muted leading-3.5" numberOfLines={2}>
              • {resp}
            </Text>
          ))}
        </View>
      )}

      {cj.child_assignments && cj.child_assignments.length > 0 && (
        <View className="mt-2 pt-1.5 border-t border-border/40 gap-1">
          <Text className="text-[10px] font-sans-bold text-text-muted uppercase">
            Internal Assignments & Sub-Roles ({cj.child_assignments.length})
          </Text>
          {cj.child_assignments.map((asg, idx) => renderChildAssignment(asg, idx))}
        </View>
      )}
    </View>
  );

  return (
    <Card className="p-3 border-border shadow-none gap-3">
      {/* Header */}
      <View className="flex-row justify-between items-center pb-2 border-b border-border">
        <View className="flex-row items-center gap-1.5">
          <Clock size={14} color={COLORS.info} />
          <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">
            Experience Timeline & Gaps
          </Text>
        </View>
        <Badge
          label={
            summary?.has_current_employment
              ? 'Currently Employed'
              : (summary?.unexplained_gaps_count || 0) > 0
              ? 'Employment Hiatus Detected'
              : 'Timeline Complete'
          }
          tone={
            summary?.has_current_employment
              ? 'info'
              : (summary?.unexplained_gaps_count || 0) > 0
              ? 'warning'
              : 'neutral'
          }
        />
      </View>

      {/* Assessment Banner */}
      {experienceAssessment ? (
        <View className="bg-info/10 p-2.5 rounded border border-info/30 flex-row items-start gap-2">
          <Info size={14} color={COLORS.info} style={{ marginTop: 2 }} />
          <Text className="text-xs font-sans text-text-primary leading-4 flex-1">
            {experienceAssessment}
          </Text>
        </View>
      ) : null}

      {/* Single Source KPI Summary from Backend summary object */}
      {summary ? (
        <View className="flex-row flex-wrap gap-2">
          <View className="flex-1 min-w-[120px] bg-background p-2 rounded border border-border">
            <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-0.5">
              Total Experience
            </Text>
            <Text className="text-xs font-sans-bold text-text-primary">
              {experienceDisplayText}
            </Text>


          </View>

          <View className="flex-1 min-w-[120px] bg-background p-2 rounded border border-border">
            <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-0.5">
              Employment Gaps
            </Text>
            <Text className="text-xs font-sans-bold text-text-primary">
              {summary.total_employment_gaps_count} ({summary.unexplained_gaps_count} Unexplained)
            </Text>
          </View>

          <View className="flex-1 min-w-[120px] bg-background p-2 rounded border border-border">
            <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-0.5">
              Concurrent Roles
            </Text>
            <Text className="text-xs font-sans-bold text-text-primary">
              {summary.concurrent_roles_count} Overlap(s)
            </Text>
          </View>
        </View>
      ) : null}

      {/* HR Review Alerts */}
      {hrIndicators.length > 0 && (
        <View className="bg-warning/10 p-2.5 rounded border border-warning/30 gap-1">
          <View className="flex-row items-center gap-1.5 mb-1">
            <ShieldAlert size={14} color={COLORS.warning} />
            <Text className="text-xs font-sans-bold text-warning uppercase">
              HR Review Indicators
            </Text>
          </View>
          {hrIndicators.map((ind: string, idx: number) => (
            <Text key={idx} className="text-xs text-text-primary leading-4">
              • {ind}
            </Text>
          ))}
        </View>
      )}

      {/* Chronological Timeline Events (Single Source of Truth) */}
      {events.length > 0 ? (
        <View className="gap-2 pt-1 border-t border-border">
          <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider mb-1">
            Chronological Employment & Gap Timeline ({events.length})
          </Text>

          <View className="pl-2 border-l-2 border-border/40 gap-2 my-1">
            {events.map((evt: TimelineEventItem, idx: number) => {
              if (evt.event_type === 'EMPLOYMENT_PERIOD' && evt.node) {
                return renderRoleNode(evt.node, false, evt.event_id || `evt-${idx}`);
              }

              if (evt.event_type === 'CONCURRENT_CLUSTER' && evt.cluster) {
                const cluster = evt.cluster;
                return (
                  <View key={evt.event_id} className="p-3 bg-info/5 border border-info/30 rounded my-1.5 gap-1.5">
                    <View className="flex-row justify-between items-center pb-1.5 border-b border-info/20">
                      <View className="flex-row items-center gap-1.5">
                        <Layers size={13} color={COLORS.info} />
                        <Text className="text-xs font-sans-bold text-info uppercase">
                          Concurrent / Overlapping Roles ({cluster.roles_count})
                        </Text>
                      </View>
                      <Badge
                        label={`${cluster.start_date || 'N/A'} → ${cluster.end_date || 'Present'}`}
                        tone="info"
                      />
                    </View>

                    <Text className="text-[11px] font-sans text-text-muted">
                      Candidate held multiple roles/deputations concurrently during this period ({cluster.duration_months} mo):
                    </Text>

                    {cluster.child_nodes.map((cNode: ExperienceTimelineNodeItem, cIdx: number) => renderRoleNode(cNode, true, `cluster-${evt.event_id}-${cIdx}`))}
                  </View>
                );
              }

              if ((evt.event_type === 'EMPLOYMENT_GAP' || evt.event_type === 'COVERED_GAP' || evt.event_type === 'TIMELINE_UNCERTAINTY') && evt.gap) {
                const gap = evt.gap;
                const style = getGapStyling(gap);

                return (
                  <View key={evt.event_id} className={`p-3 rounded my-2 ${style.cardClass}`}>
                    <View className="flex-row justify-between items-center mb-1">
                      <View className="flex-row items-center gap-1.5">
                        <Calendar size={14} color={style.iconColor} />
                        <Text className="text-xs font-sans-bold text-text-primary">
                          {gap.start_date} → {gap.end_date} ({gap.duration_months} Months)
                        </Text>
                      </View>
                      <Badge label={style.badgeLabel} tone={style.badgeTone} />
                    </View>

                    <Text className="text-xs font-sans text-text-primary leading-4 mt-0.5">
                      {gap.description}
                    </Text>

                    {gap.hr_review_reason ? (
                      <View className="mt-1.5 pt-1.5 border-t border-border/30 flex-row items-center gap-1">
                        <Info size={11} color={COLORS.textMuted} />
                        <Text className="text-[11px] font-sans text-text-muted leading-3.5 flex-1">
                          Activity Note: {gap.hr_review_reason}
                        </Text>
                      </View>
                    ) : null}
                  </View>
                );
              }

              return null;
            })}
          </View>
        </View>
      ) : canonicalJobs.length > 0 ? (
        /* Backward Compatibility: Fallback to canonical jobs list if timeline_events is absent */
        <View className="gap-2 pt-1 border-t border-border">
          <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider mb-1">
            Canonical Employment History ({canonicalJobs.length})
          </Text>
          <View className="pl-2 border-l-2 border-border/40 gap-2 my-1">
            {canonicalJobs.map((cj: CanonicalJobItem, idx: number) => renderCanonicalJob(cj, idx))}
          </View>
        </View>
      ) : null}

      {/* Undated Roles Collapsible Drawer */}
      {undated.length > 0 && (
        <View className="pt-2 border-t border-border">
          <Pressable
            onPress={() => setShowUndated(!showUndated)}
            className="flex-row justify-between items-center p-2 bg-background rounded border border-border"
          >
            <Text className="text-xs font-sans-bold text-text-muted">
              Undated Roles & Additional Details ({undated.length})
            </Text>
            {showUndated ? <ChevronUp size={14} color={COLORS.textMuted} /> : <ChevronDown size={14} color={COLORS.textMuted} />}
          </Pressable>

          {showUndated && (
            <View className="mt-2 gap-1.5 pl-1">
              {undated.map((uNode: ExperienceTimelineNodeItem, idx: number) => renderRoleNode(uNode, true, `undated-${idx}`))}
            </View>
          )}
        </View>
      )}

      {/* HR Observations Footer */}
      {hrObs.length > 0 && (
        <View className="pt-2 border-t border-border gap-1">
          <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-1">
            HR Observations
          </Text>
          {hrObs.map((obs: string, idx: number) => (
            <View key={idx} className="flex-row items-center gap-1.5">
              <CheckCircle2 size={12} color={COLORS.success} />
              <Text className="text-xs text-text-primary leading-4">{obs}</Text>
            </View>
          ))}
        </View>
      )}
    </Card>
  );
};
