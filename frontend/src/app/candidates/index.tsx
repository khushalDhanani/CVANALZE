import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { UserCheck, FileText, Search, RefreshCw, Mail, Phone, MapPin, Building, Briefcase } from 'lucide-react-native';
import { useCandidates } from '@/hooks/useCandidates';
import { useDebounce } from '@/hooks/useDebounce';
import { CandidateSummary } from '@/types/api';
import { Card, DenseRow, TextField, Badge, Button, EmptyState, SegmentedControl, FieldConfidenceView } from '@/components/ui';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { COLORS } from '@/constants/colors';

export default function CandidateListScreen() {
  const router = useRouter();
  const { candidates, loading, error, searchMode, refreshCandidates } = useCandidates();
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [filterClassification, setFilterClassification] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'UNMATCHED'>('ALL');
  const [filterDept, setFilterDept] = useState<string>('');

  const debouncedSearch = useDebounce(searchQuery, 300);
  const debouncedDept = useDebounce(filterDept, 300);

  useEffect(() => {
    refreshCandidates({
      query: debouncedSearch || undefined,
      department: debouncedDept || undefined,
    });
  }, [debouncedSearch, debouncedDept, refreshCandidates]);

  const filteredCandidates = (candidates || []).filter((cand) => {
    if (!cand) return false;
    const candClassification = cand.best_match?.classification;
    const matchClassification =
      filterClassification === 'ALL' ||
      (filterClassification === 'UNMATCHED' && !candClassification) ||
      candClassification === filterClassification;

    return matchClassification;
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

    const emailText = item.email || "—";
    const phoneText = item.phone || "—";

    const subtitleNode = (
      <View className="gap-1 mt-0.5">
        <View className="flex-row items-center gap-3 flex-wrap">
          <View className="flex-row items-center gap-1">
            <Mail size={12} color="#9CA3AF" />
            <Text numberOfLines={1} className="text-xs font-sans text-text-muted">{emailText}</Text>
          </View>
          <View className="flex-row items-center gap-1">
            <Phone size={12} color="#9CA3AF" />
            <Text numberOfLines={1} className="text-xs font-sans text-text-muted">{phoneText}</Text>
          </View>
        </View>

        {/* 4 Rule-Config Fields: Job Title, Company, Location */}
        <View className="gap-1 mt-0.5">
          <FieldConfidenceView
            fieldName="job_title"
            value={jobTitleVal}
            tier={jobTitleTier}
            icon={<Briefcase size={12} color="#9CA3AF" />}
            fallbackLabel="Job title not detected"
            textClassName="text-xs"
          />
          <View className="flex-row items-center gap-3 flex-wrap">
            <FieldConfidenceView
              fieldName="company_name"
              value={item.company_name}
              tier={compTier}
              icon={<Building size={12} color="#9CA3AF" />}
              fallbackLabel="Company not detected"
              textClassName="text-xs"
            />
            <FieldConfidenceView
              fieldName="location"
              value={item.location}
              tier={locTier}
              icon={<MapPin size={12} color="#9CA3AF" />}
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

    return (
      <View className="mb-2">
        <DenseRow
          title={titleNode}
          subtitle={subtitleNode}
          onPress={() => router.push(`/candidates/${encodeURIComponent(item.id)}` as any)}
          trailing={
            item.best_match?.score != null ? (
              <View className="items-end gap-1">
                <ScoreBadge
                  score={item.best_match.score}
                  classification={item.best_match.classification || 'LOW'}
                />
                {isDomainCapped && (
                  <Badge label="Cross-domain match — score capped" tone="warning" />
                )}
              </View>
            ) : (
              <Badge label={`${item.page_count || 1} pg`} tone="neutral" />
            )
          }
        />
      </View>
    );
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      {/* Sticky Header */}
      <View className="flex-row items-center justify-between px-3 py-2 bg-surface border-b border-border">
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
            {filteredCandidates.length} of {candidates.length} candidate records matching filters
          </Text>
        </View>
        <Button
          label="Refresh"
          variant="secondary"
          size="sm"
          onPress={() => refreshCandidates({ query: searchQuery || undefined, department: filterDept || undefined })}
        />
      </View>

      <View className="flex-1 px-3 pt-3">
        {/* Search Input */}
        <View className="mb-4">
          <TextField
            label=""
            value={searchQuery}
            onChangeText={(text) => {
              setSearchQuery(text);
            }}
            placeholder="Search by candidate name, skill, title or natural language (e.g. Senior Python Developer)..."
          />
        </View>

        {/* Filters */}
        <View className="mb-4 gap-3">
          <SegmentedControl
            options={[
              { value: 'ALL', label: 'All Matches' },
              { value: 'HIGH', label: 'High' },
              { value: 'MEDIUM', label: 'Medium' },
              { value: 'LOW', label: 'Low' },
              { value: 'UNMATCHED', label: 'Unmatched' }
            ]}
            value={filterClassification}
            onChange={(val) => setFilterClassification(val as 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'UNMATCHED')}
          />
          <TextField
            label="Department / Role Filter"
            value={filterDept}
            onChangeText={(text) => {
              setFilterDept(text);
            }}
            placeholder="e.g. Engineering, Sales..."
          />
        </View>

        {/* Loading state */}
        {loading ? (
          <View className="flex-1 justify-center items-center py-12">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">
              Loading candidate directory...
            </Text>
          </View>
        ) : error ? (
          <Card className="bg-danger/10 border-danger/30">
            <Text className="text-xs font-sans-medium text-danger">{error}</Text>
            <View className="mt-2 self-start">
              <Button label="Try Again" variant="ghost" onPress={() => refreshCandidates(searchQuery)} />
            </View>
          </Card>
        ) : (
          <FlatList
            data={filteredCandidates}
            keyExtractor={(item, index) => `${item.id}-${index}`}
            renderItem={renderCandidateRow}
            contentContainerStyle={{ paddingBottom: 24 }}
            onRefresh={() => refreshCandidates(searchQuery)}
            refreshing={loading}
            ListEmptyComponent={
              <EmptyState
                title="No candidates found"
                subtitle="Upload or analyze CVs to populate the candidate directory."
              />
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}
