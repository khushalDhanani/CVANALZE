import React, { useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Text,
  View,
} from 'react-native';
import { Briefcase, Target, CheckCircle, IndianRupee } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { jobsService } from '@/services/jobsService';
import { useJobs } from '@/hooks/useJobs';
import { JobOpening } from '@/types/api';
import { TextField, Card, Button, Badge, EmptyState } from '@/components/ui';
import { COLORS } from '@/constants/colors';

export default function VacanciesScreen() {
  const { jobs, loading, error, refreshJobs } = useJobs();
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [clearingCache, setClearingCache] = useState<boolean>(false);
  const [cacheMessage, setCacheMessage] = useState<string | null>(null);

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
    const titleMatch = (job.VacancyTitle || '').toLowerCase().includes(query);
    const deptMatch = (job.DepartmentName || '').toLowerCase().includes(query);
    const mandatoryMatch = (job.MandatorySkillsReq || '').toLowerCase().includes(query);
    const skillsMatch = (job.SkillsReq || '').toLowerCase().includes(query);
    return titleMatch || deptMatch || mandatoryMatch || skillsMatch;
  });

  const formatRupees = (val: number) => {
    if (!val || val <= 0) return null;
    if (val <= 100) {
      return `₹${val} LPA`;
    }
    return `₹${val.toLocaleString('en-IN')}`;
  };

  const formatSalary = (item: any) => {
    const min = item.SalaryMin ?? item.min_ctc;
    const max = item.SalaryMax ?? item.max_ctc;

    const formattedMin = min ? formatRupees(min) : null;
    const formattedMax = max ? formatRupees(max) : null;

    if (formattedMin && formattedMax) {
      return `${formattedMin} - ${formattedMax}`;
    }
    if (formattedMin) return `From ${formattedMin}`;
    if (formattedMax) return `Up to ${formattedMax}`;
    return 'Not Specified';
  };

  const formatExperience = (item: any) => {
    const min = item.ExperienceYearReqMin ?? item.min_experience_years;
    const max = item.ExperienceYearReqMax ?? item.max_experience_years;

    if (min != null && max != null && (min > 0 || max > 0)) {
      if (min === max) return `${min} Yrs Exp`;
      return `${min} - ${max} Yrs Exp`;
    }
    if (min != null && min > 0) return `${min}+ Yrs Exp`;
    if (max != null && max > 0) return `Up to ${max} Yrs Exp`;
    return 'Any Experience';
  };

  const renderJobCard = ({ item }: { item: JobOpening }) => {
    const title = item.VacancyTitle || (item as any).title || 'Untitled Vacancy';
    const dept = item.DepartmentName || (item as any).department;
    const vacancyId = item.VacancyID || (item as any).id;
    const salaryText = formatSalary(item);

    return (
      <Card className="mb-3">
        <View className="flex-row justify-between items-start mb-2">
          <View className="flex-1 pr-2">
            <Text className="text-xs font-sans-bold text-primary">
              {vacancyId ? `ID #${vacancyId}` : 'Active Opening'}
            </Text>
            <Text className="text-base font-sans-bold text-text-primary">
              {title}
            </Text>
            {dept && (
              <View className="flex-row items-center gap-1 mt-0.5">
                <Briefcase size={12} color={COLORS.textMuted} />
                <Text className="text-xs font-sans-medium text-text-muted">
                  {dept}
                </Text>
              </View>
            )}
          </View>
          <Badge label={formatExperience(item)} tone="info" />
        </View>

        {/* Mandatory Skills */}
        {item.MandatorySkillsReq && (
          <View className="mb-2 p-2 bg-danger/10 border border-danger/30 rounded-md">
            <Text className="text-[10px] font-sans-bold text-danger uppercase tracking-wider mb-0.5">
              Mandatory Skills
            </Text>
            <Text className="text-xs font-sans-medium text-danger">
              {item.MandatorySkillsReq}
            </Text>
          </View>
        )}

        {/* Required Skills */}
        {(item.SkillsReq || (item as any).required_skills?.length > 0) && (
          <View className="mb-2">
            <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider mb-0.5">
              Skills Required
            </Text>
            <Text className="text-xs font-sans text-text-primary">
              {item.SkillsReq || (item as any).required_skills?.join(', ')}
            </Text>
          </View>
        )}

        {/* Salary & Domain */}
        <View className="flex-row justify-between items-center pt-2 border-t border-border mt-1">
          <View className="flex-row items-center gap-1">
            <IndianRupee size={11} color={COLORS.textFaint} />
            <Text className="text-[11px] font-sans-medium text-text-muted">
              Salary: {salaryText}
            </Text>
          </View>
          {item.TargetDomainExperience && (
            <View className="flex-row items-center gap-1 truncate max-w-[160px]">
              <Target size={12} color={COLORS.textFaint} />
              <Text className="text-[11px] font-sans-medium text-text-muted truncate">
                {item.TargetDomainExperience}
              </Text>
            </View>
          )}
        </View>
      </Card>
    );
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
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

        {/* Search Input */}
        <View className="mb-4">
          <TextField
            label=""
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="Search by job title, department, or skill..."
          />
        </View>

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
            data={filteredJobs}
            keyExtractor={(item, index) => (item?.VacancyID ? String(item.VacancyID) : `job-${index}`)}
            renderItem={renderJobCard}
            contentContainerStyle={{ paddingBottom: 24 }}
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
