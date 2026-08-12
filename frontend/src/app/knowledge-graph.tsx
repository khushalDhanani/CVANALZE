import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePageTitle } from '@/hooks/usePageTitle';
import { talentGraphService } from '@/services/talentGraphService';
import {
  RecruitmentAnalyticsGraphResponse,
} from '@/types/api';
import {
  Card,
  Button,
  StatCard,
  TextField,
  SegmentedControl,
  Badge,
  Breadcrumbs,
  DenseRow,
  ErrorBanner,
  EmptyState,
} from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { GitBranch, UserCheck, Briefcase, Hash, Target, AlertCircle } from 'lucide-react-native';
import { useRouter } from 'expo-router';

type SearchType = 'Candidate' | 'Vacancy' | 'Skill';

export default function KnowledgeGraphScreen() {
  usePageTitle('Knowledge Graph & Entity Relationships | AIRIS');
  const router = useRouter();

  const [analytics, setAnalytics] = useState<RecruitmentAnalyticsGraphResponse | null>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);

  const [searchType, setSearchType] = useState<SearchType>('Candidate');
  const [searchQuery, setSearchQuery] = useState('');

  const [graphData, setGraphData] = useState<any>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [errorGraph, setErrorGraph] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    setLoadingAnalytics(true);
    setAnalyticsError(null);
    try {
      const data = await talentGraphService.getAnalyticsGraph();
      setAnalytics(data);
    } catch (err: any) {
      setAnalyticsError(err.message || 'Failed to fetch global graph analytics.');
    } finally {
      setLoadingAnalytics(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoadingGraph(true);
    setErrorGraph(null);
    setGraphData(null);

    try {
      let data;
      if (searchType === 'Candidate') {
        data = await talentGraphService.getCandidateGraph(searchQuery.trim());
      } else if (searchType === 'Vacancy') {
        data = await talentGraphService.getVacancyGraph(searchQuery.trim());
      } else {
        data = await talentGraphService.getSkillGraph(searchQuery.trim());
      }
      setGraphData(data);
    } catch (err: any) {
      setErrorGraph(err.message || 'Failed to fetch graph relationships.');
    } finally {
      setLoadingGraph(false);
    }
  };

  const navigateToEntity = (type: string, id: string) => {
    if (type.toLowerCase() === 'candidate') {
      const cleanId = id.replace('candidate:', '');
      router.push(`/candidates/${encodeURIComponent(cleanId)}` as any);
    } else if (type.toLowerCase() === 'vacancy') {
      const cleanId = id.replace('vacancy:', '');
      router.push(`/vacancies/${encodeURIComponent(cleanId)}` as any);
    }
  };

  const getIconForType = (type: string) => {
    switch (type.toLowerCase()) {
      case 'candidate':
        return <UserCheck size={16} color={COLORS.primary} />;
      case 'vacancy':
        return <Briefcase size={16} color={COLORS.category?.blue || COLORS.info} />;
      case 'skill':
        return <Hash size={16} color={COLORS.category?.purple || COLORS.primaryLight} />;
      case 'department':
        return <Target size={16} color={COLORS.category?.teal || COLORS.info} />;
      default:
        return <GitBranch size={16} color={COLORS.textMuted} />;
    }
  };

  // Build node lookup dictionary for normalized O(1) entity resolution
  const nodeMap = React.useMemo(() => {
    const map = new Map<string, any>();
    if (graphData && Array.isArray(graphData.nodes)) {
      graphData.nodes.forEach((n: any) => {
        if (n && n.id) {
          map.set(n.id, n);
        }
      });
    }
    return map;
  }, [graphData]);

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Knowledge Graph' }]} />

      {/* Responsive PageHeader */}
      <View className="flex-col sm:flex-row items-start sm:items-center justify-between px-3 py-2.5 bg-surface border-b border-border gap-3">
        <View className="flex-row items-center gap-2">
          <GitBranch size={18} color={COLORS.primary} />
          <View>
            <Text className="text-base font-sans-bold text-text-primary">
              Talent Knowledge & Relationship Explorer
            </Text>
            <Text className="text-[11px] font-sans text-text-muted">
              Semantic entity network, taxonomy connections, and candidate-vacancy graph relationships
            </Text>
          </View>
        </View>
        <Button
          label="Refresh Analytics"
          variant="ghost"
          size="sm"
          onPress={fetchAnalytics}
          disabled={loadingAnalytics}
        />
      </View>

      <ScrollView className="flex-1 px-3 py-4">
        {/* Global Analytics Section */}
        <Card className="gap-3 mb-4">
          <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider mb-1">
            Global Graph Analytics
          </Text>

          {loadingAnalytics ? (
            <View className="py-8 items-center">
              <ActivityIndicator size="small" color={COLORS.primary} />
              <Text className="text-xs font-sans text-text-muted mt-2">Loading graph analytics...</Text>
            </View>
          ) : analyticsError ? (
            <View className="gap-2">
              <ErrorBanner title="Analytics Error" message={analyticsError} />
              <View className="self-start">
                <Button label="Retry Analytics" variant="ghost" size="sm" onPress={fetchAnalytics} />
              </View>
            </View>
          ) : analytics ? (
            <View className="gap-4">
              <View className="flex-row flex-wrap gap-3">
                <StatCard
                  label="Total Nodes"
                  value={analytics.graph_summary.total_graph_nodes}
                  sublabel="Entities in Network"
                  tone="info"
                />
                <StatCard
                  label="Total Edges"
                  value={analytics.graph_summary.total_graph_edges}
                  sublabel="Connected Relationships"
                  tone="success"
                />
                <StatCard
                  label="Tracked Skills"
                  value={analytics.graph_summary.total_skills_tracked}
                  sublabel="Taxonomy Skills"
                  tone="neutral"
                />
                <StatCard
                  label="Candidates"
                  value={analytics.graph_summary.total_candidates}
                  sublabel="Indexed Profiles"
                  tone="neutral"
                />
              </View>

              <View className="flex-row flex-wrap gap-4">
                <View className="flex-1 min-w-[280px]">
                  <Text className="text-xs font-sans-bold text-text-muted uppercase mb-2">Top Skills</Text>
                  <View className="gap-2">
                    {analytics.top_candidate_skills.slice(0, 5).map((item, idx) => (
                      <View
                        key={`skill_${item.skill}_${idx}`}
                        className="flex-row items-center justify-between bg-surface p-2 rounded border border-border"
                      >
                        <Text className="text-xs font-sans-medium text-text-primary">{item.skill}</Text>
                        <Badge label={`${item.candidate_count} candidates`} tone="neutral" />
                      </View>
                    ))}
                  </View>
                </View>
                <View className="flex-1 min-w-[280px]">
                  <Text className="text-xs font-sans-bold text-text-muted uppercase mb-2">
                    Department Distribution
                  </Text>
                  <View className="gap-2">
                    {analytics.department_distribution.slice(0, 5).map((item, idx) => (
                      <View
                        key={`dept_${item.department}_${idx}`}
                        className="flex-row items-center justify-between bg-surface p-2 rounded border border-border"
                      >
                        <Text className="text-xs font-sans-medium text-text-primary">{item.department}</Text>
                        <Badge label={`${item.candidate_count} candidates`} tone="info" />
                      </View>
                    ))}
                  </View>
                </View>
              </View>
            </View>
          ) : (
            <EmptyState
              variant="compact"
              title="Analytics Unavailable"
              subtitle="The graph service returned no global telemetry summary."
            />
          )}
        </Card>

        {/* Entity Search Section */}
        <Card className="gap-3 mb-8">
          <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">
            Entity Relationship Search
          </Text>

          <View className="flex-col sm:flex-row items-stretch sm:items-end gap-3">
            <View className="w-full sm:w-52">
              <SegmentedControl
                options={[
                  { label: 'Candidate', value: 'Candidate' },
                  { label: 'Vacancy', value: 'Vacancy' },
                  { label: 'Skill', value: 'Skill' },
                ]}
                value={searchType}
                onChange={(v) => setSearchType(v as SearchType)}
              />
            </View>
            <View className="flex-1 min-w-[200px]">
              <TextField
                label="Search Term or ID"
                value={searchQuery}
                onChangeText={setSearchQuery}
                placeholder={`Enter ${searchType.toLowerCase()} ID or name...`}
                onSubmitEditing={handleSearch}
                helperText={`Search relationship network for ${searchType.toLowerCase()} entity`}
              />
            </View>
            <View className="self-end sm:self-auto pb-0.5">
              <Button
                label="Search Graph"
                onPress={handleSearch}
                loading={loadingGraph}
                disabled={!searchQuery.trim() || loadingGraph}
              />
            </View>
          </View>

          {errorGraph && <ErrorBanner title="Graph Query Error" message={errorGraph} />}

          {/* Graph Results Rendering */}
          {graphData && (
            <View className="mt-4 border-t border-border pt-4">
              <View className="flex-row items-center gap-2 mb-4 flex-wrap">
                {getIconForType(searchType)}
                <Text className="text-sm font-sans-bold text-text-primary">
                  {searchType === 'Candidate'
                    ? graphData.full_name || graphData.candidate_name
                    : searchType === 'Vacancy'
                      ? graphData.title || graphData.job_title
                      : graphData.skill || searchQuery}
                </Text>
                <Badge
                  label={`${graphData.total_nodes || graphData.nodes?.length || 0} Nodes`}
                  tone="neutral"
                />
                <Badge
                  label={`${graphData.total_edges || graphData.edges?.length || 0} Edges`}
                  tone="info"
                />
              </View>

              {!graphData.edges || graphData.edges.length === 0 ? (
                <EmptyState
                  variant="compact"
                  title="No Relationships Found"
                  subtitle={`No graph connections discovered for this ${searchType.toLowerCase()}.`}
                />
              ) : (
                <View className="gap-3">
                  {/* Group edges by relationship type */}
                  {Object.entries(
                    (graphData.edges || []).reduce((acc: any, edge: any) => {
                      const rel = edge.relationship || 'Connected';
                      if (!acc[rel]) acc[rel] = [];
                      acc[rel].push(edge);
                      return acc;
                    }, {})
                  ).map(([relType, edges]: [string, any]) => (
                    <View key={`group_${relType}`} className="bg-surface border border-border rounded-md p-3">
                      <Text className="text-xs font-sans-bold text-text-muted uppercase mb-2">
                        {relType.replace(/_/g, ' ')}
                      </Text>
                      <View className="gap-2">
                        {edges.map((edge: any, idx: number) => {
                          const targetNodeId =
                            edge.target && !edge.target.toLowerCase().startsWith(searchType.toLowerCase())
                              ? edge.target
                              : edge.source;

                          const node = nodeMap.get(targetNodeId) || nodeMap.get(edge.target) || nodeMap.get(edge.source);
                          if (!node) return null;

                          const stableKey = `${edge.source}_${edge.relationship}_${edge.target}_${idx}`;

                          return (
                            <DenseRow
                              key={stableKey}
                              title={
                                <View className="flex-row items-center gap-2">
                                  {getIconForType(node.type)}
                                  <Text className="text-xs font-sans-medium text-text-primary">
                                    {node.label || node.name || node.title || node.id}
                                  </Text>
                                </View>
                              }
                              subtitle={
                                <Text className="text-[11px] font-sans text-text-muted">
                                  {node.type}
                                  {node.properties?.department ? ` • ${node.properties.department}` : ''}
                                </Text>
                              }
                              trailing={
                                <View className="items-end gap-1 flex-row">
                                  {edge.properties?.score != null && (
                                    <Badge label={`${Math.round(edge.properties.score)}%`} tone="success" />
                                  )}
                                  {edge.properties?.similarity != null && (
                                    <Badge
                                      label={`${Math.round(edge.properties.similarity * 100)}%`}
                                      tone="info"
                                    />
                                  )}
                                  {edge.properties?.is_duplicate && (
                                    <Badge label="Duplicate" tone="danger" />
                                  )}
                                </View>
                              }
                              onPress={
                                ['Candidate', 'Vacancy'].includes(node.type)
                                  ? () => navigateToEntity(node.type, node.id)
                                  : undefined
                              }
                            />
                          );
                        })}
                      </View>
                    </View>
                  ))}
                </View>
              )}
            </View>
          )}
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}
