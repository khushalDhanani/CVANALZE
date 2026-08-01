import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View, useWindowDimensions } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft, Sparkles, Building, MapPin, IndianRupee, Briefcase,
  GraduationCap, Award, Clock, Edit3, Share2, Archive, User,
  CheckCircle2, AlertTriangle, ChevronRight, Play
} from 'lucide-react-native';
import { jobsService } from '@/services/jobsService';
import { JobOpening, VacancyRecommendationsResponse } from '@/types/api';
import { Badge } from '@/components/ui';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { COLORS } from '@/constants/colors';

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
          <Text className="text-[11px] font-sans text-text-secondary leading-4 flex-1">
            {item.trim().replace(/^- /, '')}
          </Text>
        </View>
      ))}
      {hasMore && (
        <Pressable onPress={() => setExpanded(!expanded)} className="mt-1">
          <Text className="text-[10px] font-sans-medium text-primary">
            {expanded ? 'Show Less' : `+ ${items.length - previewCount} More`}
          </Text>
        </Pressable>
      )}
    </View>
  );
};

export default function VacancyDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  const [jobDetails, setJobDetails] = useState<JobOpening | null>(null);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(true);

  const [recData, setRecData] = useState<VacancyRecommendationsResponse | null>(null);
  const [loadingRec, setLoadingRec] = useState<boolean>(true);

  useEffect(() => {
    if (id) {
      loadDetails(id);
      loadRecommendations(id);
    }
  }, [id]);

  const loadDetails = async (jobId: string) => {
    try {
      setLoadingDetails(true);
      const res = await jobsService.getJobById(jobId);
      setJobDetails(res);
    } catch (err) {
      console.warn('Failed to load job details:', err);
    } finally {
      setLoadingDetails(false);
    }
  };

  const loadRecommendations = async (jobId: string) => {
    try {
      setLoadingRec(true);
      const res = await jobsService.getVacancyRecommendations(jobId);
      setRecData(res);
    } catch (err) {
      console.warn('Failed to load vacancy recommendations:', err);
    } finally {
      setLoadingRec(false);
    }
  };

  const formatRupees = (val: number) => {
    if (!val || val <= 0) return null;
    if (val <= 100) return `₹${val}L`;
    return `₹${val.toLocaleString('en-IN')}`;
  };

  const formatSalary = (item: JobOpening) => {
    const min = item.min_ctc;
    const max = item.max_ctc;
    const formattedMin = min ? formatRupees(min) : null;
    const formattedMax = max ? formatRupees(max) : null;
    if (formattedMin && formattedMax) return `${formattedMin}-${formattedMax}`;
    if (formattedMin) return `>${formattedMin}`;
    if (formattedMax) return `<${formattedMax}`;
    return 'N/A';
  };

  const formatExperience = (item: JobOpening) => {
    const min = item.min_experience_years;
    const max = item.max_experience_years;
    if (min != null && max != null && (min > 0 || max > 0)) {
      if (min === max) return `${min}y`;
      return `${min}-${max}y`;
    }
    if (min != null && min > 0) return `${min}y+`;
    if (max != null && max > 0) return `<${max}y`;
    return 'Any';
  };

  if (loadingDetails) {
    return (
      <SafeAreaView className="flex-1 bg-background justify-center items-center">
        <ActivityIndicator size="small" color={COLORS.primary} />
      </SafeAreaView>
    );
  }

  if (!jobDetails) {
    return (
      <SafeAreaView className="flex-1 bg-background justify-center items-center">
        <Text className="text-xs font-sans-medium text-text-muted mb-4">Vacancy not found.</Text>
        <Pressable onPress={() => router.back()} className="px-3 py-1.5 bg-surface border border-border rounded">
          <Text className="text-text-primary font-sans-medium text-[11px]">Back</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView className="flex-1 bg-background" edges={['top', 'bottom']}>
      {/* Compact Hero Header */}
      <View className="bg-surface border-b border-border px-4 py-3">
        <View className="flex-row items-start justify-between mb-2">
          <View className="flex-row items-center gap-2 flex-1 pr-4">
            <Pressable onPress={() => router.back()} className="p-1 active:bg-background rounded">
              <ArrowLeft size={16} color={COLORS.textPrimary} />
            </Pressable>
            <View className="bg-success/10 px-1.5 py-0.5 rounded border border-success/20">
              <Text className="text-[9px] font-sans-bold text-success uppercase">Active</Text>
            </View>
            <Text className="text-[10px] font-sans-medium text-text-muted">#{jobDetails.id}</Text>
            <Text className="text-base font-sans-bold text-text-primary leading-5 flex-shrink" numberOfLines={1}>
              {jobDetails.title}
            </Text>
          </View>

          <View className="flex-row items-center gap-1.5">
            <Pressable
              onPress={() => router.push('/cv-match')}
              className="px-2.5 py-1.5 bg-primary rounded flex-row items-center gap-1 active:bg-primary-dark"
            >
              <Play size={10} color={COLORS.background} fill={COLORS.background} />
              <Text className="text-[10px] font-sans-bold text-white uppercase tracking-wider">Match</Text>
            </Pressable>
          </View>
        </View>

        <View className="flex-row flex-wrap items-center gap-x-4 gap-y-1.5 ml-8">
          <View className="flex-row items-center gap-1">
            <Building size={10} color={COLORS.textMuted} />
            <Text className="text-[11px] font-sans-medium text-text-secondary">{jobDetails.company_name || 'Aether'}</Text>
          </View>
          <View className="flex-row items-center gap-1">
            <MapPin size={10} color={COLORS.textMuted} />
            <Text className="text-[11px] font-sans-medium text-text-secondary">{jobDetails.location_name || 'Remote'}</Text>
          </View>
          {jobDetails.department && (
            <View className="flex-row items-center gap-1">
              <Briefcase size={10} color={COLORS.textMuted} />
              <Text className="text-[11px] font-sans-medium text-text-secondary">{jobDetails.department}</Text>
            </View>
          )}
          <View className="flex-row items-center gap-1">
            <Clock size={10} color={COLORS.textMuted} />
            <Text className="text-[11px] font-sans-medium text-text-secondary">{formatExperience(jobDetails)}</Text>
          </View>
          <View className="flex-row items-center gap-1">
            <IndianRupee size={10} color={COLORS.textMuted} />
            <Text className="text-[11px] font-sans-medium text-text-secondary">{formatSalary(jobDetails)}</Text>
          </View>
        </View>
      </View>

      <ScrollView className="flex-1" contentContainerStyle={{ padding: 12, paddingBottom: 24 }}>

        {/* Dynamic Grid Layout */}
        <View className={`flex-row flex-wrap gap-3`}>

          {/* Main Info Column */}
          <View className={`flex-1 ${isDesktop ? 'min-w-[400px]' : 'min-w-[100%]'}`}>

            {/* Responsibilities */}
            {(jobDetails.job_description || jobDetails.responsibilities) && (
              <View className="bg-surface border border-border rounded-lg p-3 mb-3">
                <View className="flex-row items-center justify-between border-b border-border/50 pb-2 mb-2">
                  <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">Role Details</Text>
                </View>
                {jobDetails.job_description && (
                  <View className="mb-2">
                    <Text className="text-[11px] font-sans text-text-secondary leading-4" numberOfLines={3}>
                      {jobDetails.job_description}
                    </Text>
                  </View>
                )}
                {jobDetails.responsibilities && (
                  <CollapsibleBullets text={jobDetails.responsibilities} previewCount={3} />
                )}
              </View>
            )}

            {/* Qualifications */}
            <View className="bg-surface border border-border rounded-lg p-3 mb-3">
              <View className="flex-row items-center justify-between border-b border-border/50 pb-2 mb-2">
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">Qualifications</Text>
              </View>

              <View className="flex-row gap-4 mb-3">
                {jobDetails.education && (
                  <View className="flex-1">
                    <Text className="text-[9px] font-sans-bold text-text-muted uppercase mb-0.5">Education</Text>
                    <Text className="text-[11px] font-sans-semibold text-text-primary" numberOfLines={1}>{jobDetails.education}</Text>
                  </View>
                )}
                {jobDetails.certifications && (
                  <View className="flex-1">
                    <Text className="text-[9px] font-sans-bold text-text-muted uppercase mb-0.5">Certifications</Text>
                    <Text className="text-[11px] font-sans-semibold text-text-primary" numberOfLines={1}>{jobDetails.certifications}</Text>
                  </View>
                )}
              </View>

              {jobDetails.required_skills && jobDetails.required_skills.length > 0 && (
                <View className="mb-2.5">
                  <Text className="text-[9px] font-sans-bold text-text-muted uppercase mb-1">Core Skills</Text>
                  <View className="flex-row flex-wrap gap-1">
                    {jobDetails.required_skills.map((skill, idx) => (
                      <View key={idx} className="bg-background border border-border px-1.5 py-0.5 rounded">
                        <Text className="text-[9px] font-sans-medium text-text-primary">{skill}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}

              {jobDetails.preferred_keywords && jobDetails.preferred_keywords.length > 0 && (
                <View>
                  <Text className="text-[9px] font-sans-bold text-text-muted uppercase mb-1">Keywords</Text>
                  <View className="flex-row flex-wrap gap-1">
                    {jobDetails.preferred_keywords.map((keyword, idx) => (
                      <View key={idx} className="bg-background border border-border/50 px-1.5 py-0.5 rounded">
                        <Text className="text-[9px] font-sans text-text-secondary">{keyword}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}
            </View>
          </View>

          {/* AI Intelligence Column */}
          <View className={`flex-1 ${isDesktop ? 'min-w-[350px] max-w-[500px]' : 'min-w-[100%]'}`}>
            <View className="bg-surface border border-info/30 rounded-lg p-3">
              <View className="flex-row items-center gap-1.5 border-b border-border/50 pb-2 mb-2">
                <Sparkles size={12} color={COLORS.info} />
                <Text className="text-[10px] font-sans-bold text-info uppercase tracking-wider">AI Intelligence</Text>
              </View>

              {loadingRec ? (
                <View className="py-6 items-center justify-center">
                  <ActivityIndicator size="small" color={COLORS.info} />
                </View>
              ) : recData ? (
                <View className="gap-3">

                  {/* Candidates */}
                  <View>
                    <Text className="text-[9px] font-sans-bold text-text-muted uppercase mb-1.5">Top Matches</Text>
                    {(!recData.top_candidate_matches || recData.top_candidate_matches.length === 0) ? (
                      <Text className="text-[10px] font-sans text-text-faint italic">No candidates matched.</Text>
                    ) : (
                      <View className="gap-1.5">
                        {recData.top_candidate_matches.slice(0, 3).map((cand: any, idx: number) => (
                          <Pressable
                            key={idx}
                            onPress={() => router.push(`/candidates/${cand.candidate_id}`)}
                            className="bg-background border border-border rounded p-2 flex-row items-center justify-between active:bg-surface-hover"
                          >
                            <View className="flex-row items-center gap-2 flex-1 pr-2">
                              <View className="w-6 h-6 rounded bg-primary/10 items-center justify-center">
                                <Text className="text-[10px] font-sans-bold text-primary">
                                  {(cand.full_name || 'U').charAt(0).toUpperCase()}
                                </Text>
                              </View>
                              <View className="flex-1">
                                <Text className="text-[11px] font-sans-bold text-text-primary" numberOfLines={1}>
                                  {cand.full_name || cand.candidate_id}
                                </Text>
                                <Text className="text-[9px] font-sans text-text-secondary" numberOfLines={1}>
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
                    <View>
                      <Text className="text-[9px] font-sans-bold text-text-muted uppercase mb-1.5">Talent Pools</Text>
                      <View className="flex-row flex-wrap gap-1">
                        {recData.talent_pools.map((pool, idx) => (
                          <Badge key={idx} label={pool} tone="success" />
                        ))}
                      </View>
                    </View>
                  )}

                  {/* Market Insights */}
                  {recData.skill_gap_insights && recData.skill_gap_insights.length > 0 && (
                    <View>
                      <Text className="text-[9px] font-sans-bold text-text-muted uppercase mb-1.5">Skill Gaps</Text>
                      <View className="gap-1.5">
                        {recData.skill_gap_insights.map((sg, idx) => (
                          <View key={idx} className="bg-warning/5 border border-warning/20 rounded p-1.5 flex-row items-center justify-between">
                            <View className="flex-1 pr-2">
                              <Text className="text-[10px] font-sans-bold text-text-primary mb-0.5">{sg.skill}</Text>
                              <Text className="text-[9px] font-sans text-text-secondary" numberOfLines={1}>{sg.recommendation}</Text>
                            </View>
                            <Badge label={sg.market_rarity} tone="warning" />
                          </View>
                        ))}
                      </View>
                    </View>
                  )}

                </View>
              ) : (
                <Text className="text-[10px] font-sans text-text-muted">No insights available.</Text>
              )}
            </View>
          </View>

        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
