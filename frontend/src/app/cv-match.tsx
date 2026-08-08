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
import { useCvUpload, FilePickerAsset } from '@/hooks/useCvUpload';
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
} from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { SUPPORTED_RESUME_FORMATS } from '@/constants/upload';

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
  } = useCvUpload();

  const [selectedJobForReview, setSelectedJobForReview] = useState<JobMatchScore | null>(null);
  const [reviewModalVisible, setReviewModalVisible] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<FilePickerAsset | null>(null);

  const isBusy = uploading || analyzingText;

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
      input.onchange = (e: any) => {
        const selected = e.target?.files?.[0];
        if (selected) {
          triggerUpload({
            uri: URL.createObjectURL(selected),
            name: selected.name,
            type: selected.type || 'application/pdf',
            rawFile: selected,
            size: selected.size,
          });
        }
      };
      input.click();
    } else {
      try {
        const result = await DocumentPicker.getDocumentAsync({
          type: SUPPORTED_RESUME_FORMATS.mimeTypes,
          copyToCacheDirectory: true,
        });

        if (!result.canceled && result.assets && result.assets.length > 0) {
          const picked = result.assets[0];
          triggerUpload({
            uri: picked.uri,
            name: picked.name,
            type: picked.mimeType || 'application/pdf',
            rawFile: (picked as any).file,
            size: picked.size,
          });
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

      {/* Sticky PageHeader */}
      <View className="px-3 py-2.5 bg-surface border-b border-border">
        <Text className="text-base font-sans-bold text-text-primary">
          CV Parsing & Job Match Analysis
        </Text>
        <Text className="text-[11px] font-sans text-text-muted">
          Multi-stage document extraction, rule-based scoring, and semantic LLM enrichment
        </Text>
      </View>

      <ScrollView className="flex-1 px-3 py-4">
        <View className="gap-4 mb-8">
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
              <Card className="items-center justify-center p-6 gap-2 border-border/80">
                <View className="w-12 h-12 rounded-full bg-primary/10 items-center justify-center mb-1">
                  <FileText size={24} color={COLORS.primary} />
                </View>
                <Text className="text-sm font-sans-bold text-text-primary">
                  Select CV Document to Match
                </Text>
                <Text className="text-xs font-sans text-text-muted text-center max-w-md">
                  Supported formats: {SUPPORTED_RESUME_FORMATS.label}. Automatic text and section extraction.
                </Text>

                <View className="mt-2">
                  <Button
                    label={uploading ? 'Processing Resume...' : 'Choose File & Match'}
                    onPress={handlePickAndUploadFile}
                    loading={uploading}
                    disabled={uploading}
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
                style={{ textAlignVertical: 'top', minHeight: 140, maxHeight: 280 }}
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
            <View className="gap-4">
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
                              score={job.overall_score}
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
