import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { FileText, Upload, Plus, CpuIcon, FolderIcon, SlidersIcon, Users } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { apiClient } from '@/services/apiClient';
import { matchService } from '@/services/matchService';
import { useJobs } from '@/hooks/useJobs';
import { useCandidates } from '@/hooks/useCandidates';
import { usePageTitle } from '@/hooks/usePageTitle';
import { LlmHealthResponse, SystemHealthResponse } from '@/types/api';
import { Card, DenseRow, Badge, Button, StatCard, Breadcrumbs } from '@/components/ui';
import { COLORS } from '@/constants/colors';

export default function HomeScreen() {
  usePageTitle('Dashboard | AIRIS');
  const router = useRouter();
  const { jobs, loading: jobsLoading } = useJobs();
  const { candidates, loading: candidatesLoading } = useCandidates();
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [llmHealth, setLlmHealth] = useState<LlmHealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);

  const fetchHealth = async () => {
    setHealthLoading(true);
    try {
      const [sysRes, llmRes] = await Promise.all([
        apiClient.get<SystemHealthResponse>('/health').catch(() => ({
          status: 'offline',
          version: '1.0.0',
          database: 'offline',
          pg_database: 'offline',
          ollama_llm: 'offline',
        })),
        matchService.getLlmHealth().catch(() => ({
          status: 'offline',
          message: 'Backend server offline (Start server at http://localhost:8000)',
        })),
      ]);
      setHealth(sysRes);
      setLlmHealth(llmRes);
    } catch (err) {
        setHealth({
        status: 'offline',
        version: '1.0.0',
        database: 'offline',
        pg_database: 'offline',
        ollama_llm: 'offline',
      });
      setLlmHealth({
        status: 'offline',
        message: 'Backend server offline',
      });
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  const uniqueJobs = Array.from(new Map(jobs.map(j => {
    const title = (j as any).VacancyTitle || (j as any).title;
    return [title, j];
  })).values());

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[]} />
      <ScrollView className="flex-1 px-3">
        <View className="gap-4 py-4">

          {/* Hero Section */}
          <View className="bg-primary rounded-md p-3 border border-primary shadow-sm" style={{ elevation: 1 }}>
            <View className="flex-row items-center justify-between mb-2">
              <View className="flex-row items-center gap-2">
                <View className="w-8 h-8 rounded-md bg-surface/20 items-center justify-center">
                  <CpuIcon size={18} color={COLORS.textInverse} />
                </View>
                <Text className="text-xl font-sans-bold text-text-inverse tracking-wide">
                  CAP
                </Text>
              </View>
              <Badge label={`v${health?.version || '1.0.0'}`} tone="info" />
            </View>
            <Text className="text-text-inverse opacity-90 text-sm font-sans">
              AI-powered CV extraction, job vacancy matching, and intelligent batch candidate screening.
            </Text>
          </View>

          {/* Quick Stats Grid */}
          <View className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Active Vacancies"
              value={jobsLoading ? undefined : jobs.length}
              sublabel="Cached in-memory"
              loading={jobsLoading}
            />
            <StatCard
              label="LLM Engine"
              value={llmHealth?.status === 'online' ? 'ONLINE' : 'BYPASS'}
              sublabel={llmHealth?.model_configured || 'Confidence Gated'}
              tone={llmHealth?.status === 'online' ? 'success' : 'warning'}
            />
            <StatCard
              label="MSSQL Primary DB"
              value={health?.database?.toUpperCase() || 'ONLINE'}
              sublabel="Relational Store"
              tone={health?.database === 'online' ? 'success' : 'neutral'}
            />
            <StatCard
              label="pgvector DB"
              value={health?.pg_database?.toUpperCase() || 'ONLINE'}
              sublabel="PostgreSQL Vectors"
              tone={health?.pg_database === 'online' ? 'success' : 'warning'}
            />
          </View>

          {/* Action Shortcuts */}
          <View>
            <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide pt-4 pb-1">
              Quick Workflows
            </Text>
            <View className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              <DenseRow
                className="h-full"
                title="Single CV Match & Upload"
                subtitle="Upload PDF/Docx or paste CV text for instant evaluation"
                onPress={() => router.push('/cv-match')}
                trailing={
                  <View className="w-9 h-9 rounded-full bg-primary/10 items-center justify-center mr-1">
                    <FileText size={16} color={COLORS.primary} />
                  </View>
                }
              />
              <DenseRow
                className="h-full"
                title="Candidate Directory"
                subtitle="Browse, search, and review all parsed candidate profiles"
                onPress={() => router.push('/candidates')}
                trailing={
                  <View className="w-9 h-9 rounded-full bg-info/10 items-center justify-center mr-1">
                    <Users size={16} color={COLORS.info} />
                  </View>
                }
              />
              <DenseRow
                className="h-full"
                title="Job Openings Directory"
                subtitle="View active job requirements, skills, and clear cache"
                onPress={() => router.push('/vacancies')}
                trailing={
                  <View className="w-9 h-9 rounded-full bg-success/10 items-center justify-center mr-1">
                    <FolderIcon size={16} color={COLORS.success} />
                  </View>
                }
              />
              <DenseRow
                className="h-full"
                title="Batch Processing"
                subtitle="Evaluate candidates against vacancies with WebSocket progress"
                onPress={() => router.push('/batch')}
                trailing={
                  <View className="w-9 h-9 rounded-full bg-warning/10 items-center justify-center mr-1">
                    <Plus size={16} color={COLORS.warning} />
                  </View>
                }
              />
              <DenseRow
                className="h-full"
                title="Engine Weight Config"
                subtitle="Tune role, skills, domain weights & failure penalties"
                onPress={() => router.push('/config')}
                trailing={
                  <View className="w-9 h-9 rounded-full bg-info/10 items-center justify-center mr-1">
                    <SlidersIcon size={16} color={COLORS.info} />
                  </View>
                }
              />
            </View>
          </View>


          {/* System Health Detailed Box */}
          {/* Needs Attention Panel */}
          <View>
            <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide pt-4 pb-1">
              Needs Attention
            </Text>
            <View className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              <StatCard
                label="Unreviewed"
                value={candidates.filter(c => !c.best_match?.classification).length}
                tone={candidates.filter(c => !c.best_match?.classification).length > 0 ? 'warning' : 'neutral'}
              />
              <StatCard
                label="OCR Warnings"
                value={candidates.filter(c => c.ocr_applied).length}
                tone={candidates.filter(c => c.ocr_applied).length > 0 ? 'info' : 'neutral'}
              />
              <StatCard
                label="Failed Parses"
                value={candidates.filter(c => c.page_count === 0).length}
                tone={candidates.filter(c => c.page_count === 0).length > 0 ? 'danger' : 'neutral'}
              />
            </View>
          </View>

          {/* Recent Activity */}
          <View>
            <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide pt-4 pb-1">
              Recent Activity
            </Text>
            <View className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {candidatesLoading ? (
                <ActivityIndicator size="small" />
              ) : candidates.slice(0, 4).map((cand, i) => (
                <DenseRow
                  className="h-full"
                  key={cand.id || i}
                  title={cand.filename || 'Unknown CV'}
                  subtitle={cand.best_match?.job_title || 'Parsed recently'}
                  onPress={() => router.push(`/candidates/${encodeURIComponent(cand.id)}` as any)}
                />
              ))}
              {candidates.length === 0 && !candidatesLoading && (
                <Text className="text-xs font-sans text-text-muted">No recent activity.</Text>
              )}
            </View>
          </View>

          {/* Top Vacancies */}
          <View>
            <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide pt-4 pb-1">
              Top Vacancies
            </Text>
            <View className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {jobsLoading ? (
                <ActivityIndicator size="small" />
              ) : uniqueJobs.slice(0, 4).map((job, i) => (
                <DenseRow
                  className="h-full"
                  key={(job as any).VacancyID || (job as any).id || i}
                  title={(job as any).VacancyTitle || (job as any).title || 'Unknown'}
                  subtitle={(job as any).DepartmentName || (job as any).department || 'General'}
                  onPress={() => {
                    const vId = (job as any).id || (job as any).VacancyID;
                    router.push(vId ? `/vacancies/${vId}` as any : `/vacancies`);
                  }}
                />
              ))}
              {jobs.length === 0 && !jobsLoading && (
                <Text className="text-xs font-sans text-text-muted">No active vacancies.</Text>
              )}
            </View>
          </View>

          {/* System Health Detailed Box */}
          <View className="mb-4">
            <View className="flex-row justify-between items-center mb-2">
              <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide pt-4 pb-1">
                System Health & Services
              </Text>
              <Button
                label={healthLoading ? 'Refreshing...' : 'Refresh'}
                variant="ghost"
                size="sm"
                onPress={fetchHealth}
                disabled={healthLoading}
              />
            </View>
            <View className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              <DenseRow
                className="h-full"
                title="FastAPI Server"
                trailing={
                  <Badge
                    label={health?.status === 'offline' ? 'Offline (Start Server)' : 'Operational'}
                    tone={health?.status === 'offline' ? 'warning' : 'success'}
                  />
                }
              />
              <DenseRow
                className="h-full"
                title="MSSQL Primary DB"
                trailing={
                  <Badge
                    label={health?.database === 'offline' ? 'Offline' : 'Operational'}
                    tone={health?.database === 'offline' ? 'warning' : 'success'}
                  />
                }
              />
              <DenseRow
                className="h-full"
                title="PostgreSQL (Vector DB)"
                trailing={
                  <Badge
                    label={health?.pg_database === 'offline' ? 'Offline' : 'Operational'}
                    tone={health?.pg_database === 'offline' ? 'warning' : 'success'}
                  />
                }
              />
              <DenseRow
                className="h-full"
                title="Ollama LLM Model"
                trailing={
                  <Badge
                    label={
                      llmHealth?.status === 'online'
                        ? llmHealth.model_configured || 'Connected'
                        : llmHealth?.status === 'disabled'
                          ? 'Disabled (Confidence Gated)'
                          : 'Offline'
                    }
                    tone={
                      llmHealth?.status === 'online'
                        ? 'success'
                        : llmHealth?.status === 'disabled'
                          ? 'info'
                          : 'warning'
                    }
                  />
                }
              />
              <DenseRow
                className="h-full"
                title="Available LLMs"
                subtitle={
                  llmHealth?.status === 'online'
                    ? llmHealth.available_models?.join(', ') || 'None found'
                    : llmHealth?.status === 'disabled'
                      ? 'Bypass (Fast-Track Rule Engine)'
                      : 'Ollama Unreachable'
                }
              />
            </View>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
