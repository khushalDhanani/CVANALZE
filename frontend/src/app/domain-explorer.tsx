import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePageTitle } from '@/hooks/usePageTitle';
import { domainKnowledgeService } from '@/services/domainKnowledgeService';
import { DomainEquivalentResponse } from '@/types/api';
import {
  Card,
  Button,
  TextField,
  Badge,
  Breadcrumbs,
  DenseRow,
  ErrorBanner,
  EmptyState,
} from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { SIMILARITY_CONFIG } from '@/constants/similarity';
import { BookOpen, Search, Hash, RefreshCw } from 'lucide-react-native';

export default function DomainExplorerScreen() {
  usePageTitle('Domain Explorer | AIRIS');

  const [categories, setCategories] = useState<string[]>([]);
  const [loadingCategories, setLoadingCategories] = useState<boolean>(true);
  const [categoryError, setCategoryError] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [threshold, setThreshold] = useState<string>(String(SIMILARITY_CONFIG.defaultThreshold));
  const [limit, setLimit] = useState<string>(String(SIMILARITY_CONFIG.defaultLimit));

  const [results, setResults] = useState<DomainEquivalentResponse | null>(null);
  const [loadingResults, setLoadingResults] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCategories = async () => {
    setLoadingCategories(true);
    setCategoryError(null);
    try {
      const cats = await domainKnowledgeService.getCategories();
      setCategories(cats);
      if (cats.length > 0) {
        setSelectedCategory((prev) => (prev && cats.includes(prev) ? prev : cats[0]));
      }
    } catch (err: any) {
      setCategoryError(err.message || 'Failed to fetch domain categories from knowledge service.');
    } finally {
      setLoadingCategories(false);
    }
  };

  useEffect(() => {
    fetchCategories();
  }, []);

  // Strict numeric validations
  const parsedThreshold = parseFloat(threshold);
  const thresholdError =
    isNaN(parsedThreshold) ||
    !Number.isFinite(parsedThreshold) ||
    parsedThreshold < SIMILARITY_CONFIG.minThreshold ||
    parsedThreshold > SIMILARITY_CONFIG.maxThreshold
      ? 'Threshold must be between 0.00 and 1.00'
      : undefined;

  const parsedLimit = parseInt(limit, 10);
  const limitError =
    isNaN(parsedLimit) ||
    !Number.isFinite(parsedLimit) ||
    parsedLimit < SIMILARITY_CONFIG.minLimit ||
    parsedLimit > SIMILARITY_CONFIG.maxLimit
      ? 'Limit must be an integer between 1 and 50'
      : undefined;

  const isFormValid = Boolean(
    searchTerm.trim() &&
      selectedCategory &&
      !thresholdError &&
      !limitError
  );

  const handleSearch = async () => {
    if (!isFormValid || !selectedCategory) return;
    setLoadingResults(true);
    setError(null);
    setResults(null);

    try {
      const data = await domainKnowledgeService.getEquivalents({
        term: searchTerm.trim(),
        category: selectedCategory,
        threshold: parsedThreshold,
        limit: parsedLimit,
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

      {/* Sticky Header */}
      <View className="flex-row items-center justify-between px-3 py-2.5 bg-surface border-b border-border">
        <View className="flex-row items-center gap-2">
          <BookOpen size={18} color={COLORS.primary} />
          <View>
            <Text className="text-base font-sans-bold text-text-primary">Domain Explorer</Text>
            <Text className="text-[11px] font-sans text-text-muted">
              Semantic Equivalents & Domain Knowledge Discovery
            </Text>
          </View>
        </View>
      </View>

      <ScrollView className="flex-1 px-3 py-4">
        {/* Search Panel */}
        <Card className="gap-4 mb-4">
          <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">
            Semantic Equivalents Lookup
          </Text>

          {/* Category Selector with Dedicated Error/Loading Handling */}
          {loadingCategories ? (
            <View className="py-4 items-center flex-row gap-2">
              <ActivityIndicator size="small" color={COLORS.primary} />
              <Text className="text-xs font-sans text-text-muted">Loading domain categories...</Text>
            </View>
          ) : categoryError ? (
            <View className="gap-2">
              <ErrorBanner title="Taxonomy Error" message={categoryError} />
              <View className="self-start">
                <Button
                  label="Retry Loading Taxonomy"
                  variant="ghost"
                  size="sm"
                  onPress={fetchCategories}
                />
              </View>
            </View>
          ) : (
            <View className="gap-3">
              <View>
                <Text className="text-xs font-sans-medium text-text-muted mb-1.5">Taxonomy Category</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} className="flex-row">
                  <View className="flex-row gap-2 py-0.5">
                    {categories.map((cat) => {
                      const isSelected = selectedCategory === cat;
                      return (
                        <Pressable
                          key={cat}
                          onPress={() => setSelectedCategory(cat)}
                          className={`px-3 py-1.5 rounded-full border min-h-[36px] justify-center ${
                            isSelected
                              ? 'bg-primary border-primary'
                              : 'bg-surface border-border active:bg-surface-hover'
                          }`}
                          accessibilityRole="button"
                          accessibilityState={{ selected: isSelected }}
                          hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
                        >
                          <Text
                            className={`text-xs capitalize ${
                              isSelected ? 'text-white font-sans-bold' : 'text-text-primary font-sans-medium'
                            }`}
                          >
                            {cat.replace(/_/g, ' ')}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </ScrollView>
              </View>

              {/* Form Inputs Grid */}
              <View className="flex-col sm:flex-row flex-wrap gap-3">
                <View className="flex-1 min-w-[200px]">
                  <TextField
                    label="Search Term"
                    value={searchTerm}
                    onChangeText={setSearchTerm}
                    placeholder="e.g. Postgres or Backend Developer"
                    onSubmitEditing={handleSearch}
                    helperText="Input a skill, title, technology, or domain concept"
                  />
                </View>
                <View className="flex-1 min-w-[120px] sm:flex-initial sm:w-28">
                  <TextField
                    label="Threshold"
                    value={threshold}
                    onChangeText={setThreshold}
                    placeholder="0.82"
                    keyboardType="numeric"
                    error={thresholdError}
                    helperText="Min similarity (0–1)"
                  />
                </View>
                <View className="flex-1 min-w-[120px] sm:flex-initial sm:w-28">
                  <TextField
                    label="Limit"
                    value={limit}
                    onChangeText={setLimit}
                    placeholder="5"
                    keyboardType="numeric"
                    error={limitError}
                    helperText="Max results (1–50)"
                  />
                </View>
              </View>

              <View className="self-end mt-1">
                <Button
                  label="Find Equivalents"
                  icon={<Search size={14} color="white" />}
                  onPress={handleSearch}
                  loading={loadingResults}
                  disabled={!isFormValid || loadingResults}
                />
              </View>
            </View>
          )}

          {error && <ErrorBanner title="Query Error" message={error} />}
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
              <Badge label={results.category.replace(/_/g, ' ')} tone="neutral" />
            </View>

            <View className="gap-2 mt-1">
              {results.equivalents.length === 0 ? (
                <EmptyState
                  variant="compact"
                  title="No Equivalents Found"
                  subtitle={`No semantic equivalents met the requested ${(parsedThreshold * 100).toFixed(0)}% similarity threshold.`}
                />
              ) : (
                results.equivalents.map((eq, idx) => (
                  <DenseRow
                    key={idx}
                    title={eq.term}
                    subtitle={`Cosine similarity score: ${(eq.similarity_score * 100).toFixed(1)}%`}
                    trailing={
                      <Badge
                        label={`${Math.round(eq.similarity_score * 100)}% Match`}
                        tone={SIMILARITY_CONFIG.getTone(eq.similarity_score)}
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
