import React, { useState } from 'react';
import { ActivityIndicator, FlatList, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { UserCheck, FileText, Search, RefreshCw } from 'lucide-react-native';
import { useCandidates } from '@/hooks/useCandidates';
import { CandidateSummary } from '@/types/api';
import { Card, DenseRow, TextField, Badge, Button, EmptyState } from '@/components/ui';
import { ScoreBadge } from '@/components/ui/ScoreBadge';

export default function CandidateListScreen() {
  const router = useRouter();
  const { candidates, loading, error, refreshCandidates } = useCandidates();
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filteredCandidates = (candidates || []).filter((cand) => {
    if (!cand) return false;
    const q = searchQuery.toLowerCase();
    const fname = (cand.filename || '').toLowerCase();
    const id = (cand.id || '').toLowerCase();
    const dept = (cand.primary_department || '').toLowerCase();
    const job = (cand.best_match?.job_title || '').toLowerCase();
    return fname.includes(q) || id.includes(q) || dept.includes(q) || job.includes(q);
  });

  const renderCandidateRow = ({ item }: { item: CandidateSummary }) => {
    const title = item.filename || item.id;
    const subtitle = item.best_match?.job_title
      ? `Top Role: ${item.best_match.job_title}${item.primary_department ? ` (${item.primary_department})` : ''}`
      : 'Parsed Candidate Record';

    return (
      <View className="mb-2">
        <DenseRow
          title={title}
          subtitle={subtitle}
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
          <Text className="text-base font-sans-bold text-text-primary">Candidate Directory</Text>
          <Text className="text-[11px] font-sans text-text-muted">
            {filteredCandidates.length} of {candidates.length} candidate records parsed
          </Text>
        </View>
        <Button
          label="Refresh"
          variant="secondary"
          size="sm"
          onPress={() => refreshCandidates(searchQuery)}
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
              refreshCandidates(text);
            }}
            placeholder="Search by candidate name, filename, department, or job title..."
          />
        </View>

        {/* Loading state */}
        {loading ? (
          <View className="flex-1 justify-center items-center py-12">
            <ActivityIndicator size="large" color="#4F46E5" />
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
