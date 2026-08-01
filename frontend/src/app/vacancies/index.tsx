import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
  useWindowDimensions,
} from 'react-native';
import { Briefcase, Target, CheckCircle, IndianRupee, Sparkles, X, UserCheck, AlertTriangle } from 'lucide-react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { jobsService } from '@/services/jobsService';
import { useJobs } from '@/hooks/useJobs';
import { usePageTitle } from '@/hooks/usePageTitle';
import { JobOpening, VacancyRecommendationsResponse } from '@/types/api';
import { TextField, Card, Button, Badge, EmptyState, DenseRow, Breadcrumbs } from '@/components/ui';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { COLORS } from '@/constants/colors';

export default function VacanciesScreen() {
  usePageTitle('Job Vacancies | AIRIS');
  const router = useRouter();
  const params = useLocalSearchParams<{ query?: string; department?: string; domain?: string }>();
  const { jobs, loading, error, refreshJobs } = useJobs();

  const [searchQuery, setSearchQuery] = useState<string>(params.query || '');
  const [filterDept, setFilterDept] = useState<string>(params.department || '');
  const [filterDomain, setFilterDomain] = useState<string>(params.domain || '');
  
  const [clearingCache, setClearingCache] = useState<boolean>(false);
  const [cacheMessage, setCacheMessage] = useState<string | null>(null);

  // Synchronize state changes with URL query parameters
  useEffect(() => {
    const nextParams: Record<string, string> = {};
    if (searchQuery) nextParams.query = searchQuery;
    if (filterDept) nextParams.department = filterDept;
    if (filterDomain) nextParams.domain = filterDomain;

    router.setParams(nextParams);
  }, [searchQuery, filterDept, filterDomain]);

  const handleOpenDetails = (jobId: string | number) => {
    const queryParams: Record<string, string> = {};
    if (searchQuery) queryParams.query = searchQuery;
    if (filterDept) queryParams.department = filterDept;
    if (filterDomain) queryParams.domain = filterDomain;

    router.push({
      pathname: '/vacancies/[id]',
      params: { id: String(jobId), ...queryParams },
    } as any);
  };

  const handleOpenRecommendations = (jobId: string | number) => {
    handleOpenDetails(jobId);
  };

  const { width } = useWindowDimensions();
  let numColumns = 1;
  if (width >= 1024) {
    numColumns = 4;
  } else if (width >= 768) {
    numColumns = 3;
  }

  const handleInvalidateCache = async () => {
    setClearingCache(true);
    setCacheMessage(null);
    try {
      const res = await jobsService.invalidateJobsCache();
      setCacheMessage(res.message || 'Cache cleared!');
      await refreshJobs();
    } catch (err: any) {
      setCacheMessage('Failed to invalidate cache.');
    } finally {
      setClearingCache(false);
      setTimeout(() => setCacheMessage(null), 3000);
    }
  };

  const filteredJobs = (jobs || []).filter((job) => {
    if (!job) return false;
    const query = searchQuery.toLowerCase();
    const titleMatch = (job.title || '').toLowerCase().includes(query);
    const deptMatch = (job.department || '').toLowerCase().includes(query);
    const skillsMatch = (job.required_skills || []).join(' ').toLowerCase().includes(query);
    
    const matchesQuery = query === '' || titleMatch || deptMatch || skillsMatch;
    const matchesDept = filterDept === '' || (job.department || '').toLowerCase() === filterDept.toLowerCase();
    const matchesDomain = filterDomain === '' || (job.domain || '').toLowerCase() === filterDomain.toLowerCase();
    
    return matchesQuery && matchesDept && matchesDomain;
  });

  const formatRupees = (val: number) => {
    if (!val || val <= 0) return null;
    if (val <= 100) {
      return `₹${val} LPA`;
    }
    return `₹${val.toLocaleString('en-IN')}`;
  };

  const formatSalary = (item: JobOpening) => {
    const min = item.min_ctc;
    const max = item.max_ctc;

    const formattedMin = min ? formatRupees(min) : null;
    const formattedMax = max ? formatRupees(max) : null;

    if (formattedMin && formattedMax) {
      return `${formattedMin} - ${formattedMax}`;
    }
    if (formattedMin) return `From ${formattedMin}`;
    if (formattedMax) return `Up to ${formattedMax}`;
    return 'Not Specified';
  };

  const formatExperience = (item: JobOpening) => {
    const min = item.min_experience_years;
    const max = item.max_experience_years;

    if (min != null && max != null && (min > 0 || max > 0)) {
      if (min === max) return `${min} Yrs Exp`;
      return `${min} - ${max} Yrs Exp`;
    }
    if (min != null && min > 0) return `${min}+ Yrs Exp`;
    if (max != null && max > 0) return `Up to ${max} Yrs Exp`;
    return 'Any Experience';
  };

  const renderJobCard = ({ item }: { item: JobOpening }) => {
    const title = item.title || 'Untitled Vacancy';
    const dept = item.department;
    const vacancyId = item.id;
    const salaryText = formatSalary(item);
    const expText = formatExperience(item);
    const displayedSkills = item.required_skills?.slice(0, 4) || [];
    const remainingSkillsCount = (item.required_skills?.length || 0) - 4;

    return (
      <View className="flex-1" style={numColumns > 1 ? { maxWidth: `${100/numColumns}%` } : {}}>
        <Card className="flex-1 mb-3 mx-1 p-3">
          {/* Header */}
          <View className="mb-2.5">
            <View className="flex-row items-center justify-between mb-1">
              <Text className="text-[10px] font-sans-bold text-primary uppercase tracking-wider">
                {vacancyId ? `ID #${vacancyId}` : 'Active'}
              </Text>
              {dept && (
                <View className="flex-row items-center gap-1 bg-surface border border-border px-1.5 py-0.5 rounded">
                  <Briefcase size={10} color={COLORS.textMuted} />
                  <Text className="text-[9px] font-sans-medium text-text-muted" numberOfLines={1}>
                    {dept}
                  </Text>
                </View>
              )}
            </View>
            <Text className="text-sm font-sans-bold text-text-primary leading-tight" numberOfLines={2}>
              {title}
            </Text>
          </View>

          {/* Metrics */}
          <View className="flex-row gap-3 mb-2.5">
            <View className="flex-1 bg-background border border-border rounded p-1.5">
              <Text className="text-[9px] font-sans-bold text-text-muted uppercase tracking-wider mb-0.5">Exp</Text>
              <Text className="text-[11px] font-sans-medium text-text-primary" numberOfLines={1}>{expText}</Text>
            </View>
            <View className="flex-1 bg-background border border-border rounded p-1.5">
              <Text className="text-[9px] font-sans-bold text-text-muted uppercase tracking-wider mb-0.5">Salary</Text>
              <Text className="text-[11px] font-sans-medium text-text-primary" numberOfLines={1}>{salaryText}</Text>
            </View>
          </View>

          {/* Required Skills */}
          {displayedSkills.length > 0 && (
            <View className="mb-3">
              <View className="flex-row flex-wrap gap-1">
                {displayedSkills.map((skill, idx) => (
                  <View key={idx} className="bg-surface border border-border px-1.5 py-0.5 rounded">
                    <Text className="text-[9px] font-sans text-text-secondary">{skill}</Text>
                  </View>
                ))}
                {remainingSkillsCount > 0 && (
                  <View className="bg-background border border-border px-1.5 py-0.5 rounded">
                    <Text className="text-[9px] font-sans text-text-faint">+{remainingSkillsCount}</Text>
                  </View>
                )}
              </View>
            </View>
          )}

          {/* Flex spacer to push footer to bottom */}
          <View className="flex-1" />

          {/* Footer Actions */}
          <View className="flex-row gap-2 pt-2.5 border-t border-border">
            <Pressable
              onPress={() => handleOpenDetails(item.id)}
              className="flex-1 bg-surface border border-border py-1.5 rounded items-center justify-center active:bg-background"
            >
              <Text className="text-[11px] font-sans-semibold text-text-primary">View Details</Text>
            </Pressable>
            <Pressable
              onPress={() => handleOpenRecommendations(vacancyId)}
              className="flex-1 flex-row bg-primary/10 py-1.5 rounded items-center justify-center gap-1 active:bg-primary/20"
            >
              <Sparkles size={10} color={COLORS.info} />
              <Text className="text-[11px] font-sans-semibold text-info">AI Insights</Text>
            </Pressable>
          </View>
        </Card>
      </View>
    );
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Job Vacancies' }]} />
      {/* Sticky Header */}
      <View className="flex-row items-center justify-between px-3 py-2 bg-surface border-b border-border">
        <View>
          <Text className="text-base font-sans-bold text-text-primary">Active Job Vacancies</Text>
          <Text className="text-[11px] font-sans text-text-muted">
            {filteredJobs.length} of {jobs.length} jobs available in memory
          </Text>
        </View>
        <Button
          label={clearingCache ? 'Clearing...' : 'Clear Cache'}
          variant="secondary"
          size="sm"
          onPress={handleInvalidateCache}
          loading={clearingCache}
          disabled={clearingCache}
        />
      </View>

      <View className="flex-1 px-3 pt-3">
        {cacheMessage && (
          <Card className="bg-success/10 border-success/30 flex-row items-center justify-center gap-1.5 mb-3">
            <CheckCircle size={14} color={COLORS.success} />
            <Text className="text-xs font-sans-semibold text-success">
              {cacheMessage}
            </Text>
          </Card>
        )}

        {/* Search & Filters Panel */}
        <Card className="mb-4 gap-3">
          <TextField
            label=""
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="Search by job title, department, or skill..."
          />
          <View className="flex-row gap-3">
            <View className="flex-1">
              <TextField
                label="Department Filter"
                value={filterDept}
                onChangeText={setFilterDept}
                placeholder="e.g. Engineering"
              />
            </View>
            <View className="flex-1">
              <TextField
                label="Domain Filter"
                value={filterDomain}
                onChangeText={setFilterDomain}
                placeholder="e.g. Software"
              />
            </View>
          </View>
        </Card>

        {/* Loading state */}
        {loading ? (
          <View className="flex-1 justify-center items-center py-12">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">Fetching job openings from backend...</Text>
          </View>
        ) : error ? (
          <Card className="bg-danger/10 border-danger/30">
            <Text className="text-xs font-sans-medium text-danger">{error}</Text>
            <View className="mt-2 self-start">
              <Button label="Try Refreshing" variant="ghost" onPress={refreshJobs} />
            </View>
          </Card>
        ) : (
          <FlatList
            key={`grid-${numColumns}`}
            numColumns={numColumns}
            columnWrapperStyle={numColumns > 1 ? { gap: 8, paddingHorizontal: 4 } : undefined}
            data={filteredJobs}
            keyExtractor={(item, index) => (item?.id ? String(item.id) : `job-${index}`)}
            renderItem={renderJobCard}
            contentContainerStyle={{ paddingBottom: 24, paddingHorizontal: numColumns > 1 ? 4 : 0 }}
            onRefresh={refreshJobs}
            refreshing={loading}
            ListEmptyComponent={
              <EmptyState 
                title="No job openings found" 
                subtitle="Try adjusting your search criteria" 
              />
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}
