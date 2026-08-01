import * as DocumentPicker from 'expo-document-picker';
import React, { useEffect, useState } from 'react';
import {
  Platform,
  ScrollView,
  Switch,
  Text,
  View,
} from 'react-native';
import { Edit3, FileText, FolderIcon } from 'lucide-react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { HrReviewModal } from '@/components/ui/HrReviewModal';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { useCvUpload } from '@/hooks/useCvUpload';
import { matchService } from '@/services/matchService';
import { usePageTitle } from '@/hooks/usePageTitle';
import { CandidateMatchAnalysis, JobMatchScore } from '@/types/api';
import {
  Card,
  Button,
  TextField,
  Badge,
  DenseRow,
  SegmentedControl,
  MatchAnalysisCard,
  StepProgressCard,
  StepState,
  Breadcrumbs,
} from '@/components/ui';
import { COLORS } from '@/constants/colors';

export default function CvMatchScreen() {
  usePageTitle('CV Match Analysis | AIRIS');
  const router = useRouter();
  const params = useLocalSearchParams<{ tab?: 'file' | 'text' }>();

  const [activeTab, setActiveTab] = useState<'file' | 'text'>(params.tab || 'file');

  useEffect(() => {
    if (activeTab) {
      router.setParams({ tab: activeTab });
    }
  }, [activeTab]);
  const [cvText, setCvText] = useState<string>('');
  const [useLlmEnrichment, setUseLlmEnrichment] = useState<boolean>(true);
  const [analyzingText, setAnalyzingText] = useState<boolean>(false);
  const [textError, setTextError] = useState<string | null>(null);
  const [textAnalysis, setTextAnalysis] = useState<CandidateMatchAnalysis | null>(null);

  const {
    uploading,
    isComplete,
    statusMessage,
    error: uploadError,
    basicResult,
    enrichedResult,
    elapsedSeconds,
    currentStepIndex,
    stepStates,
    uploadAndProcess,
  } = useCvUpload();

  const [selectedJobForReview, setSelectedJobForReview] = useState<JobMatchScore | null>(null);
  const [reviewModalVisible, setReviewModalVisible] = useState<boolean>(false);

  const handleAnalyzeText = async () => {
    if (!cvText.trim()) {
      setTextError('Please enter or paste CV text first.');
      return;
    }

    setAnalyzingText(true);
    setTextError(null);
    try {
      const result = await matchService.analyzeCvText(cvText);
      setTextAnalysis(result as any);
    } catch (err: any) {
      setTextError(err.message || 'Failed to analyze CV text');
    } finally {
      setAnalyzingText(false);
    }
  };

  const handlePickAndUploadFile = async () => {
    if (Platform.OS === 'web') {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = '.pdf,.doc,.docx,.txt';
      input.onchange = (e: any) => {
        const selectedFile = e.target?.files?.[0];
        if (selectedFile) {
          uploadAndProcess(
            {
              uri: URL.createObjectURL(selectedFile),
              name: selectedFile.name,
              type: selectedFile.type || 'application/pdf',
              rawFile: selectedFile,
            },
            useLlmEnrichment
          );
        }
      };
      input.click();
    } else {
      try {
        const result = await DocumentPicker.getDocumentAsync({
          type: [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
          ],
          copyToCacheDirectory: true,
        });

        if (!result.canceled && result.assets && result.assets.length > 0) {
          const picked = result.assets[0];
          uploadAndProcess(
            {
              uri: picked.uri,
              name: picked.name,
              type: picked.mimeType || 'application/pdf',
              rawFile: (picked as any).file,
            },
            useLlmEnrichment
          );
        }
      } catch (err: any) {
        console.warn('Native document picker failed:', err);
      }
    }
  };

  const currentAnalysis =
    activeTab === 'file'
      ? enrichedResult || (basicResult?.match_analysis as any)
      : textAnalysis;

  const scanId =
    currentAnalysis?.scan_id || basicResult?.scan_id || 'manual_text_scan';

  const showProgressCard = activeTab === 'file' && (uploading || isComplete || !!uploadError || currentStepIndex > 0);

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'CV Match Analysis' }]} />
      <ScrollView className="flex-1 px-3 py-4">
        <View className="gap-4 mb-4">
          {/* Header */}
          <View>
            <Text className="text-xl font-sans-bold text-text-primary mb-1">
              CV Parsing & Job Match Analysis
            </Text>
            <Text className="text-xs font-sans text-text-muted">
              Analyze candidate resumes against active job vacancies with Docling extraction, rule-based scoring, and LLM semantic enrichment.
            </Text>
          </View>

          {/* Mode Selector Tabs - Upload CV File as First & Default active tab */}
          <SegmentedControl
            options={[
              {
                value: 'file',
                label: 'Upload CV File',
                icon: (props) => <FolderIcon {...props} />,
                accessibilityLabel: 'Upload Resume File',
              },
              {
                value: 'text',
                label: 'Paste Raw CV Text',
                icon: (props) => <Edit3 {...props} />,
                accessibilityLabel: 'Paste Raw CV Text',
              },
            ]}
            value={activeTab}
            onChange={(val) => setActiveTab(val as 'file' | 'text')}
          />

          {/* LLM Enrichment Switch */}
          <Card className="flex-row items-center justify-between">
            <View className="flex-1 pr-2">
              <Text className="text-xs font-sans-bold text-text-primary">
                Enable LLM Semantic Enrichment
              </Text>
              <Text className="text-[11px] font-sans text-text-muted">
                Uses local Ollama model to infer implicit skills and boost match scores.
              </Text>
            </View>
            <Switch
              value={useLlmEnrichment}
              onValueChange={setUseLlmEnrichment}
              trackColor={{ false: COLORS.border, true: COLORS.primaryLight }}
              thumbColor={useLlmEnrichment ? COLORS.primary : COLORS.textFaint}
            />
          </Card>

          {/* TAB 1: Upload File (Default & Primary Tab) */}
          {activeTab === 'file' && (
            <View className="gap-3">
              {/* File Upload Drop Area */}
              <View className="bg-surface border-2 border-dashed border-border rounded-md p-6 items-center justify-center">
                <View className="w-12 h-12 rounded-full bg-primary/10 items-center justify-center mb-2">
                  <FileText size={24} color={COLORS.primary} />
                </View>
                <Text className="text-sm font-sans-bold text-text-primary mb-1">
                  Upload Resume File
                </Text>
                <Text className="text-xs font-sans text-text-muted text-center mb-4">
                  Docling will extract text from PDF, DOCX, or Image resumes automatically.
                </Text>

                <Button
                  label={uploading ? 'Processing Resume...' : 'Select File & Match'}
                  onPress={handlePickAndUploadFile}
                  loading={uploading}
                  disabled={uploading}
                  size="md"
                />
              </View>

              {/* Step-by-Step Modern Progress UI */}
              {showProgressCard && (
                <StepProgressCard
                  currentStepIndex={currentStepIndex}
                  stepStates={stepStates}
                  elapsedSeconds={elapsedSeconds}
                  statusMessage={statusMessage}
                  error={uploadError}
                  useLlmEnrichment={useLlmEnrichment}
                  onRetry={handlePickAndUploadFile}
                  isProcessing={uploading}
                  isComplete={isComplete}
                />
              )}
            </View>
          )}

          {/* TAB 2: Paste Raw CV Text */}
          {activeTab === 'text' && (
            <View className="gap-3">
              <TextField
                label="Candidate CV Content:"
                value={cvText}
                onChangeText={setCvText}
                multiline
                numberOfLines={8}
                placeholder="Paste candidate resume/CV text here..."
                style={{ textAlignVertical: 'top', height: 144 }}
                error={textError || undefined}
              />

              <Button
                label={analyzingText ? 'Analyzing CV...' : 'Run Job Match Analysis'}
                onPress={handleAnalyzeText}
                loading={analyzingText}
                disabled={analyzingText}
                size="md"
              />
            </View>
          )}

          {/* ANALYSIS RESULTS SECTION */}
          {currentAnalysis && (
            <View className="gap-4">
              <Text className="text-base font-sans-bold text-text-primary border-b border-border pb-2">
                Match Results Summary
              </Text>

              {/* Best Match Card */}
              <MatchAnalysisCard
                bestMatch={currentAnalysis.best_match}
                candidateName={currentAnalysis.full_name || currentAnalysis.candidate_name}
                onReviewPress={() => {
                  setSelectedJobForReview(currentAnalysis.best_match!);
                  setReviewModalVisible(true);
                }}
              />

              {/* Other Suitable Openings */}
              {currentAnalysis.suitable_openings?.length > 1 && (
                <View className="gap-2 mt-2">
                  <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider">
                    Other Suitable Vacancies ({currentAnalysis.suitable_openings.length - 1})
                  </Text>

                  {currentAnalysis.suitable_openings
                    .filter(
                      (j: JobMatchScore) => j.job_id !== currentAnalysis.best_match?.job_id
                    )
                    .map((job: JobMatchScore) => (
                      <DenseRow
                        key={job.job_id}
                        title={job.job_title}
                        subtitle={job.ranking_reason}
                        trailing={
                          <View className="flex-row items-center gap-1.5">
                            {!!job.retrieval_source && (
                              <Badge
                                label={
                                  job.retrieval_source === 'both' || job.retrieval_source === 'hybrid'
                                    ? 'Hybrid'
                                    : job.retrieval_source === 'vector'
                                      ? 'pgvector'
                                      : 'Keyword'
                                }
                                tone={
                                  job.retrieval_source === 'both' || job.retrieval_source === 'hybrid'
                                    ? 'success'
                                    : job.retrieval_source === 'vector'
                                      ? 'info'
                                      : 'neutral'
                                }
                              />
                            )}
                            <ScoreBadge
                              score={job.overall_score}
                              classification={job.classification}
                            />
                          </View>
                        }
                        onPress={() => {
                          setSelectedJobForReview(job);
                          setReviewModalVisible(true);
                        }}
                      />
                    ))}
                </View>
              )}
            </View>
          )}

          {/* HR Review Modal */}
          <HrReviewModal
            visible={reviewModalVisible}
            scanId={scanId}
            job={selectedJobForReview}
            onClose={() => setReviewModalVisible(false)}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
