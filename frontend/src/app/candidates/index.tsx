import React, { useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { UserCheck, FileText, Search, RefreshCw, Mail, Phone } from 'lucide-react-native';
import { useCandidates } from '@/hooks/useCandidates';
import { useDebounce } from '@/hooks/useDebounce';
import { CandidateSummary } from '@/types/api';
import { Card, DenseRow, TextField, Badge, Button, EmptyState, SegmentedControl } from '@/components/ui';
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
    const titleNode = item.full_name ? (
      <Text numberOfLines={1} className="text-sm font-sans-medium text-text-primary">
        {item.full_name}
      </Text>
    ) : (
      <Text numberOfLines={1} className="text-sm font-sans-medium text-text-faint">
        Name not detected
      </Text>
    );

    const emailText = item.email || "—";
    const phoneText = item.phone || "—";

    const subtitleNode = (
      <View className="gap-1 mt-0.5">
        <View className="flex-row items-center gap-3">
          <View className="flex-row items-center gap-1">
            <Mail size={12} color="#9CA3AF" />
            <Text numberOfLines={1} className="text-xs font-sans text-text-muted">{emailText}</Text>
          </View>
          <View className="flex-row items-center gap-1 flex-1">
            <Phone size={12} color="#9CA3AF" />
            <Text numberOfLines={1} className="text-xs font-sans text-text-muted">{phoneText}</Text>
          </View>
        </View>
        {item.best_match?.job_title && (
          <Text numberOfLines={1} className="text-xs font-sans text-text-muted">
            Role: {item.best_match.job_title}{item.primary_department ? ` (${item.primary_department})` : ''}
          </Text>
        )}
        <Text numberOfLines={1} className="text-[11px] font-sans text-text-faint">
          File: {item.filename}
        </Text>
      </View>
    );

    return (
      <View className="mb-2">
        <DenseRow
          title={titleNode}
          subtitle={subtitleNode}
          onPress={() => router.push(`/candidates/${encodeURIComponent(item.id)}` as any)}
          trailing={
            item.best_match?.score != null ? (
              <ScoreBadge
                score={item.best_match.score}
                classification={item.best_match.classification || 'LOW'}
              />
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
          onPress={() => handleSearchTrigger(searchQuery, filterDept)}
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
              handleSearchTrigger(text, filterDept);
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
            label=""
            value={filterDept}
            onChangeText={(dept) => {
              setFilterDept(dept);
              handleSearchTrigger(searchQuery, dept);
            }}
            placeholder="Filter by specific department (e.g. Engineering)..."
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
