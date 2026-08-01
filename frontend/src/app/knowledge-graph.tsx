import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { usePageTitle } from '@/hooks/usePageTitle';
import { talentGraphService } from '@/services/talentGraphService';
import {
  RecruitmentAnalyticsGraphResponse,
  CandidateGraphResponse,
  VacancyGraphResponse,
  SkillGraphResponse,
} from '@/types/api';
import { Card, Button, StatCard, TextField, SegmentedControl, Badge, Breadcrumbs, DenseRow } from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { GitBranch, UserCheck, Briefcase, Hash, Target } from 'lucide-react-native';
import { useRouter } from 'expo-router';

type SearchType = 'Candidate' | 'Vacancy' | 'Skill';

export default function KnowledgeGraphScreen() {
  usePageTitle('Knowledge Graph | AIRIS');
  const router = useRouter();

  const [analytics, setAnalytics] = useState<RecruitmentAnalyticsGraphResponse | null>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);

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
    try {
      const data = await talentGraphService.getAnalyticsGraph();
      setAnalytics(data);
    } catch (error) {
      console.warn('Failed to fetch analytics graph', error);
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
      setErrorGraph(err.message || 'Failed to fetch graph data.');
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
      case 'candidate': return <UserCheck size={16} color={COLORS.primary} />;
      case 'vacancy': return <Briefcase size={16} color={COLORS.warning} />;
      case 'skill': return <Hash size={16} color={COLORS.info} />;
      case 'department': return <Target size={16} color={COLORS.success} />;
      default: return <GitBranch size={16} color={COLORS.textMuted} />;
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Knowledge Graph' }]} />
      
      <View className="flex-row items-center justify-between px-3 py-2 bg-surface border-b border-border">
        <View className="flex-row items-center gap-2">
          <GitBranch size={18} color={COLORS.primary} />
          <View>
            <Text className="text-base font-sans-bold text-text-primary">Talent Knowledge Graph</Text>
            <Text className="text-[11px] font-sans text-text-muted">
              Semantic Entity Network & Graph Relationships
            </Text>
          </View>
        </View>
        <Button label="Refresh Analytics" variant="ghost" size="sm" onPress={fetchAnalytics} disabled={loadingAnalytics} />
      </View>

      <ScrollView className="flex-1 px-3 py-4">
        {/* Global Analytics Section */}
        <Card className="gap-3 mb-4">
          <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider mb-2">
            Global Graph Analytics
          </Text>
          {loadingAnalytics ? (
            <ActivityIndicator size="small" color={COLORS.primary} className="py-4" />
          ) : analytics ? (
            <View className="gap-4">
              <View className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard label="Total Nodes" value={analytics.graph_summary.total_graph_nodes} tone="info" />
                <StatCard label="Total Edges" value={analytics.graph_summary.total_graph_edges} tone="success" />
                <StatCard label="Tracked Skills" value={analytics.graph_summary.total_skills_tracked} tone="warning" />
                <StatCard label="Candidates" value={analytics.graph_summary.total_candidates} tone="primary" />
              </View>
              
              <View className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <View>
                  <Text className="text-xs font-sans-bold text-text-muted uppercase mb-2">Top Skills</Text>
                  <View className="gap-2">
                    {analytics.top_candidate_skills.slice(0, 5).map((item, idx) => (
                      <View key={idx} className="flex-row items-center justify-between bg-surface p-2 rounded border border-border">
                        <Text className="text-xs font-sans-medium text-text-primary">{item.skill}</Text>
                        <Badge label={`${item.candidate_count} candidates`} tone="neutral" />
                      </View>
                    ))}
                  </View>
                </View>
                <View>
                  <Text className="text-xs font-sans-bold text-text-muted uppercase mb-2">Department Distribution</Text>
                  <View className="gap-2">
                    {analytics.department_distribution.slice(0, 5).map((item, idx) => (
                      <View key={idx} className="flex-row items-center justify-between bg-surface p-2 rounded border border-border">
                        <Text className="text-xs font-sans-medium text-text-primary">{item.department}</Text>
                        <Badge label={`${item.candidate_count} candidates`} tone="info" />
                      </View>
                    ))}
                  </View>
                </View>
              </View>
            </View>
          ) : null}
        </Card>

        {/* Entity Search Section */}
        <Card className="gap-3 mb-8">
          <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
            Entity Search
          </Text>
          <View className="flex-row flex-wrap items-end gap-3">
            <View className="w-48">
              <SegmentedControl
                options={[
                  { label: 'Candidate', value: 'Candidate' },
                  { label: 'Vacancy', value: 'Vacancy' },
                  { label: 'Skill', value: 'Skill' }
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
              />
            </View>
            <View className="pb-1">
              <Button label="Search Graph" onPress={handleSearch} loading={loadingGraph} disabled={!searchQuery.trim()} />
            </View>
          </View>

          {errorGraph && (
            <Card className="bg-danger/10 border-danger/30 p-3 mt-3">
              <Text className="text-xs font-sans-medium text-danger">{errorGraph}</Text>
            </Card>
          )}

          {/* Graph Results Rendering */}
          {graphData && (
            <View className="mt-4 border-t border-border pt-4">
              <View className="flex-row items-center gap-2 mb-4">
                {getIconForType(searchType)}
                <Text className="text-sm font-sans-bold text-text-primary">
                  {searchType === 'Candidate' ? graphData.full_name : searchType === 'Vacancy' ? graphData.title : graphData.skill}
                </Text>
                <Badge label={`${graphData.total_nodes || graphData.nodes?.length} Nodes`} tone="neutral" />
                <Badge label={`${graphData.total_edges || graphData.edges?.length} Edges`} tone="info" />
              </View>

              <View className="gap-3">
                {/* Group edges by relationship type */}
                {Object.entries(
                  (graphData.edges || []).reduce((acc: any, edge: any) => {
                    if (!acc[edge.relationship]) acc[edge.relationship] = [];
                    acc[edge.relationship].push(edge);
                    return acc;
                  }, {})
                ).map(([relType, edges]: [string, any]) => (
                  <View key={relType} className="bg-surface border border-border rounded-md p-3">
                    <Text className="text-xs font-sans-bold text-text-muted uppercase mb-2">{relType}</Text>
                    <View className="gap-2">
                      {edges.map((edge: any, idx: number) => {
                        const targetNode = graphData.nodes.find((n: any) => n.id === edge.target || n.id === edge.source && n.id !== (searchType === 'Candidate' ? `candidate:${graphData.candidate_id}` : '')); // Simplified node lookup
                        // Proper node lookup:
                        const node = graphData.nodes.find((n: any) => 
                          (n.id === edge.target && edge.source.startsWith(searchType.toLowerCase())) ||
                          (n.id === edge.source && edge.target.startsWith(searchType.toLowerCase()))
                        ) || graphData.nodes.find((n: any) => n.id === edge.target);

                        if (!node) return null;

                        return (
                          <DenseRow
                            key={idx}
                            title={
                              <View className="flex-row items-center gap-2">
                                {getIconForType(node.type)}
                                <Text className="text-xs font-sans-medium text-text-primary">{node.label}</Text>
                              </View>
                            }
                            subtitle={
                              <Text className="text-[10px] font-sans text-text-muted">
                                {node.type} {node.properties?.department ? `• ${node.properties.department}` : ''}
                              </Text>
                            }
                            trailing={
                              <View className="items-end gap-1">
                                {edge.properties?.score != null && (
                                  <Badge label={`${Math.round(edge.properties.score)}%`} tone="success" />
                                )}
                                {edge.properties?.similarity != null && (
                                  <Badge label={`${Math.round(edge.properties.similarity * 100)}%`} tone="info" />
                                )}
                                {edge.properties?.is_duplicate && (
                                  <Badge label="Duplicate" tone="danger" />
                                )}
                              </View>
                            }
                            onPress={['Candidate', 'Vacancy'].includes(node.type) ? () => navigateToEntity(node.type, node.id) : undefined}
                          />
                        );
                      })}
                    </View>
                  </View>
                ))}
              </View>
            </View>
          )}
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}
