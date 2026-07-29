import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { FileText, Upload, Plus, CpuIcon, FolderIcon, SlidersIcon, Users } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { apiClient } from '@/services/apiClient';
import { matchService } from '@/services/matchService';
import { useJobs } from '@/hooks/useJobs';
import { useCandidates } from '@/hooks/useCandidates';
import { LlmHealthResponse, SystemHealthResponse } from '@/types/api';
import { Card, DenseRow, Badge, Button } from '@/components/ui';
import { COLORS } from '@/constants/colors';

export default function HomeScreen() {
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
      <ScrollView className="flex-1 px-3">
        <View className="gap-4 py-4">

          {/* Hero Section */}
          <View className="bg-primary rounded-md p-3 border border-primary shadow-sm" style={{ elevation: 1 }}>
            <View className="flex-row items-center justify-between mb-2">
              <View className="flex-row items-center gap-2">
                <View className="w-8 h-8 rounded-lg bg-surface/20 items-center justify-center">
                  <CpuIcon size={18} color={COLORS.textInverse} />
                </View>
                <Text className="text-xl font-sans-bold text-text-inverse tracking-wide">
                  CV ANALYZER PRO
                </Text>
              </View>
              <Badge label={`v${health?.version || '1.0.0'}`} tone="info" />
            </View>
            <Text className="text-text-inverse opacity-90 text-sm font-sans">
              AI-powered CV extraction, job vacancy matching, and intelligent batch candidate screening.
            </Text>
          </View>

          {/* Quick Stats Grid */}
          <View className="flex-row gap-4">
            <Card className="flex-1">
              <Text className="text-xs font-sans-medium text-text-muted mb-1">
                Active Vacancies
              </Text>
              {jobsLoading ? (
                <ActivityIndicator size="small" className="mt-1 self-start" />
              ) : (
                <Text className="text-2xl font-sans-bold text-primary">
                  {jobs.length}
                </Text>
              )}
              <Text className="text-[11px] text-text-faint mt-1">
                Cached in-memory
              </Text>
            </Card>

            <Card className="flex-1">
              <Text className="text-xs font-sans-medium text-text-muted mb-1">
                LLM Engine
              </Text>
              <Text
                className={`text-2xl font-sans-bold ${llmHealth?.status === 'online'
                  ? 'text-success'
                  : 'text-warning'
                  }`}
              >
                {llmHealth?.status === 'online' ? 'ONLINE' : 'BYPASS'}
              </Text>
              <Text className="text-[11px] text-text-faint mt-1 truncate">
                {llmHealth?.model_configured || 'Confidence Gated'}
              </Text>
            </Card>

            <Card className="flex-1">
              <Text className="text-xs font-sans-medium text-text-muted mb-1">
                Database
              </Text>
              <Text
                className={`text-2xl font-sans-bold ${health?.database === 'online'
                  ? 'text-success'
                  : 'text-text-muted'
                  }`}
              >
                {health?.database?.toUpperCase() || 'ONLINE'}
              </Text>
              <Text className="text-[11px] text-text-faint mt-1">
                SQLite / PostgreSQL
              </Text>
            </Card>
          </View>

          {/* Action Shortcuts */}
          <View>
            <Text className="text-sm font-sans-bold text-text-muted uppercase tracking-wider mb-2">
              Quick Workflows
            </Text>
            <View className="gap-2">
              <DenseRow
                title="Single CV Match & Upload"
                subtitle="Upload PDF/Docx or paste CV text for instant evaluation"
                onPress={() => router.push('/cv-match')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-primary/10 items-center justify-center mr-1">
                    <FileText size={16} color={COLORS.primary} />
                  </View>
                }
              />
              <DenseRow
                title="Candidate Directory"
                subtitle="Browse, search, and review all parsed candidate profiles"
                onPress={() => router.push('/candidates')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-info/10 items-center justify-center mr-1">
                    <Users size={16} color={COLORS.info} />
                  </View>
                }
              />
              <DenseRow
                title="Job Openings Directory"
                subtitle="View active job requirements, skills, and clear cache"
                onPress={() => router.push('/vacancies')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-success/10 items-center justify-center mr-1">
                    <FolderIcon size={16} color={COLORS.success} />
                  </View>
                }
              />
              <DenseRow
                title="Batch Processing"
                subtitle="Evaluate candidates against vacancies with WebSocket progress"
                onPress={() => router.push('/batch')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-warning/10 items-center justify-center mr-1">
                    <Plus size={16} color={COLORS.warning} />
                  </View>
                }
              />
              <DenseRow
                title="Engine Weight Config"
                subtitle="Tune role, skills, domain weights & failure penalties"
                onPress={() => router.push('/config')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-info/10 items-center justify-center mr-1">
                    <SlidersIcon size={16} color={COLORS.info} />
                  </View>
                }
              />
            </View>
          </View>


          {/* System Health Detailed Box */}
          {/* Needs Attention Panel */}
          <View>
            <Text className="text-sm font-sans-bold text-text-muted uppercase tracking-wider mb-2">
              Needs Attention
            </Text>
            <View className="flex-row gap-2">
              <Card className="flex-1 bg-warning/10 border-warning/30 p-3">
                <Text className="text-2xl font-sans-bold text-warning">{candidates.filter(c => !c.best_match?.classification).length}</Text>
                <Text className="text-xs font-sans text-text-primary">Unreviewed</Text>
              </Card>
              <Card className="flex-1 bg-info/10 border-info/30 p-3">
                <Text className="text-2xl font-sans-bold text-info">{candidates.filter(c => c.ocr_applied).length}</Text>
                <Text className="text-xs font-sans text-text-primary">OCR Warnings</Text>
              </Card>
              <Card className="flex-1 bg-danger/10 border-danger/30 p-3">
                <Text className="text-2xl font-sans-bold text-danger">{candidates.filter(c => c.page_count === 0).length}</Text>
                <Text className="text-xs font-sans text-text-primary">Failed Parses</Text>
              </Card>
            </View>
          </View>

          {/* Recent Activity */}
          <View>
            <Text className="text-sm font-sans-bold text-text-muted uppercase tracking-wider mb-2">
              Recent Activity
            </Text>
            <View className="gap-2">
              {candidatesLoading ? (
                <ActivityIndicator size="small" />
              ) : candidates.slice(0, 3).map((cand, i) => (
                <DenseRow
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
            <Text className="text-sm font-sans-bold text-text-muted uppercase tracking-wider mb-2">
              Top Vacancies
            </Text>
            <View className="gap-2">
              {jobsLoading ? (
                <ActivityIndicator size="small" />
              ) : uniqueJobs.slice(0, 3).map((job, i) => (
                <DenseRow
                  key={(job as any).VacancyID || (job as any).id || i}
                  title={(job as any).VacancyTitle || (job as any).title || 'Unknown'}
                  subtitle={(job as any).DepartmentName || (job as any).department || 'General'}
                  onPress={() => router.push(`/vacancies`)}
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
              <Text className="text-sm font-sans-bold text-text-muted uppercase tracking-wider">
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
            <View className="gap-2">
              <DenseRow
                title="FastAPI Server"
                trailing={
                  <Badge
                    label={health?.status === 'offline' ? 'Offline (Start Server)' : 'Operational'}
                    tone={health?.status === 'offline' ? 'warning' : 'success'}
                  />
                }
              />
              <DenseRow
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
