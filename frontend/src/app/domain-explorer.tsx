import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePageTitle } from '@/hooks/usePageTitle';
import { domainKnowledgeService } from '@/services/domainKnowledgeService';
import { DomainEquivalentResponse } from '@/types/api';
import { Card, Button, TextField, SegmentedControl, Badge, Breadcrumbs, DenseRow } from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { BookOpen, Search, Hash } from 'lucide-react-native';

export default function DomainExplorerScreen() {
  usePageTitle('Domain Explorer | AIRIS');

  const [categories, setCategories] = useState<string[]>([]);
  const [loadingCategories, setLoadingCategories] = useState(true);

  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('skills');
  const [threshold, setThreshold] = useState('0.82');
  const [limit, setLimit] = useState('5');
  
  const [results, setResults] = useState<DomainEquivalentResponse | null>(null);
  const [loadingResults, setLoadingResults] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    setLoadingCategories(true);
    try {
      const cats = await domainKnowledgeService.getCategories();
      setCategories(cats);
      if (cats.length > 0 && !cats.includes(selectedCategory)) {
        setSelectedCategory(cats[0]);
      }
    } catch (err) {
      console.warn('Failed to fetch domain categories', err);
    } finally {
      setLoadingCategories(false);
    }
  };

  const handleSearch = async () => {
    if (!searchTerm.trim()) return;
    setLoadingResults(true);
    setError(null);
    setResults(null);

    try {
      const data = await domainKnowledgeService.getEquivalents({
        term: searchTerm.trim(),
        category: selectedCategory,
        threshold: parseFloat(threshold) || 0.82,
        limit: parseInt(limit, 10) || 5,
      });
      setResults(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch semantic equivalents.');
    } finally {
      setLoadingResults(false);
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Domain Explorer' }]} />
      
      <View className="flex-row items-center justify-between px-3 py-2 bg-surface border-b border-border">
        <View className="flex-row items-center gap-2">
          <BookOpen size={18} color={COLORS.primary} />
          <View>
            <Text className="text-base font-sans-bold text-text-primary">Domain Explorer</Text>
            <Text className="text-[11px] font-sans text-text-muted">
              Semantic Equivalents & Domain Knowledge
            </Text>
          </View>
        </View>
      </View>

      <ScrollView className="flex-1 px-3 py-4">
        {/* Search Panel */}
        <Card className="gap-4 mb-4">
          <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
            Semantic Equivalents Lookup
          </Text>
          
          {loadingCategories ? (
            <ActivityIndicator size="small" color={COLORS.primary} />
          ) : (
            <View className="gap-3">
              <View>
                <Text className="text-xs font-sans-medium text-text-muted mb-1.5">Category</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <SegmentedControl
                    options={categories.map(c => ({ label: c.replace('_', ' '), value: c }))}
                    value={selectedCategory}
                    onChange={(v) => setSelectedCategory(v.toString())}
                  />
                </ScrollView>
              </View>

              <View className="flex-row flex-wrap gap-3">
                <View className="flex-1 min-w-[200px]">
                  <TextField
                    label="Search Term"
                    value={searchTerm}
                    onChangeText={setSearchTerm}
                    placeholder="e.g. Postgres or Backend Developer"
                    onSubmitEditing={handleSearch}
                  />
                </View>
                <View className="w-24">
                  <TextField
                    label="Threshold"
                    value={threshold}
                    onChangeText={setThreshold}
                    placeholder="0.82"
                  />
                </View>
                <View className="w-24">
                  <TextField
                    label="Limit"
                    value={limit}
                    onChangeText={setLimit}
                    placeholder="5"
                  />
                </View>
              </View>

              <View className="self-end mt-2">
                <Button label="Find Equivalents" icon={<Search size={14} color="white" />} onPress={handleSearch} loading={loadingResults} disabled={!searchTerm.trim()} />
              </View>
            </View>
          )}

          {error && (
            <Card className="bg-danger/10 border-danger/30 p-3 mt-2">
              <Text className="text-xs font-sans-medium text-danger">{error}</Text>
            </Card>
          )}
        </Card>

        {/* Results Panel */}
        {results && (
          <Card className="gap-3">
            <View className="flex-row items-center justify-between border-b border-border pb-2">
              <View className="flex-row items-center gap-2">
                <Hash size={16} color={COLORS.info} />
                <Text className="text-sm font-sans-bold text-text-primary">
                  Results for "{results.term}"
                </Text>
              </View>
              <Badge label={results.category} tone="neutral" />
            </View>
            
            <View className="gap-2 mt-2">
              {results.equivalents.length === 0 ? (
                <Text className="text-xs text-text-muted p-2 text-center">No semantic equivalents found above the threshold.</Text>
              ) : (
                results.equivalents.map((eq, idx) => (
                  <DenseRow
                    key={idx}
                    title={eq.term}
                    trailing={
                      <Badge 
                        label={`${Math.round(eq.similarity_score * 100)}% Match`} 
                        tone={eq.similarity_score >= 0.9 ? 'success' : eq.similarity_score >= 0.8 ? 'info' : 'warning'} 
                      />
                    }
                  />
                ))
              )}
            </View>
          </Card>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
