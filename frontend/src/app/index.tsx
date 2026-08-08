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
import {
  Card,
  DenseRow,
  Badge,
  Button,
  StatCard,
  Breadcrumbs,
  EmptyState,
  ResponsiveStatGrid,
  ResponsiveFieldGrid,
  StatusBanner,
} from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { BRAND } from '@/constants/brand';

export default function HomeScreen() {
  usePageTitle('Dashboard | AIRIS');
  const router = useRouter();
  const { jobs, loading: jobsLoading, error: jobsError } = useJobs();
  const { candidates, loading: candidatesLoading, error: candidatesError } = useCandidates();
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [llmHealth, setLlmHealth] = useState<LlmHealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<boolean>(false);

  const fetchHealth = async () => {
    setHealthLoading(true);
    setHealthError(false);
    try {
      const [sysRes, llmRes] = await Promise.all([
        apiClient.get<SystemHealthResponse>('/health').catch(() => null),
        matchService.getLlmHealth().catch(() => null),
      ]);
      setHealth(sysRes);
      setLlmHealth(llmRes);
      if (!sysRes && !llmRes) {
        setHealthError(true);
      }
    } catch (err) {
      setHealth(null);
      setLlmHealth(null);
      setHealthError(true);
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  // Deduplicate by stable ID rather than title alone
  const uniqueJobs = Array.from(
    new Map(
      jobs.map((j) => {
        const id = (j as any).id || (j as any).VacancyID || (j as any).vacancy_id || (j as any).title;
        return [id, j];
      })
    ).values()
  );

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[]} />
      <ScrollView className="flex-1 px-3" contentContainerStyle={{ paddingBottom: 32 }}>
        <View className="gap-5 py-4">

          {/* Hero Section */}
          <View className="bg-primary rounded-lg p-4 border border-primary shadow-sm" style={{ elevation: 1 }}>
            <View className="flex-row items-center justify-between mb-2">
              <View className="flex-row items-center gap-2.5">
                <View className="w-9 h-9 rounded-md bg-surface/20 items-center justify-center">
                  <CpuIcon size={20} color={COLORS.textInverse} />
                </View>
                <Text className="text-xl font-sans-bold text-text-inverse tracking-wide">
                  {BRAND.name}
                </Text>
              </View>
              {health?.version ? (
                <Badge label={`v${health.version}`} tone="info" />
              ) : healthLoading ? (
                <Badge label="Checking..." tone="neutral" />
              ) : healthError || health?.status === 'offline' ? (
                <Badge label="Offline" tone="warning" />
              ) : null}
            </View>
            <Text className="text-text-inverse opacity-90 text-sm font-sans leading-5">
              {BRAND.tagline}
            </Text>
          </View>

          {/* Quick Stats Grid */}
          <ResponsiveStatGrid minCardWidth={160} gap={12}>
            <StatCard
              label="Active Vacancies"
              value={jobsLoading ? undefined : jobsError ? 'Unavailable' : jobs.length}
              sublabel={jobsError ? 'Failed to fetch directory' : 'Current active vacancies'}
              loading={jobsLoading}
              tone={jobsError ? 'danger' : 'neutral'}
            />
            <StatCard
              label="LLM Engine"
              value={
                healthLoading
                  ? undefined
                  : llmHealth?.status === 'online'
                  ? 'ONLINE'
                  : llmHealth?.status === 'disabled'
                  ? 'DISABLED'
                  : 'OFFLINE'
              }
              sublabel={
                healthLoading
                  ? 'Checking engine...'
                  : llmHealth?.status === 'online'
                  ? llmHealth.model_configured || 'Connected'
                  : llmHealth?.status === 'disabled'
                  ? 'LLM Reasoning Disabled'
                  : 'Backend Unreachable'
              }
              loading={healthLoading}
              tone={
                healthLoading
                  ? 'neutral'
                  : llmHealth?.status === 'online'
                  ? 'success'
                  : llmHealth?.status === 'disabled'
                  ? 'info'
                  : 'danger'
              }
            />
            <StatCard
              label="MSSQL Primary DB"
              value={
                healthLoading
                  ? undefined
                  : health?.database === 'online'
                  ? 'ONLINE'
                  : 'OFFLINE'
              }
              sublabel={healthLoading ? 'Checking DB...' : 'Relational Store'}
              loading={healthLoading}
              tone={
                healthLoading
                  ? 'neutral'
                  : health?.database === 'online'
                  ? 'success'
                  : 'danger'
              }
            />
            <StatCard
              label="pgvector DB"
              value={
                healthLoading
                  ? undefined
                  : health?.pg_database === 'online'
                  ? 'ONLINE'
                  : 'OFFLINE'
              }
              sublabel={healthLoading ? 'Checking vectors...' : 'PostgreSQL Vectors'}
              loading={healthLoading}
              tone={
                healthLoading
                  ? 'neutral'
                  : health?.pg_database === 'online'
                  ? 'success'
                  : 'warning'
              }
            />
          </ResponsiveStatGrid>

          {/* Action Shortcuts */}
          <View className="gap-2">
            <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide">
              Quick Workflows
            </Text>
            <ResponsiveFieldGrid minItemWidth={280} gap={10}>
              <DenseRow
                title="Single CV Match & Upload"
                subtitle="Upload PDF/Docx or paste CV text for instant evaluation"
                onPress={() => router.push('/cv-match')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-primary/10 items-center justify-center">
                    <FileText size={15} color={COLORS.primary} />
                  </View>
                }
              />
              <DenseRow
                title="Candidate Directory"
                subtitle="Browse, search, and review all parsed candidate profiles"
                onPress={() => router.push('/candidates')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-info/10 items-center justify-center">
                    <Users size={15} color={COLORS.info} />
                  </View>
                }
              />
              <DenseRow
                title="Job Openings Directory"
                subtitle="View active job requirements, skills, and clear cache"
                onPress={() => router.push('/vacancies')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-success/10 items-center justify-center">
                    <FolderIcon size={15} color={COLORS.success} />
                  </View>
                }
              />
              <DenseRow
                title="Batch Processing"
                subtitle="Evaluate candidates against vacancies with WebSocket progress"
                onPress={() => router.push('/batch')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-warning/10 items-center justify-center">
                    <Plus size={15} color={COLORS.warning} />
                  </View>
                }
              />
              <DenseRow
                title="Engine Weight Config"
                subtitle="Tune role, skills, domain weights & failure penalties"
                onPress={() => router.push('/config')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-info/10 items-center justify-center">
                    <SlidersIcon size={15} color={COLORS.info} />
                  </View>
                }
              />
            </ResponsiveFieldGrid>
          </View>

          {/* Needs Attention Panel */}
          <View className="gap-2">
            <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide">
              Needs Attention
            </Text>
            {candidatesError ? (
              <StatusBanner
                tone="danger"
                title="Candidate Telemetry Unavailable"
                message={candidatesError}
              />
            ) : (
              <ResponsiveStatGrid minCardWidth={140} gap={12}>
                <StatCard
                  label="Unreviewed"
                  value={candidatesLoading ? undefined : candidates.filter((c) => !c.best_match?.classification).length}
                  loading={candidatesLoading}
                  tone={candidates.filter((c) => !c.best_match?.classification).length > 0 ? 'warning' : 'neutral'}
                />
                <StatCard
                  label="OCR Warnings"
                  value={candidatesLoading ? undefined : candidates.filter((c) => c.ocr_applied).length}
                  loading={candidatesLoading}
                  tone={candidates.filter((c) => c.ocr_applied).length > 0 ? 'info' : 'neutral'}
                />
                <StatCard
                  label="Failed Parses"
                  value={candidatesLoading ? undefined : candidates.filter((c) => c.page_count === 0).length}
                  loading={candidatesLoading}
                  tone={candidates.filter((c) => c.page_count === 0).length > 0 ? 'danger' : 'neutral'}
                />
              </ResponsiveStatGrid>
            )}
          </View>

          {/* Recent Activity */}
          <View className="gap-2">
            <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide">
              Recent Activity
            </Text>
            {candidatesLoading ? (
              <View className="py-6 items-center justify-center">
                <ActivityIndicator size="small" color={COLORS.primary} />
              </View>
            ) : candidatesError ? (
              <StatusBanner
                tone="danger"
                title="Recent Activity Unavailable"
                message={candidatesError}
              />
            ) : candidates.length === 0 ? (
              <EmptyState variant="compact" title="No recent activity" subtitle="Uploaded CVs will appear here" />
            ) : (
              <ResponsiveFieldGrid minItemWidth={280} gap={10}>
                {candidates.slice(0, 4).map((cand, i) => (
                  <DenseRow
                    key={`${cand.id}-${i}`}
                    title={cand.filename || 'Unknown CV'}
                    subtitle={cand.best_match?.job_title || 'Parsed recently'}
                    onPress={() => router.push(`/candidates/${encodeURIComponent(cand.id)}` as any)}
                  />
                ))}
              </ResponsiveFieldGrid>
            )}
          </View>

          {/* Top Vacancies */}
          <View className="gap-2">
            <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide">
              Top Vacancies
            </Text>
            {jobsLoading ? (
              <View className="py-6 items-center justify-center">
                <ActivityIndicator size="small" color={COLORS.primary} />
              </View>
            ) : jobsError ? (
              <StatusBanner
                tone="danger"
                title="Vacancy Directory Unavailable"
                message={jobsError}
              />
            ) : uniqueJobs.length === 0 ? (
              <EmptyState variant="compact" title="No active vacancies" subtitle="Created job openings will appear here" />
            ) : (
              <ResponsiveFieldGrid minItemWidth={280} gap={10}>
                {uniqueJobs.slice(0, 4).map((job, i) => (
                  <DenseRow
                    key={(job as any).VacancyID || (job as any).id || i}
                    title={(job as any).VacancyTitle || (job as any).title || 'Unknown'}
                    subtitle={(job as any).DepartmentName || (job as any).department || 'General'}
                    onPress={() => {
                      const vId = (job as any).id || (job as any).VacancyID;
                      router.push(vId ? (`/vacancies/${vId}` as any) : `/vacancies`);
                    }}
                  />
                ))}
              </ResponsiveFieldGrid>
            )}
          </View>

          {/* System Health Detailed Box */}
          <View className="gap-2">
            <View className="flex-row justify-between items-center">
              <Text className="text-[11px] font-sans-semibold text-text-faint uppercase tracking-wide">
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
            <ResponsiveFieldGrid minItemWidth={280} gap={10}>
              <DenseRow
                title="FastAPI Server"
                trailing={
                  <Badge
                    label={healthLoading ? 'Checking...' : health?.status === 'offline' || healthError ? 'Offline (Start Server)' : 'Operational'}
                    tone={healthLoading ? 'neutral' : health?.status === 'offline' || healthError ? 'warning' : 'success'}
                  />
                }
              />
              <DenseRow
                title="MSSQL Primary DB"
                trailing={
                  <Badge
                    label={healthLoading ? 'Checking...' : health?.database === 'offline' || healthError ? 'Offline' : 'Operational'}
                    tone={healthLoading ? 'neutral' : health?.database === 'offline' || healthError ? 'warning' : 'success'}
                  />
                }
              />
              <DenseRow
                title="PostgreSQL (Vector DB)"
                trailing={
                  <Badge
                    label={healthLoading ? 'Checking...' : health?.pg_database === 'offline' || healthError ? 'Offline' : 'Operational'}
                    tone={healthLoading ? 'neutral' : health?.pg_database === 'offline' || healthError ? 'warning' : 'success'}
                  />
                }
              />
              <DenseRow
                title="Ollama LLM Model"
                trailing={
                  <Badge
                    label={
                      healthLoading
                        ? 'Checking...'
                        : llmHealth?.status === 'online'
                        ? llmHealth.model_configured || 'Connected'
                        : llmHealth?.status === 'disabled'
                        ? 'Disabled (Confidence Gated)'
                        : 'Offline'
                    }
                    tone={
                      healthLoading
                        ? 'neutral'
                        : llmHealth?.status === 'online'
                        ? 'success'
                        : llmHealth?.status === 'disabled'
                        ? 'info'
                        : 'warning'
                    }
                  />
                }
              />
              <DenseRow
                title="Available LLMs"
                subtitle={
                  healthLoading
                    ? 'Probing Ollama engine...'
                    : llmHealth?.status === 'online'
                    ? llmHealth.available_models?.join(', ') || 'None found'
                    : llmHealth?.status === 'disabled'
                    ? 'Bypass (Fast-Track Rule Engine)'
                    : 'Ollama Unreachable'
                }
              />
            </ResponsiveFieldGrid>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
