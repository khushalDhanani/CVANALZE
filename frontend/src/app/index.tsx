import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { FileText, Upload, Plus, CpuIcon, FolderIcon, SlidersIcon } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { apiClient } from '@/services/apiClient';
import { matchService } from '@/services/matchService';
import { useJobs } from '@/hooks/useJobs';
import { LlmHealthResponse, SystemHealthResponse } from '@/types/api';
import { Card, DenseRow, Badge, Button } from '@/components/ui';

export default function HomeScreen() {
  const router = useRouter();
  const { jobs, loading: jobsLoading } = useJobs();
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

  return (
    <SafeAreaView className="flex-1 bg-background">
      <ScrollView className="flex-1 px-3">
        <View className="gap-4 py-4">

          {/* Hero Section */}
          <Card className="bg-primary border-primary">
            <View className="flex-row items-center justify-between mb-2">
              <View className="flex-row items-center gap-2">
                <View className="w-8 h-8 rounded-lg bg-surface/20 items-center justify-center">
                  <CpuIcon size={18} color="#FFFFFF" />
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
          </Card>

          {/* Quick Stats Grid */}
          <View className="flex-row gap-3">
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
                    <FileText size={16} color="#4F46E5" />
                  </View>
                }
              />
              <DenseRow
                title="Job Openings Directory"
                subtitle="View active job requirements, skills, and clear cache"
                onPress={() => router.push('/vacancies')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-success/10 items-center justify-center mr-1">
                    <FolderIcon size={16} color="#16A34A" />
                  </View>
                }
              />
              <DenseRow
                title="Batch Processing"
                subtitle="Evaluate candidates against vacancies with WebSocket progress"
                onPress={() => router.push('/batch')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-warning/10 items-center justify-center mr-1">
                    <Plus size={16} color="#D97706" />
                  </View>
                }
              />
              <DenseRow
                title="Engine Weight Config"
                subtitle="Tune role, skills, domain weights & failure penalties"
                onPress={() => router.push('/config')}
                trailing={
                  <View className="w-8 h-8 rounded-full bg-info/10 items-center justify-center mr-1">
                    <SlidersIcon size={16} color="#2563EB" />
                  </View>
                }
              />
            </View>
          </View>

          {/* System Health Detailed Box */}
          <Card className="mb-4">
            <View className="flex-row justify-between items-center mb-3">
              <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider">
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
              <View className="flex-row justify-between items-center py-1 border-b border-border">
                <Text className="text-xs font-sans text-text-primary">FastAPI Server</Text>
                <Badge
                  label={health?.status === 'offline' ? 'Offline (Start Server)' : 'Operational'}
                  tone={health?.status === 'offline' ? 'warning' : 'success'}
                />
              </View>
              <View className="flex-row justify-between items-center py-1 border-b border-border">
                <Text className="text-xs font-sans text-text-primary">Ollama LLM Model</Text>
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
              </View>
              <View className="flex-row justify-between items-center py-1">
                <Text className="text-xs font-sans text-text-primary">Available LLMs</Text>
                <Text className="text-xs font-sans-medium text-text-muted">
                  {llmHealth?.status === 'online'
                    ? llmHealth.available_models?.join(', ') || 'None found'
                    : llmHealth?.status === 'disabled'
                      ? 'Bypass (Fast-Track Rule Engine)'
                      : 'Ollama Unreachable'}
                </Text>
              </View>
            </View>
          </Card>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
