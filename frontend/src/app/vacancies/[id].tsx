import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View, useWindowDimensions } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft, Sparkles, Building, MapPin, IndianRupee, Briefcase,
  GraduationCap, Award, Clock, Edit3, Share2, Archive, User,
  CheckCircle2, AlertTriangle, ChevronRight, Play, RefreshCw
} from 'lucide-react-native';
import { jobsService } from '@/services/jobsService';
import { JobOpening, VacancyRecommendationsResponse } from '@/types/api';
import { Badge, Breadcrumbs, Button, Card, EmptyState, ErrorBanner } from '@/components/ui';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { usePageTitle } from '@/hooks/usePageTitle';
import { COLORS } from '@/constants/colors';
import { formatSalary, formatExperience } from '@/utils/salary';

const CollapsibleBullets = ({ text, previewCount = 3 }: { text: string; previewCount?: number }) => {
  const [expanded, setExpanded] = useState(false);
  if (!text) return null;

  const items = text.includes('\n')
    ? text.split('\n').filter(s => s.trim().length > 0)
    : text.split('. ').filter(s => s.trim().length > 0).map(s => s.endsWith('.') ? s : s + '.');

  const visibleItems = expanded ? items : items.slice(0, previewCount);
  const hasMore = items.length > previewCount;

  return (
    <View className="gap-1.5 mt-1">
      {visibleItems.map((item, idx) => (
        <View key={idx} className="flex-row items-start gap-2 pr-2">
          <View className="w-1 h-1 rounded-full bg-text-muted mt-1.5" />
          <Text className="text-[11px] font-sans text-text-primary leading-4 flex-1">
            {item.trim().replace(/^- /, '')}
          </Text>
        </View>
      ))}
      {hasMore && (
        <Pressable
          onPress={() => setExpanded(!expanded)}
          className="mt-1 min-h-[32px] justify-center"
          accessibilityRole="button"
          hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
        >
          <Text className="text-[11px] font-sans-medium text-primary">
            {expanded ? 'Show Less' : `+ ${items.length - previewCount} More`}
          </Text>
        </Pressable>
      )}
    </View>
  );
};

export default function VacancyDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id: string; query?: string; department?: string; domain?: string; focus?: string }>();
  const { id, query, department, domain, focus } = params;
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;
  const isFocusedInsights = focus === 'insights';

  const [jobDetails, setJobDetails] = useState<JobOpening | null>(null);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(true);
  const [detailsError, setDetailsError] = useState<string | null>(null);
  const [isDescriptionExpanded, setIsDescriptionExpanded] = useState<boolean>(false);

  usePageTitle(jobDetails?.title ? `Vacancy #${id}: ${jobDetails.title} | AIRIS` : 'Job Vacancy | AIRIS');

  const getReturnHref = () => {
    const q = new URLSearchParams();
    if (query) q.set('query', query);
    if (department) q.set('department', department);
    if (domain) q.set('domain', domain);
    const str = q.toString();
    return `/vacancies${str ? `?${str}` : ''}`;
  };

  const handleBack = () => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace(getReturnHref() as any);
    }
  };

  const [recData, setRecData] = useState<VacancyRecommendationsResponse | null>(null);
  const [loadingRec, setLoadingRec] = useState<boolean>(true);
  const [recError, setRecError] = useState<string | null>(null);

  const loadDetails = async (jobId: string) => {
    try {
      setLoadingDetails(true);
      setDetailsError(null);
      const res = await jobsService.getJobById(jobId);
      setJobDetails(res);
    } catch (err: any) {
      setDetailsError(err.message || 'Failed to load vacancy details.');
    } finally {
      setLoadingDetails(false);
    }
  };

  const loadRecommendations = async (jobId: string) => {
    try {
      setLoadingRec(true);
      setRecError(null);
      const res = await jobsService.getVacancyRecommendations(jobId);
      setRecData(res);
    } catch (err: any) {
      setRecError(err.message || 'Failed to load vacancy recommendations.');
    } finally {
      setLoadingRec(false);
    }
  };

  useEffect(() => {
    if (id) {
      loadDetails(id);
      loadRecommendations(id);
    }
  }, [id]);

  const handleMatchCandidates = () => {
    if (!id) return;
    router.push({
      pathname: '/cv-match',
      params: { vacancy_id: String(id) },
    } as any);
  };

  const getStatusTone = (status?: string | null): 'success' | 'danger' | 'warning' | 'neutral' => {
    if (!status) return 'neutral';
    const s = status.toUpperCase();
    if (s === 'ACTIVE' || s === 'OPEN') return 'success';
    if (s === 'CLOSED' || s === 'INACTIVE' || s === 'CANCELLED') return 'danger';
    if (s === 'DRAFT' || s === 'PENDING') return 'warning';
    return 'neutral';
  };

  const rawStatus = jobDetails?.status || (jobDetails as any)?.vacancy_status || (jobDetails?.is_active != null ? (jobDetails.is_active ? 'ACTIVE' : 'INACTIVE') : 'ACTIVE');
  const statusTone = getStatusTone(rawStatus);

  if (loadingDetails) {
    return (
      <SafeAreaView className="items-center justify-center flex-1 bg-background">
        <ActivityIndicator size="small" color={COLORS.primary} />
        <Text className="text-xs font-sans text-text-muted mt-2">Loading vacancy profile...</Text>
      </SafeAreaView>
    );
  }

  if (detailsError) {
    return (
      <SafeAreaView className="flex-1 bg-background p-4 justify-center items-center">
        <View className="w-full max-w-md gap-3">
          <ErrorBanner title="Vacancy Load Error" message={detailsError} />
          <View className="flex-row justify-end gap-2">
            <Button label="Back to Vacancies" variant="secondary" size="sm" onPress={handleBack} />
            <Button label="Retry" variant="primary" size="sm" onPress={() => { if (id) { loadDetails(id); loadRecommendations(id); } }} />
          </View>
        </View>
      </SafeAreaView>
    );
  }

  if (!jobDetails) {
    return (
      <SafeAreaView className="items-center justify-center flex-1 bg-background p-4">
        <EmptyState
          title="Vacancy Not Found"
          subtitle="The requested job vacancy ID does not exist or may have been archived."
        />
        <View className="mt-4">
          <Button label="Back to Vacancies" variant="secondary" size="sm" onPress={handleBack} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      <Breadcrumbs
        items={[
          { label: 'Job Vacancies', href: getReturnHref() },
          { label: jobDetails?.title ? `#${id} - ${jobDetails.title}` : `#${id}` },
        ]}
      />
      {/* Responsive Header Area */}
      <View className="px-4 py-3.5 border-b bg-surface border-border">
        {/* Row 1: Back Navigation, Title, ID, Status Badge & Primary Action */}
        <View className="flex-row items-center justify-between gap-3">
          <View className="flex-row items-center flex-1 gap-2.5 pr-2">
            <Pressable
              onPress={handleBack}
              className="w-8 h-8 items-center justify-center rounded border border-border/80 bg-background active:bg-surface-hover"
              accessibilityRole="button"
              accessibilityLabel="Back to Vacancies"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <ArrowLeft size={16} color={COLORS.textPrimary} />
            </Pressable>

            <View className="flex-row flex-wrap items-center gap-2 flex-1">
              <Badge label={rawStatus.toUpperCase()} tone={statusTone} />
              <View className="bg-background px-1.5 py-0.5 rounded border border-border/60">
                <Text className="text-[11px] font-sans-bold text-text-muted">#{jobDetails.id}</Text>
              </View>
              <Text className="text-base sm:text-lg font-sans-bold text-text-primary leading-6" numberOfLines={1}>
                {jobDetails.title}
              </Text>
            </View>
          </View>

          <Button
            label="Match Candidates"
            variant="primary"
            size="sm"
            icon={<Play size={12} color={COLORS.background} fill={COLORS.background} />}
            onPress={handleMatchCandidates}
          />
        </View>

        {/* Row 2: Metadata Chips */}
        <View className="flex-row flex-wrap items-center gap-2 mt-2.5 ml-0 sm:ml-10">
          <View className="flex-row items-center gap-1.5 bg-background border border-border/60 px-2 py-1 rounded">
            <Building size={12} color={COLORS.textMuted} />
            <Text className="text-[11px] font-sans-medium text-text-muted">
              {jobDetails.company_name || jobDetails.company_name_db || 'Company not specified'}
            </Text>
          </View>

          <View className="flex-row items-center gap-1.5 bg-background border border-border/60 px-2 py-1 rounded">
            <MapPin size={12} color={COLORS.textMuted} />
            <Text className="text-[11px] font-sans-medium text-text-muted">
              {jobDetails.location_name || jobDetails.location_name_db || 'Location not specified'}
            </Text>
          </View>

          {jobDetails.department && (
            <View className="flex-row items-center gap-1.5 bg-background border border-border/60 px-2 py-1 rounded">
              <Briefcase size={12} color={COLORS.textMuted} />
              <Text className="text-[11px] font-sans-medium text-text-muted">{jobDetails.department}</Text>
            </View>
          )}

          <View className="flex-row items-center gap-1.5 bg-background border border-border/60 px-2 py-1 rounded">
            <Clock size={12} color={COLORS.textMuted} />
            <Text className="text-[11px] font-sans-medium text-text-muted">{formatExperience(jobDetails)}</Text>
          </View>

          <View className="flex-row items-center gap-1.5 bg-background border border-border/60 px-2 py-1 rounded">
            <IndianRupee size={12} color={COLORS.textMuted} />
            <Text className="text-[11px] font-sans-medium text-text-muted">{formatSalary(jobDetails)}</Text>
          </View>
        </View>
      </View>

      <ScrollView className="flex-1" contentContainerStyle={{ padding: 12, paddingBottom: 24 }}>

        {/* Dynamic Grid Layout */}
        <View className="flex-col lg:flex-row gap-4">

          {/* Left Column — Role Specifications */}
          <View className="w-full lg:w-7/12 gap-3.5">

            {/* Organization Hierarchy Card */}
            <Card className="gap-2.5 p-3.5 shadow-none border-border">
              <Text className="text-[11px] font-sans-bold text-primary uppercase tracking-wider">
                Organization Hierarchy Placement
              </Text>
              <View className="flex-row flex-wrap items-center gap-1.5">
                <View className="px-2 py-1 border rounded bg-background border-border">
                  <Text className="text-[10px] font-sans-bold text-text-muted uppercase">Business Group</Text>
                  <Text className="text-[11px] font-sans-semibold text-text-primary">
                    {jobDetails.business_group_name || (jobDetails.business_group_id ? `ID #${jobDetails.business_group_id}` : 'General')}
                  </Text>
                </View>
                <ChevronRight size={12} color={COLORS.textMuted} />

                <View className="px-2 py-1 border rounded bg-background border-border">
                  <Text className="text-[10px] font-sans-bold text-text-muted uppercase">Company</Text>
                  <Text className="text-[11px] font-sans-semibold text-text-primary">
                    {jobDetails.company_name_db || jobDetails.company_name || 'Not specified'}
                  </Text>
                </View>
                <ChevronRight size={12} color={COLORS.textMuted} />

                <View className="px-2 py-1 border rounded bg-background border-border">
                  <Text className="text-[10px] font-sans-bold text-text-muted uppercase">Location</Text>
                  <Text className="text-[11px] font-sans-semibold text-text-primary">
                    {jobDetails.location_name_db || jobDetails.location_name || 'Not specified'}
                  </Text>
                </View>
                <ChevronRight size={12} color={COLORS.textMuted} />

                <View className="px-2 py-1 border rounded bg-background border-border">
                  <Text className="text-[10px] font-sans-bold text-text-muted uppercase">Main Dept</Text>
                  <Text className="text-[11px] font-sans-semibold text-text-primary">
                    {jobDetails.main_department_name || (jobDetails.main_department_id ? `ID #${jobDetails.main_department_id}` : 'General')}
                  </Text>
                </View>
                <ChevronRight size={12} color={COLORS.textMuted} />

                <View className="px-2 py-1 border rounded bg-background border-border">
                  <Text className="text-[10px] font-sans-bold text-text-muted uppercase">Department</Text>
                  <Text className="text-[11px] font-sans-semibold text-text-primary">
                    {jobDetails.department_name || jobDetails.department || 'Not specified'}
                  </Text>
                </View>
                <ChevronRight size={12} color={COLORS.textMuted} />

                <View className="px-2 py-1 border rounded bg-primary/10 border-primary/30">
                  <Text className="text-[10px] font-sans-bold text-primary uppercase">Designation</Text>
                  <Text className="text-[11px] font-sans-semibold text-primary">
                    {jobDetails.designation_name || jobDetails.title}
                  </Text>
                </View>
              </View>
            </Card>

            {/* Responsibilities & Description with Show More/Less */}
            {(jobDetails.job_description || jobDetails.responsibilities) && (
              <Card className="gap-2.5 p-3.5 shadow-none border-border">
                <View className="flex-row items-center justify-between pb-2 border-b border-border/50">
                  <Text className="text-[11px] font-sans-bold text-text-muted uppercase tracking-wider">Role Details</Text>
                </View>
                {jobDetails.job_description && (
                  <View className="gap-1">
                    <Text
                      className="text-xs font-sans text-text-primary leading-5"
                      numberOfLines={isDescriptionExpanded ? undefined : 3}
                    >
                      {jobDetails.job_description}
                    </Text>
                    {jobDetails.job_description.length > 150 && (
                      <Pressable
                        onPress={() => setIsDescriptionExpanded(!isDescriptionExpanded)}
                        className="py-1 min-h-[32px] justify-center self-start"
                        accessibilityRole="button"
                        hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                      >
                        <Text className="text-[11px] font-sans-medium text-primary">
                          {isDescriptionExpanded ? 'Show Less Description' : 'Show Full Description'}
                        </Text>
                      </Pressable>
                    )}
                  </View>
                )}
                {jobDetails.responsibilities && (
                  <CollapsibleBullets text={jobDetails.responsibilities} previewCount={3} />
                )}
              </Card>
            )}

            {/* Qualifications */}
            <Card className="gap-3 p-3.5 shadow-none border-border">
              <View className="flex-row items-center justify-between pb-2 border-b border-border/50">
                <Text className="text-[11px] font-sans-bold text-text-muted uppercase tracking-wider">Qualifications & Requirements</Text>
              </View>

              <View className="flex-row flex-wrap gap-4">
                {jobDetails.education && (
                  <View className="flex-1 min-w-[140px] bg-background p-2 rounded border border-border">
                    <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-0.5">Education</Text>
                    <Text className="text-xs font-sans-semibold text-text-primary" numberOfLines={1}>{jobDetails.education}</Text>
                  </View>
                )}
                {jobDetails.certifications && (
                  <View className="flex-1 min-w-[140px] bg-background p-2 rounded border border-border">
                    <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-0.5">Certifications</Text>
                    <Text className="text-xs font-sans-semibold text-text-primary" numberOfLines={1}>{jobDetails.certifications}</Text>
                  </View>
                )}
              </View>

              {jobDetails.required_skills && jobDetails.required_skills.length > 0 && (
                <View className="gap-1.5">
                  <Text className="text-[11px] font-sans-bold text-text-muted uppercase">Core Skills</Text>
                  <View className="flex-row flex-wrap gap-1.5">
                    {jobDetails.required_skills.map((skill, idx) => (
                      <View key={idx} className="bg-background border border-border px-2 py-1 rounded">
                        <Text className="text-[11px] font-sans-medium text-text-primary">{skill}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}

              {jobDetails.preferred_keywords && jobDetails.preferred_keywords.length > 0 && (
                <View className="gap-1.5 pt-1 border-t border-border/40">
                  <Text className="text-[11px] font-sans-bold text-text-muted uppercase">Keywords & Domain Terms</Text>
                  <View className="flex-row flex-wrap gap-1.5">
                    {jobDetails.preferred_keywords.map((keyword, idx) => (
                      <View key={idx} className="bg-background border border-border/50 px-2 py-0.5 rounded">
                        <Text className="text-[11px] font-sans text-text-muted">{keyword}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}
            </Card>
          </View>

          {/* Right Column — AI Insights & Talent Recommendations */}
          <View className="w-full lg:w-5/12 gap-3.5">
            <Card className={`gap-3 p-3.5 shadow-none ${isFocusedInsights ? 'border-primary shadow-sm bg-primary/5' : 'border-border'}`}>
              <View className="flex-row items-center justify-between border-b border-border/50 pb-2">
                <View className="flex-row items-center gap-1.5">
                  <Sparkles size={14} color={isFocusedInsights ? COLORS.primary : COLORS.info} />
                  <Text className={`text-[11px] font-sans-bold uppercase tracking-wider ${isFocusedInsights ? 'text-primary' : 'text-text-primary'}`}>
                    AI Intelligence {isFocusedInsights && '• Focused'}
                  </Text>
                </View>
                {isFocusedInsights && (
                  <Badge label="Target Section" tone="info" />
                )}
              </View>

              {loadingRec ? (
                <View className="items-center justify-center py-8">
                  <ActivityIndicator size="small" color={COLORS.info} />
                  <Text className="text-xs font-sans text-text-muted mt-2">Loading match insights...</Text>
                </View>
              ) : recError ? (
                <View className="gap-2 py-2">
                  <ErrorBanner title="Recommendations Error" message={recError} />
                  <View className="self-start">
                    <Button
                      label="Retry Recommendations"
                      variant="ghost"
                      size="sm"
                      icon={<RefreshCw size={12} color={COLORS.textMuted} />}
                      onPress={() => { if (id) loadRecommendations(id); }}
                    />
                  </View>
                </View>
              ) : recData ? (
                <View className="gap-3">

                  {/* Candidates */}
                  <View className="gap-2">
                    <Text className="text-[11px] font-sans-bold text-text-muted uppercase tracking-wider">Top Candidate Matches</Text>
                    {(!recData.top_candidate_matches || recData.top_candidate_matches.length === 0) ? (
                      <View className="p-3 border rounded bg-background border-border">
                        <Text className="text-[11px] font-sans text-text-muted italic">No candidate matches found for this vacancy.</Text>
                      </View>
                    ) : (
                      <View className="gap-1.5">
                        {recData.top_candidate_matches.slice(0, 4).map((cand: any, idx: number) => (
                          <Pressable
                            key={idx}
                            onPress={() => router.push(`/candidates/${cand.candidate_id}`)}
                            className="flex-row items-center justify-between p-2.5 border rounded bg-background border-border min-h-[44px] active:bg-surface-hover"
                            accessibilityRole="button"
                            hitSlop={{ top: 4, bottom: 4, left: 4, right: 4 }}
                          >
                            <View className="flex-row items-center flex-1 gap-2.5 pr-2">
                              <View className="items-center justify-center w-7 h-7 rounded bg-primary/10">
                                <Text className="text-xs font-sans-bold text-primary">
                                  {(cand.full_name || 'U').charAt(0).toUpperCase()}
                                </Text>
                              </View>
                              <View className="flex-1">
                                <Text className="text-xs font-sans-bold text-text-primary" numberOfLines={1}>
                                  {cand.full_name || cand.candidate_id}
                                </Text>
                                <Text className="text-[11px] font-sans text-text-muted" numberOfLines={1}>
                                  {cand.recommendation}
                                </Text>
                              </View>
                            </View>
                            <ScoreBadge score={cand.match_score || 0} classification={cand.classification || 'LOW'} />
                          </Pressable>
                        ))}
                      </View>
                    )}
                  </View>

                  {/* Talent Pools */}
                  {recData.talent_pools && recData.talent_pools.length > 0 && (
                    <View className="gap-1.5 pt-2 border-t border-border/40">
                      <Text className="text-[11px] font-sans-bold text-text-muted uppercase tracking-wider">Talent Pools</Text>
                      <View className="flex-row flex-wrap gap-1.5">
                        {recData.talent_pools.map((pool, idx) => (
                          <Badge key={idx} label={pool} tone="neutral" />
                        ))}
                      </View>
                    </View>
                  )}

                  {/* Market Insights */}
                  {recData.skill_gap_insights && recData.skill_gap_insights.length > 0 && (
                    <View className="gap-1.5 pt-2 border-t border-border/40">
                      <Text className="text-[11px] font-sans-bold text-text-muted uppercase tracking-wider">Skill Gaps & Market Insights</Text>
                      <View className="gap-1.5">
                        {recData.skill_gap_insights.map((sg, idx) => (
                          <View key={idx} className="bg-warning/5 border border-warning/20 rounded p-2.5 flex-row items-center justify-between">
                            <View className="flex-1 pr-2">
                              <Text className="text-[11px] font-sans-bold text-text-primary mb-0.5">{sg.skill}</Text>
                              <Text className="text-[11px] font-sans text-text-muted" numberOfLines={1}>{sg.recommendation}</Text>
                            </View>
                            <Badge label={sg.market_rarity} tone="warning" />
                          </View>
                        ))}
                      </View>
                    </View>
                  )}

                </View>
              ) : (
                <Text className="text-[11px] font-sans text-text-muted">No insights available.</Text>
              )}
            </Card>
          </View>

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
