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
import { Briefcase, Target, CheckCircle, Sparkles, X, AlertTriangle, RefreshCw } from 'lucide-react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { jobsService } from '@/services/jobsService';
import { useJobs } from '@/hooks/useJobs';
import { usePageTitle } from '@/hooks/usePageTitle';
import { JobOpening, OrganizationSelection } from '@/types/api';
import {
  TextField,
  Card,
  Button,
  Badge,
  EmptyState,
  Breadcrumbs,
  OrganizationHierarchySelector,
  ErrorBanner,
} from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { formatSalary, formatExperience } from '@/utils/salary';

export default function VacanciesScreen() {
  usePageTitle('Job Vacancies | AIRIS');
  const router = useRouter();
  const params = useLocalSearchParams<{ query?: string; department?: string; domain?: string }>();
  const { jobs, loading, error, refreshJobs } = useJobs();

  const [searchQuery, setSearchQuery] = useState<string>(params.query || '');
  const [filterDept, setFilterDept] = useState<string>(params.department || '');
  const [filterDomain, setFilterDomain] = useState<string>(params.domain || '');
  const [orgSelection, setOrgSelection] = useState<OrganizationSelection>({});
  const [showHierarchyFilter, setShowHierarchyFilter] = useState<boolean>(false);

  const [confirmPurgeModalVisible, setConfirmPurgeModalVisible] = useState<boolean>(false);
  const [clearingCache, setClearingCache] = useState<boolean>(false);
  const [cacheSuccess, setCacheSuccess] = useState<string | null>(null);
  const [cacheError, setCacheError] = useState<string | null>(null);

  // Synchronize state changes with URL query parameters deliberately
  useEffect(() => {
    router.setParams({
      query: searchQuery || undefined,
      department: filterDept || undefined,
      domain: filterDomain || undefined,
    });
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
    const queryParams: Record<string, string> = { focus: 'insights' };
    if (searchQuery) queryParams.query = searchQuery;
    if (filterDept) queryParams.department = filterDept;
    if (filterDomain) queryParams.domain = filterDomain;

    router.push({
      pathname: '/vacancies/[id]',
      params: { id: String(jobId), ...queryParams },
    } as any);
  };

  const { width } = useWindowDimensions();
  let numColumns = 1;
  if (width >= 1380) {
    numColumns = 4;
  } else if (width >= 1024) {
    numColumns = 3;
  } else if (width >= 640) {
    numColumns = 2;
  }

  const handleConfirmPurgeCache = async () => {
    setConfirmPurgeModalVisible(false);
    setClearingCache(true);
    setCacheSuccess(null);
    setCacheError(null);
    try {
      const res = await jobsService.invalidateJobsCache();
      setCacheSuccess(res.message || 'Vacancies cache cleared successfully.');
      await refreshJobs();
    } catch (err: any) {
      setCacheError(err.message || 'Failed to invalidate vacancies cache.');
    } finally {
      setClearingCache(false);
      setTimeout(() => {
        setCacheSuccess(null);
      }, 4000);
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

    // Cascading Hierarchy ID Matching
    const matchesBg = orgSelection.business_group_id == null || job.business_group_id === orgSelection.business_group_id;
    const matchesComp = orgSelection.company_id == null || job.company_id === orgSelection.company_id;
    const matchesLoc = orgSelection.location_id == null || job.location_id === orgSelection.location_id;
    const matchesMainDept = orgSelection.main_department_id == null || job.main_department_id === orgSelection.main_department_id;
    const matchesDeptId = orgSelection.department_id == null || job.department_id === orgSelection.department_id;
    const matchesDesig = orgSelection.designation_id == null || job.designation_id === orgSelection.designation_id;

    return matchesQuery && matchesDept && matchesDomain && matchesBg && matchesComp && matchesLoc && matchesMainDept && matchesDeptId && matchesDesig;
  });

  const renderJobCard = ({ item }: { item: JobOpening }) => {
    const title = item.title || 'Untitled Vacancy';
    const dept = item.department;
    const vacancyId = item.id;
    const salaryText = formatSalary(item);
    const expText = formatExperience(item);
    const displayedSkills = item.required_skills?.slice(0, 4) || [];
    const remainingSkillsCount = (item.required_skills?.length || 0) - 4;

    return (
      <View className="flex-1" style={numColumns > 1 ? { maxWidth: `${100 / numColumns}%` } : {}}>
        <Card className="flex-1 mb-3 mx-1 p-3.5 bg-surface border-border">
          {/* Header */}
          <View className="mb-2.5">
            <View className="flex-row items-center justify-between mb-1">
              <Text className="text-[11px] font-sans-bold text-primary uppercase tracking-wider">
                {vacancyId ? `ID #${vacancyId}` : 'Active'}
              </Text>
              {dept && (
                <View className="flex-row items-center gap-1 bg-background border border-border px-1.5 py-0.5 rounded">
                  <Briefcase size={10} color={COLORS.textMuted} />
                  <Text className="text-[11px] font-sans-medium text-text-muted" numberOfLines={1}>
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
          <View className="flex-row gap-2.5 mb-2.5">
            <View className="flex-1 bg-background border border-border rounded p-1.5">
              <Text className="text-[11px] font-sans-bold text-text-muted uppercase tracking-wider mb-0.5">Exp</Text>
              <Text className="text-[11px] font-sans-medium text-text-primary" numberOfLines={1}>{expText}</Text>
            </View>
            <View className="flex-1 bg-background border border-border rounded p-1.5">
              <Text className="text-[11px] font-sans-bold text-text-muted uppercase tracking-wider mb-0.5">Salary</Text>
              <Text className="text-[11px] font-sans-medium text-text-primary" numberOfLines={1}>{salaryText}</Text>
            </View>
          </View>

          {/* Required Skills */}
          {displayedSkills.length > 0 && (
            <View className="mb-3">
              <View className="flex-row flex-wrap gap-1">
                {displayedSkills.map((skill, idx) => (
                  <View key={idx} className="bg-background border border-border px-1.5 py-0.5 rounded">
                    <Text className="text-[11px] font-sans text-text-muted">{skill}</Text>
                  </View>
                ))}
                {remainingSkillsCount > 0 && (
                  <View className="bg-background border border-border px-1.5 py-0.5 rounded">
                    <Text className="text-[11px] font-sans text-text-faint">+{remainingSkillsCount}</Text>
                  </View>
                )}
              </View>
            </View>
          )}

          {/* Flex spacer to push footer to bottom */}
          <View className="flex-1" />

          {/* Footer Actions with 44px touch targets */}
          <View className="flex-row gap-2 pt-2.5 border-t border-border">
            <Pressable
              onPress={() => handleOpenDetails(item.id)}
              className="flex-1 bg-surface border border-border min-h-[44px] rounded items-center justify-center active:bg-background"
              accessibilityRole="button"
              accessibilityLabel="View Vacancy Details"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Text className="text-xs font-sans-semibold text-text-primary">View Details</Text>
            </Pressable>
            <Pressable
              onPress={() => handleOpenRecommendations(vacancyId)}
              className="flex-1 flex-row bg-primary/10 border border-primary/20 min-h-[44px] rounded items-center justify-center gap-1 active:bg-primary/20"
              accessibilityRole="button"
              accessibilityLabel="View AI Recommendations & Match Insights"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Sparkles size={12} color={COLORS.primary} />
              <Text className="text-xs font-sans-semibold text-primary">AI Insights</Text>
            </Pressable>
          </View>
        </Card>
      </View>
    );
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Job Vacancies' }]} />
      {/* Responsive Header */}
      <View className="flex-col sm:flex-row items-start sm:items-center justify-between px-4 py-3 bg-surface border-b border-border gap-2">
        <View>
          <Text className="text-base font-sans-bold text-text-primary">Active Job Vacancies</Text>
          <Text className="text-[11px] font-sans text-text-muted">
            {filteredJobs.length} active vacancies {jobs.length > 0 && `(${jobs.length} total catalogued)`}
          </Text>
        </View>
        <View className="flex-row items-center gap-2 self-end sm:self-auto">
          <Button
            label="Refresh"
            variant="ghost"
            size="sm"
            onPress={refreshJobs}
            disabled={loading}
          />
          <Button
            label={clearingCache ? 'Purging...' : 'Purge Cache'}
            variant="secondary"
            size="sm"
            icon={<RefreshCw size={12} color={COLORS.textMuted} />}
            onPress={() => setConfirmPurgeModalVisible(true)}
            loading={clearingCache}
            disabled={clearingCache}
          />
        </View>
      </View>

      <View className="flex-1 px-4 pt-3">
        {cacheSuccess && (
          <Card className="bg-success/10 border-success/30 flex-row items-center gap-2 mb-3 p-3">
            <CheckCircle size={14} color={COLORS.success} />
            <Text className="text-xs font-sans-semibold text-success flex-1">
              {cacheSuccess}
            </Text>
            <Pressable onPress={() => setCacheSuccess(null)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
              <X size={14} color={COLORS.success} />
            </Pressable>
          </Card>
        )}

        {cacheError && (
          <View className="mb-3">
            <ErrorBanner title="Cache Invalidation Error" message={cacheError} />
          </View>
        )}

        {/* Search & Filters Panel */}
        <Card className="mb-4 gap-3 bg-surface border-border">
          <TextField
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="Search by job title, department, or skill..."
          />
          <View className="flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
            <Pressable
              onPress={() => setShowHierarchyFilter(!showHierarchyFilter)}
              className="flex-row items-center gap-1.5 bg-primary/10 px-2.5 py-1.5 rounded border border-primary/20 min-h-[36px]"
              accessibilityRole="button"
              hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
            >
              <Briefcase size={14} color={COLORS.primary} />
              <Text className="text-xs font-sans-semibold text-primary">
                {showHierarchyFilter ? 'Hide Organization Hierarchy Filter' : 'Filter by Organization Hierarchy'}
              </Text>
            </Pressable>
            {Object.values(orgSelection).some((v) => v != null) && (
              <Pressable
                onPress={() => setOrgSelection({})}
                className="bg-surface px-2.5 py-1.5 rounded border border-border min-h-[36px] items-center justify-center"
                accessibilityRole="button"
                hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
              >
                <Text className="text-[11px] font-sans-medium text-danger">Reset Hierarchy Filter</Text>
              </Pressable>
            )}
          </View>

          {showHierarchyFilter && (
            <OrganizationHierarchySelector
              value={orgSelection}
              onChange={setOrgSelection}
            />
          )}
        </Card>

        {/* Loading state */}
        {loading ? (
          <View className="flex-1 justify-center items-center py-16">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">Fetching job openings from backend...</Text>
          </View>
        ) : error ? (
          <View className="gap-2">
            <ErrorBanner title="Vacancy Load Error" message={error} />
            <View className="self-start">
              <Button label="Try Refreshing" variant="ghost" size="sm" onPress={refreshJobs} />
            </View>
          </View>
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
                subtitle="Try adjusting your search criteria or reset active filters."
              />
            }
          />
        )}
      </View>

      {/* Destructive Cache Purge Modal */}
      <Modal animationType="fade" transparent={true} visible={confirmPurgeModalVisible} onRequestClose={() => setConfirmPurgeModalVisible(false)}>
        <View className="items-center justify-center flex-1 px-4 bg-black/60">
          <Card className="w-full max-w-md gap-3 p-4 bg-surface border-border">
            <View className="flex-row items-center justify-between pb-2 border-b border-border">
              <View className="flex-row items-center gap-2">
                <AlertTriangle size={16} color={COLORS.danger} />
                <Text className="text-sm font-sans-bold text-text-primary">Purge Vacancies Cache</Text>
              </View>
              <Pressable
                onPress={() => setConfirmPurgeModalVisible(false)}
                className="min-h-[36px] min-w-[36px] items-center justify-center"
                hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
              >
                <X size={16} color={COLORS.textMuted} />
              </Pressable>
            </View>
            <Text className="font-sans text-xs leading-5 text-text-primary">
              Are you sure you want to purge the cached job vacancies?
            </Text>
            <View className="bg-danger/10 p-2.5 rounded-md border border-danger/30">
              <Text className="text-[11px] font-sans text-danger leading-4">
                ⚠️ This forces the backend to evict cached job catalog schemas and re-query primary persistent vacancy storage.
              </Text>
            </View>
            <View className="flex-row justify-end gap-2 mt-2">
              <Button label="Cancel" variant="ghost" size="sm" onPress={() => setConfirmPurgeModalVisible(false)} />
              <Button label="Purge Cache" variant="destructive" size="sm" onPress={handleConfirmPurgeCache} />
            </View>
          </Card>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
