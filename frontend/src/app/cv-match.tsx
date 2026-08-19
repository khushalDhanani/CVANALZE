import * as DocumentPicker from 'expo-document-picker';
import React, { useEffect, useState } from 'react';
import {
  Platform,
  ScrollView,
  Switch,
  Text,
  View,
} from 'react-native';
import { Edit3, FileText, FolderIcon, Info } from 'lucide-react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { HrReviewModal } from '@/components/ui/HrReviewModal';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { CandidateProfileSummary } from '@/components/ui/CandidateProfileSummary';
import { useCvUpload } from '@/hooks/useCvUpload';
import type { FilePickerAsset } from '@/hooks/useCvUpload';
import { useCvQueueUploads } from '@/hooks/useCvQueueUploads';
import type { CvQueueUploadFile } from '@/hooks/useCvQueueUploads';
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
  Breadcrumbs,
  ErrorBanner,
  PageHeader,
} from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { SUPPORTED_RESUME_FORMATS } from '@/constants/upload';
import { getCvQueueStateMeta } from '@/utils/cvQueueState';
import { resolveVacancyFitScore } from '@/utils/candidateDetail';

const MAX_FILES_PER_SELECTION = 10;

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
  const [pickerError, setPickerError] = useState<string | null>(null);
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
    forceReanalyze,
    stopProcessing,
    resetUpload,
  } = useCvUpload();
  const {
    items: queuedUploads,
    summary: queueSummary,
    isActive: queueIsActive,
    uploadFiles,
    clearFinished,
    clearAll,
    stopItem,
    stopAll,
    removeItem,
    reprocessItem,
    reprocessFailed,
    hydrationError: queueHydrationError,
  } = useCvQueueUploads();

  const [selectedJobForReview, setSelectedJobForReview] = useState<JobMatchScore | null>(null);
  const [reviewModalVisible, setReviewModalVisible] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<FilePickerAsset | null>(null);

  const isBusy = uploading || queueIsActive || analyzingText;

  const triggerUpload = (file: FilePickerAsset & { size?: number }) => {
    setPickerError(null);
    const size = file.size || (file.rawFile && file.rawFile.size) || 0;
    if (size > SUPPORTED_RESUME_FORMATS.maxSizeBytes) {
      setPickerError(`File exceeds maximum size of 10MB (${(size / (1024 * 1024)).toFixed(1)}MB).`);
      return;
    }
    setSelectedFile(file);
    uploadAndProcess(file, useLlmEnrichment);
  };

  const triggerUploads = (files: CvQueueUploadFile[]) => {
    setPickerError(null);
    if (files.length > MAX_FILES_PER_SELECTION) {
      setPickerError(`Select up to ${MAX_FILES_PER_SELECTION} CVs at a time.`);
      return;
    }
    const oversized = files.find((file) => (file.size || (file.rawFile && file.rawFile.size) || 0) > SUPPORTED_RESUME_FORMATS.maxSizeBytes);
    if (oversized) {
      setPickerError(`${oversized.name} exceeds the maximum size of 10MB.`);
      return;
    }
    if (files.length === 1) {
      triggerUpload(files[0]);
      return;
    }
    setSelectedFile(null);
    uploadFiles(files, useLlmEnrichment);
  };

  const handleRetry = () => {
    if (selectedFile) {
      triggerUpload(selectedFile);
    } else {
      handlePickAndUploadFile();
    }
  };

  const handleAnalyzeText = async () => {
    if (!cvText.trim()) {
      setTextError('Please enter or paste candidate CV text first.');
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
    setPickerError(null);
    if (Platform.OS === 'web') {
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = SUPPORTED_RESUME_FORMATS.accept;
      input.multiple = true;
      input.onchange = (e: any) => {
        const selectedFiles = Array.from(e.target?.files || []) as File[];
        if (selectedFiles.length > 0) {
          triggerUploads(selectedFiles.map((selected) => ({
            uri: URL.createObjectURL(selected),
            name: selected.name,
            type: selected.type || 'application/pdf',
            rawFile: selected,
            size: selected.size,
          })));
        }
      };
      input.click();
    } else {
      try {
        const result = await DocumentPicker.getDocumentAsync({
          type: SUPPORTED_RESUME_FORMATS.mimeTypes,
          copyToCacheDirectory: true,
          multiple: true,
        });

        if (!result.canceled && result.assets && result.assets.length > 0) {
          triggerUploads(result.assets.map((picked) => ({
            uri: picked.uri,
            name: picked.name,
            type: picked.mimeType || 'application/pdf',
            rawFile: (picked as any).file,
            size: picked.size,
          })));
        }
      } catch (err: any) {
        setPickerError(err.message || 'Failed to select document from device storage.');
      }
    }
  };

  const currentAnalysis =
    activeTab === 'file'
      ? enrichedResult || (basicResult?.match_analysis as any)
      : textAnalysis;

  const rawScanId = currentAnalysis?.scan_id || basicResult?.scan_id;
  const hasPersistedScan =
    activeTab === 'file' && !!rawScanId && rawScanId !== 'manual_text_scan' && rawScanId !== 'undefined';
  const scanId = rawScanId || 'manual_text_scan';

  const showProgressCard = activeTab === 'file' && (uploading || isComplete || !!uploadError || currentStepIndex > 0);

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'CV Match Analysis' }]} />

      <PageHeader
        title="CV Parsing & Job Match Analysis"
        subtitle="Multi-stage document extraction, rule-based scoring, and semantic LLM enrichment"
      />

      <ScrollView className="flex-1 px-3 py-3">
        <View className="gap-3 pb-4">
          {/* Mode Selector Tabs with Processing Lock */}
          <View className="gap-1.5">
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
              onChange={(val) => !isBusy && setActiveTab(val as 'file' | 'text')}
            />
            {isBusy && (
              <Text className="text-[11px] font-sans text-text-muted pl-1">
                Tab switching is locked while analysis is in progress.
              </Text>
            )}
          </View>

          {/* LLM Semantic Enrichment Switch */}
          {activeTab === 'file' && (
            <Card className="flex-row items-center justify-between">
              <View className="flex-1 pr-2">
                <Text className="text-xs font-sans-bold text-text-primary">
                  Enable LLM Semantic Enrichment
                </Text>
                <Text className="text-[11px] font-sans text-text-muted">
                  Uses semantic reasoning to infer implicit qualifications and boost score accuracy.
                </Text>
              </View>
              <Switch
                value={useLlmEnrichment}
                onValueChange={setUseLlmEnrichment}
                disabled={isBusy}
                trackColor={{ false: COLORS.border, true: COLORS.primaryLight }}
                thumbColor={useLlmEnrichment ? COLORS.primary : COLORS.textFaint}
              />
            </Card>
          )}

          {/* TAB 1: Upload File */}
          {activeTab === 'file' && (
            <View className="gap-3">
              {/* Document Selection Card */}
              <Card className="items-center justify-center py-4 gap-2 border-border/80">
                <View className="w-10 h-10 rounded-full bg-primary/10 items-center justify-center">
                  <FileText size={20} color={COLORS.primary} />
                </View>
                <Text className="text-sm font-sans-bold text-text-primary">
                  Select CV Documents to Match
                </Text>
                <Text className="text-xs font-sans text-text-muted text-center max-w-md">
                  Select up to {MAX_FILES_PER_SELECTION} files. Supported formats: {SUPPORTED_RESUME_FORMATS.label}. Files are queued in selection order.
                </Text>

                <View className="mt-2">
                  <Button
                    label={isBusy ? 'CV Queue Active...' : 'Choose CVs & Match'}
                    onPress={handlePickAndUploadFile}
                    loading={uploading || queueIsActive}
                    disabled={isBusy}
                    size="md"
                  />
                </View>
              </Card>

              {/* Picker Error Banner */}
              {pickerError && (
                <ErrorBanner
                  title="Document Selection Error"
                  message={pickerError}
                />
              )}

              {queueHydrationError && (
                <ErrorBanner
                  title="Queue Status Unavailable"
                  message={queueHydrationError}
                />
              )}

              {queuedUploads.length > 0 && (
                <Card className="gap-3">
                  <View className="flex-row items-center justify-between gap-2">
                    <View className="flex-1">
                      <Text className="text-sm font-sans-bold text-text-primary">CV Processing Queue</Text>
                      <Text className="text-xs font-sans text-text-muted">Execution order is controlled exclusively by the backend FIFO worker.</Text>
                    </View>
                    <View className="flex-row items-center gap-1.5">
                      {queueIsActive && (
                        <Button label="Stop Queue" variant="destructive" size="sm" onPress={stopAll} />
                      )}
                      {queueSummary.FAILED > 0 && (
                        <Button label="Re-process Failed CVs" variant="destructive" size="sm" onPress={reprocessFailed} />
                      )}
                      {!queueIsActive && (
                        <Button label="Clear Finished" variant="secondary" size="sm" onPress={clearFinished} />
                      )}
                      <Button label="Clear All" variant="secondary" size="sm" onPress={clearAll} />
                    </View>
                  </View>
                  <View className="flex-row flex-wrap gap-1.5">
                    <Badge label={`${queueSummary.PROCESSING} Processing`} tone="info" />
                    <Badge label={`${queueSummary.PENDING} Pending`} tone="neutral" />
                    <Badge label={`${queueSummary.RETRYING} Retrying`} tone="warning" />
                    <Badge label={`${queueSummary.COMPLETED} Completed`} tone="success" />
                    <Badge label={`${queueSummary.FAILED} Failed`} tone="danger" />
                  </View>
                  <View className="gap-1.5">
                    {queuedUploads.map((item) => {
                      const stateMeta = getCvQueueStateMeta(item.state);
                      const tracking = item.jobId ? `Job ${item.jobId}` : 'Preparing upload';
                      const isItemActive = item.state === 'PROCESSING' || item.state === 'PENDING' || item.state === 'RETRYING';
                      return (
                        <DenseRow
                          key={item.clientId}
                          title={item.filename}
                          subtitle={`${tracking} · ${item.progress}% · ${item.errorCode ? `${item.errorCode}: ` : ''}${item.message}${item.syncError ? ` · Refresh error: ${item.syncError}` : ''}`}
                          trailing={
                            <View className="flex-row items-center gap-1.5">
                              {isItemActive && (
                                <Button label="Stop" variant="destructive" size="sm" onPress={() => stopItem(item.clientId)} />
                              )}
                              {item.state === 'FAILED' && (
                                <Button label="Re-process" variant="destructive" size="sm" onPress={() => reprocessItem(item.clientId)} />
                              )}
                              <Button label="Remove" variant="secondary" size="sm" onPress={() => removeItem(item.clientId)} />
                              <Badge label={stateMeta.label} tone={stateMeta.tone} />
                            </View>
                          }
                        />
                      );
                    })}
                  </View>
                </Card>
              )}

              {/* Step-by-Step Modern Progress UI */}
              {showProgressCard && (
                <StepProgressCard
                  currentStepIndex={currentStepIndex}
                  stepStates={stepStates}
                  elapsedSeconds={elapsedSeconds}
                  statusMessage={statusMessage}
                  error={uploadError}
                  useLlmEnrichment={useLlmEnrichment}
                  onRetry={handleRetry}
                  onStop={stopProcessing}
                  onClear={resetUpload}
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
                className="min-h-[112px] max-h-[240px]"
                style={{ textAlignVertical: 'top' }}
                error={textError || undefined}
                helperText="Paste raw plain-text resume content to perform instant semantic vacancy matching."
              />

              <Button
                label={analyzingText ? 'Analyzing CV Content...' : 'Run Job Match Analysis'}
                onPress={handleAnalyzeText}
                loading={analyzingText}
                disabled={analyzingText}
                size="md"
              />
            </View>
          )}

          {/* ANALYSIS RESULTS SECTION */}
          {currentAnalysis && (
            <View className="gap-3">
              <View className="flex-row items-center justify-between border-b border-border pb-2">
                <Text className="text-base font-sans-bold text-text-primary">
                  Match Results Summary
                </Text>
                {hasPersistedScan && (
                  <Button
                    label="Force Re-analyze"
                    variant="secondary"
                    size="sm"
                    onPress={() => forceReanalyze(scanId)}
                    disabled={uploading}
                  />
                )}
              </View>

              {/* Candidate Profile Details */}
              <CandidateProfileSummary analysis={currentAnalysis as any} />

              {/* Best Match Card */}
              <MatchAnalysisCard
                bestMatch={currentAnalysis.best_match}
                candidateName={currentAnalysis.full_name || currentAnalysis.candidate_name}
                onReviewPress={
                  hasPersistedScan
                    ? () => {
                        setSelectedJobForReview(currentAnalysis.best_match!);
                        setReviewModalVisible(true);
                      }
                    : undefined
                }
              />

              {/* Non-persisted scan guidance */}
              {!hasPersistedScan && (
                <View className="bg-surface border border-border rounded-md p-2.5 flex-row items-center gap-2">
                  <Info size={14} color={COLORS.textMuted} />
                  <Text className="text-xs font-sans text-text-muted flex-1">
                    HR Review & score corrections are available when analyzing uploaded documents with a persisted scan record.
                  </Text>
                </View>
              )}

              {/* Other Suitable Openings */}
              {currentAnalysis.suitable_openings && currentAnalysis.suitable_openings.length > 1 && (
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
                              score={resolveVacancyFitScore(job) ?? 0}
                              classification={job.classification}
                            />
                          </View>
                        }
                        onPress={
                          hasPersistedScan
                            ? () => {
                                setSelectedJobForReview(job);
                                setReviewModalVisible(true);
                              }
                            : undefined
                        }
                      />
                    ))}
                </View>
              )}
            </View>
          )}

          {/* HR Review Modal */}
          {hasPersistedScan && (
            <HrReviewModal
              visible={reviewModalVisible}
              scanId={scanId}
              job={selectedJobForReview}
              onClose={() => setReviewModalVisible(false)}
            />
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
