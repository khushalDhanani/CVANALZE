import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { UserCheck, FileText, Search, RefreshCw, Mail, Phone, MapPin, Building, Briefcase } from 'lucide-react-native';
import { useCandidates } from '@/hooks/useCandidates';
import { useDebounce } from '@/hooks/useDebounce';
import { usePageTitle } from '@/hooks/usePageTitle';
import { CandidateSummary } from '@/types/api';
import {
  Card,
  DenseRow,
  TextField,
  Badge,
  Button,
  EmptyState,
  FieldConfidenceView,
  Breadcrumbs,
  ErrorBanner,
} from '@/components/ui';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { VacancyMatchStatusBadge, normalizeCanonicalMatchStatus, resolveVacancyFitScore } from '@/components/ui/VacancyMatchStatusBadge';
import { COLORS } from '@/constants/colors';

const CLASSIFICATION_OPTIONS = [
  { value: 'ALL', label: 'All Matches' },
  { value: 'MATCHED', label: 'Matched' },
  { value: 'POTENTIAL_MATCH', label: 'Potential' },
  { value: 'NO_STRONG_MATCH', label: 'No Strong Match' },
  { value: 'UNMATCHED', label: 'Unmatched' },
];

export default function CandidateListScreen() {
  usePageTitle('Candidate Directory | AIRIS');
  const router = useRouter();
  const params = useLocalSearchParams<{
    query?: string;
    classification?: string;
    department?: string;
    location?: string;
    skills?: string;
    education?: string;
    min_experience?: string;
    max_experience?: string;
    limit?: string;
  }>();

  const { candidates, loading, error, searchMode, totalFound, refreshCandidates } = useCandidates();

  const [searchQuery, setSearchQuery] = useState<string>(params.query || '');
  const [filterClassification, setFilterClassification] = useState<string>(params.classification || 'ALL');
  const [filterDept, setFilterDept] = useState<string>(params.department || '');
  const [filterLocation, setFilterLocation] = useState<string>(params.location || '');
  const [filterSkills, setFilterSkills] = useState<string>(params.skills || '');
  const [filterEducation, setFilterEducation] = useState<string>(params.education || '');
  const [filterMinExp, setFilterMinExp] = useState<string>(params.min_experience || '');
  const [filterMaxExp, setFilterMaxExp] = useState<string>(params.max_experience || '');
  const [filterLimit, setFilterLimit] = useState<string>(params.limit || '50');

  const debouncedSearch = useDebounce(searchQuery, 300);
  const debouncedDept = useDebounce(filterDept, 300);
  const debouncedLocation = useDebounce(filterLocation, 300);
  const debouncedSkills = useDebounce(filterSkills, 300);
  const debouncedEducation = useDebounce(filterEducation, 300);
  const debouncedMinExp = useDebounce(filterMinExp, 300);
  const debouncedMaxExp = useDebounce(filterMaxExp, 300);
  const debouncedLimit = useDebounce(filterLimit, 300);

  // Strict inline numeric range validations
  const parsedMinExp = parseFloat(filterMinExp);
  const minExpError =
    filterMinExp.trim() && (isNaN(parsedMinExp) || !Number.isFinite(parsedMinExp) || parsedMinExp < 0)
      ? 'Must be ≥ 0'
      : undefined;

  const parsedMaxExp = parseFloat(filterMaxExp);
  const maxExpError =
    filterMaxExp.trim() &&
    (isNaN(parsedMaxExp) ||
      !Number.isFinite(parsedMaxExp) ||
      parsedMaxExp < 0 ||
      (!isNaN(parsedMinExp) && parsedMaxExp < parsedMinExp))
      ? 'Must be ≥ Min Exp'
      : undefined;

  const parsedLimit = parseInt(filterLimit, 10);
  const limitError =
    filterLimit.trim() &&
    (isNaN(parsedLimit) || !Number.isFinite(parsedLimit) || parsedLimit < 1 || parsedLimit > 100)
      ? 'Integer 1–100'
      : undefined;

  // Synchronize state changes with URL query parameters deliberately (clearing unused keys)
  useEffect(() => {
    router.setParams({
      query: debouncedSearch || undefined,
      classification: filterClassification !== 'ALL' ? filterClassification : undefined,
      department: debouncedDept || undefined,
      location: debouncedLocation || undefined,
      skills: debouncedSkills || undefined,
      education: debouncedEducation || undefined,
      min_experience: debouncedMinExp || undefined,
      max_experience: debouncedMaxExp || undefined,
      limit: debouncedLimit && debouncedLimit !== '50' ? debouncedLimit : undefined,
    });
  }, [
    debouncedSearch,
    filterClassification,
    debouncedDept,
    debouncedLocation,
    debouncedSkills,
    debouncedEducation,
    debouncedMinExp,
    debouncedMaxExp,
    debouncedLimit,
  ]);

  // Unified single search payload builder
  const buildSearchPayload = React.useCallback(() => ({
    query: debouncedSearch.trim() || undefined,
    department: debouncedDept.trim() || undefined,
    location: debouncedLocation.trim() || undefined,
    education: debouncedEducation.trim() || undefined,
    skills: debouncedSkills
      ? debouncedSkills.split(',').map((s) => s.trim()).filter(Boolean)
      : undefined,
    min_experience: !minExpError && debouncedMinExp ? parseFloat(debouncedMinExp) : undefined,
    max_experience: !maxExpError && debouncedMaxExp ? parseFloat(debouncedMaxExp) : undefined,
    limit: !limitError && debouncedLimit ? parseInt(debouncedLimit, 10) : 50,
  }), [
    debouncedSearch,
    debouncedDept,
    debouncedLocation,
    debouncedEducation,
    debouncedSkills,
    debouncedMinExp,
    debouncedMaxExp,
    debouncedLimit,
    minExpError,
    maxExpError,
    limitError,
  ]);

  useEffect(() => {
    refreshCandidates(buildSearchPayload());
  }, [buildSearchPayload, refreshCandidates]);

  const handleClearAllFilters = () => {
    setSearchQuery('');
    setFilterClassification('ALL');
    setFilterDept('');
    setFilterLocation('');
    setFilterSkills('');
    setFilterEducation('');
    setFilterMinExp('');
    setFilterMaxExp('');
    setFilterLimit('50');
  };

  const hasActiveFilters = Boolean(
    searchQuery.trim() ||
      filterClassification !== 'ALL' ||
      filterDept.trim() ||
      filterLocation.trim() ||
      filterSkills.trim() ||
      filterEducation.trim() ||
      filterMinExp.trim() ||
      filterMaxExp.trim() ||
      (filterLimit.trim() && filterLimit !== '50')
  );

  const handleOpenCandidateDetail = (candId: string) => {
    const queryParams: Record<string, string> = {};
    if (searchQuery) queryParams.query = searchQuery;
    if (filterClassification !== 'ALL') queryParams.classification = filterClassification;
    if (filterDept) queryParams.department = filterDept;
    if (filterLocation) queryParams.location = filterLocation;
    if (filterSkills) queryParams.skills = filterSkills;
    if (filterEducation) queryParams.education = filterEducation;
    if (filterMinExp) queryParams.min_experience = filterMinExp;
    if (filterMaxExp) queryParams.max_experience = filterMaxExp;
    if (filterLimit && filterLimit !== '50') queryParams.limit = filterLimit;

    router.push({
      pathname: '/candidates/[id]',
      params: { id: candId, ...queryParams },
    } as any);
  };

  const filteredCandidates = (candidates || []).filter((cand) => {
    if (!cand) return false;
    const rawStatus =
      cand.best_match?.vacancy_match_status ||
      cand.best_match?.match_status ||
      cand.best_match?.classification;
    const canonicalStatus = normalizeCanonicalMatchStatus(rawStatus);

    if (filterClassification === 'ALL') return true;
    if (filterClassification === 'UNMATCHED') {
      return (
        canonicalStatus === 'NO_STRONG_MATCH' ||
        canonicalStatus === 'NO_ACTIVE_VACANCIES' ||
        !rawStatus
      );
    }
    return canonicalStatus === filterClassification;
  });

  const renderCandidateRow = ({ item }: { item: CandidateSummary }) => {
    const nameTier = item.name_confidence_tier || item.field_confidence_tiers?.name;
    const locTier = item.location_confidence_tier || item.field_confidence_tiers?.location;
    const jobTitleTier = item.job_title_confidence_tier || item.field_confidence_tiers?.job_title;
    const compTier = item.company_name_confidence_tier || item.field_confidence_tiers?.company_name;

    const jobTitleVal = item.job_title || item.best_match?.job_title;

    const titleNode = (
      <FieldConfidenceView
        fieldName="name"
        value={item.full_name}
        tier={nameTier}
        fallbackLabel="Name not detected"
      />
    );

    const emailText = item.email || '—';
    const phoneText = item.phone || '—';

    const subtitleNode = (
      <View className="gap-1 mt-0.5">
        <View className="flex-row items-center gap-3 flex-wrap">
          <View className="flex-row items-center gap-1">
            <Mail size={12} color={COLORS.textFaint} />
            <Text numberOfLines={1} className="text-xs font-sans text-text-muted">{emailText}</Text>
          </View>
          <View className="flex-row items-center gap-1">
            <Phone size={12} color={COLORS.textFaint} />
            <Text numberOfLines={1} className="text-xs font-sans text-text-muted">{phoneText}</Text>
          </View>
        </View>

        {/* 4 Rule-Config Fields: Job Title, Company, Location */}
        <View className="gap-1 mt-0.5">
          <FieldConfidenceView
            fieldName="job_title"
            value={jobTitleVal}
            tier={jobTitleTier}
            icon={<Briefcase size={12} color={COLORS.textFaint} />}
            fallbackLabel="Job title not detected"
            textClassName="text-xs"
          />
          <View className="flex-row items-center gap-3 flex-wrap">
            <FieldConfidenceView
              fieldName="company_name"
              value={item.company_name}
              tier={compTier}
              icon={<Building size={12} color={COLORS.textFaint} />}
              fallbackLabel="Company not detected"
              textClassName="text-xs"
            />
            <FieldConfidenceView
              fieldName="location"
              value={item.location}
              tier={locTier}
              icon={<MapPin size={12} color={COLORS.textFaint} />}
              fallbackLabel="Location not detected"
              textClassName="text-xs"
            />
          </View>
        </View>

        <Text numberOfLines={1} className="text-[11px] font-sans text-text-faint mt-0.5">
          File: {item.filename}
        </Text>
      </View>
    );

    const isDomainCapped = Boolean(item.best_match?.domain_mismatch_capped);
    const matchStatus =
      item.best_match?.vacancy_match_status ||
      item.best_match?.match_status ||
      item.best_match?.classification;
    const matchScore = resolveVacancyFitScore(item.best_match);

    return (
      <DenseRow
        title={titleNode}
        subtitle={subtitleNode}
        onPress={() => handleOpenCandidateDetail(item.id)}
        trailing={
          item.best_match ? (
            <View className="items-end gap-1">
              <VacancyMatchStatusBadge status={matchStatus} score={matchScore} />
              {isDomainCapped && (
                <Badge label="Cross-domain match — score capped" tone="warning" />
              )}
            </View>
          ) : (
            <Badge
              label={item.page_count != null ? `${item.page_count} pg` : '—'}
              tone="neutral"
            />
          )
        }
      />
    );
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Candidate Directory' }]} />

      {/* Responsive PageHeader */}
      <View className="flex-col sm:flex-row items-start sm:items-center justify-between px-3 py-2.5 bg-surface border-b border-border gap-3">
        <View>
          <View className="flex-row items-center gap-2">
            <Text className="text-base font-sans-bold text-text-primary">Candidate Directory</Text>
            {searchQuery.trim() !== '' && (
              <Badge
                label={searchMode === 'semantic' ? 'Semantic Search' : 'Keyword Search'}
                tone={searchMode === 'semantic' ? 'success' : 'neutral'}
              />
            )}
          </View>
          <Text className="text-[11px] font-sans text-text-muted">
            Showing {filteredCandidates.length} of {totalFound || candidates.length} candidate records matching filters
          </Text>
        </View>
        <Button
          label="Refresh"
          variant="secondary"
          size="sm"
          onPress={() => refreshCandidates(buildSearchPayload())}
          disabled={loading}
        />
      </View>

      <View className="flex-1 px-3 pt-3">
        {/* Search Input without unnecessary blank label space */}
        <View className="mb-3">
          <TextField
            value={searchQuery}
            onChangeText={setSearchQuery}
            placeholder="Search by candidate name, skill, title or natural language (e.g. Senior Python Developer)..."
            onSubmitEditing={() => refreshCandidates(buildSearchPayload())}
          />
        </View>

        {/* Scrollable Filter Chips for Classification */}
        <View className="mb-3">
          <ScrollView horizontal showsHorizontalScrollIndicator={false} className="flex-row">
            <View className="flex-row gap-2 py-0.5">
              {CLASSIFICATION_OPTIONS.map((opt) => {
                const isSelected = filterClassification === opt.value;
                return (
                  <Pressable
                    key={opt.value}
                    onPress={() => setFilterClassification(opt.value)}
                    accessibilityRole="button"
                    accessibilityState={{ selected: isSelected }}
                    hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                    className={`px-3 py-1.5 rounded-full border min-h-[36px] justify-center ${
                      isSelected
                        ? 'bg-primary border-primary'
                        : 'bg-surface border-border active:bg-surface-hover'
                    }`}
                  >
                    <Text
                      className={`text-xs ${
                        isSelected ? 'text-white font-sans-bold' : 'text-text-primary font-sans-medium'
                      }`}
                    >
                      {opt.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </ScrollView>
        </View>

        {/* Responsive Filter Grid */}
        <View className="mb-4 gap-2.5">
          <View className="flex-col sm:flex-row gap-2.5">
            <View className="flex-1 min-w-[140px]">
              <TextField
                label="Department / Role"
                value={filterDept}
                onChangeText={setFilterDept}
                placeholder="e.g. Engineering..."
              />
            </View>
            <View className="flex-1 min-w-[140px]">
              <TextField
                label="Location"
                value={filterLocation}
                onChangeText={setFilterLocation}
                placeholder="e.g. Remote, NY..."
              />
            </View>
          </View>

          <View className="flex-col sm:flex-row gap-2.5">
            <View className="flex-[2] min-w-[180px]">
              <TextField
                label="Required Skills (comma separated)"
                value={filterSkills}
                onChangeText={setFilterSkills}
                placeholder="e.g. Python, React, SQL..."
              />
            </View>
            <View className="flex-1 min-w-[90px]">
              <TextField
                label="Limit"
                value={filterLimit}
                onChangeText={setFilterLimit}
                placeholder="50"
                keyboardType="numeric"
                error={limitError}
              />
            </View>
          </View>

          <View className="flex-col sm:flex-row gap-2.5">
            <View className="flex-1 min-w-[110px]">
              <TextField
                label="Min Exp (Yrs)"
                value={filterMinExp}
                onChangeText={setFilterMinExp}
                placeholder="e.g. 2"
                keyboardType="numeric"
                error={minExpError}
              />
            </View>
            <View className="flex-1 min-w-[110px]">
              <TextField
                label="Max Exp (Yrs)"
                value={filterMaxExp}
                onChangeText={setFilterMaxExp}
                placeholder="e.g. 5"
                keyboardType="numeric"
                error={maxExpError}
              />
            </View>
            <View className="flex-1 min-w-[110px]">
              <TextField
                label="Education"
                value={filterEducation}
                onChangeText={setFilterEducation}
                placeholder="e.g. Bachelor"
              />
            </View>
          </View>
        </View>

        {/* Loading / Error / Data state */}
        {loading ? (
          <View className="flex-1 justify-center items-center py-12">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">
              Loading candidate directory...
            </Text>
          </View>
        ) : error ? (
          <View className="gap-2">
            <ErrorBanner title="Query Error" message={error} />
            <View className="self-start">
              <Button
                label="Try Again"
                variant="ghost"
                size="sm"
                onPress={() => refreshCandidates(buildSearchPayload())}
              />
            </View>
          </View>
        ) : (
          <FlatList
            data={filteredCandidates}
            keyExtractor={(item, index) => item.id || `cand_${index}`}
            renderItem={renderCandidateRow}
            ItemSeparatorComponent={() => <View className="h-2" />}
            contentContainerStyle={{ paddingBottom: 24 }}
            onRefresh={() => refreshCandidates(buildSearchPayload())}
            refreshing={loading}
            ListEmptyComponent={
              candidates.length === 0 ? (
                <EmptyState
                  title="No Candidates Collected Yet"
                  subtitle="Upload or analyze CVs to populate the candidate directory."
                />
              ) : (
                <View className="items-center py-6 gap-3">
                  <EmptyState
                    title="No Matching Candidate Records"
                    subtitle="No candidates match the active search criteria and filter rules."
                  />
                  <Button
                    label="Clear All Filters"
                    variant="outline"
                    size="sm"
                    onPress={handleClearAllFilters}
                  />
                </View>
              )
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}
