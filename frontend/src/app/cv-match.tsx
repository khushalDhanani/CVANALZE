import React, { useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  Switch,
  Text,
  View,
} from 'react-native';
import { Edit3, Folder, FileText, Award, AlertTriangle, CpuIcon, FolderIcon } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ComponentScoreBar } from '@/components/ui/ComponentScoreBar';
import { HrReviewModal } from '@/components/ui/HrReviewModal';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { useCvUpload } from '@/hooks/useCvUpload';
import { matchService } from '@/services/matchService';
import { CandidateMatchAnalysis, JobMatchScore, MandatoryFailure } from '@/types/api';
import { Card, Button, TextField, Badge, DenseRow } from '@/components/ui';

export default function CvMatchScreen() {
  const [activeTab, setActiveTab] = useState<'text' | 'file'>('text');
  const [cvText, setCvText] = useState<string>('');
  const [useLlmEnrichment, setUseLlmEnrichment] = useState<boolean>(true);
  const [analyzingText, setAnalyzingText] = useState<boolean>(false);
  const [textError, setTextError] = useState<string | null>(null);
  const [textAnalysis, setTextAnalysis] =
    useState<CandidateMatchAnalysis | null>(null);

  const {
    uploading,
    statusMessage,
    error: uploadError,
    basicResult,
    enrichedResult,
    uploadAndProcess,
  } = useCvUpload();

  const [selectedJobForReview, setSelectedJobForReview] =
    useState<JobMatchScore | null>(null);
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
      setTextAnalysis(result);
    } catch (err: any) {
      setTextError(err.message || 'Failed to analyze CV text');
    } finally {
      setAnalyzingText(false);
    }
  };

  const handlePickAndUploadFile = () => {
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
      uploadAndProcess(
        {
          uri: 'file:///sample.pdf',
          name: 'Sample_Candidate_CV.pdf',
          type: 'application/pdf',
        },
        useLlmEnrichment
      );
    }
  };

  const currentAnalysis =
    activeTab === 'text'
      ? textAnalysis
      : enrichedResult || (basicResult?.match_analysis as any);

  const scanId =
    currentAnalysis?.scan_id || basicResult?.scan_id || 'manual_text_scan';

  return (
    <SafeAreaView className="flex-1 bg-background">
      <ScrollView className="flex-1 px-3 py-4">
        <View className="gap-4 mb-8">
          {/* Header */}
          <View>
            <Text className="text-xl font-sans-bold text-text-primary mb-1">
              CV Parsing & Job Match Analysis
            </Text>
            <Text className="text-xs font-sans text-text-muted">
              Analyze candidates against active job vacancies with rule-based scoring and LLM semantic enrichment.
            </Text>
          </View>

          {/* Mode Selector Tabs */}
          <View className="flex-row bg-surface border border-border p-1 rounded-md">
            <Pressable
              onPress={() => setActiveTab('text')}
              className={`flex-1 py-2 rounded-sm items-center flex-row justify-center gap-1.5 ${activeTab === 'text' ? 'bg-primary active:bg-primary-dark' : 'bg-transparent active:bg-background'
                }`}
            >
              <Edit3
                size={14}
                color={activeTab === 'text' ? '#FFFFFF' : '#9CA3AF'}
              />
              <Text
                className={`text-xs font-sans-bold ${activeTab === 'text' ? 'text-text-inverse' : 'text-text-muted'
                  }`}
              >
                Paste Raw CV Text
              </Text>
            </Pressable>

            <Pressable
              onPress={() => setActiveTab('file')}
              className={`flex-1 py-2 rounded-sm items-center flex-row justify-center gap-1.5 ${activeTab === 'file' ? 'bg-primary active:bg-primary-dark' : 'bg-transparent active:bg-background'
                }`}
            >
              <FolderIcon
                size={14}
                color={activeTab === 'file' ? '#FFFFFF' : '#9CA3AF'}
              />
              <Text
                className={`text-xs font-sans-bold ${activeTab === 'file' ? 'text-text-inverse' : 'text-text-muted'
                  }`}
              >
                Upload CV File
              </Text>
            </Pressable>
          </View>

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
              trackColor={{ false: '#E5E7EB', true: '#818CF8' }}
              thumbColor={useLlmEnrichment ? '#4F46E5' : '#9CA3AF'}
            />
          </Card>

          {/* TAB 1: Paste Text */}
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

          {/* TAB 2: Upload File */}
          {activeTab === 'file' && (
            <View className="gap-3">
              <View className="bg-surface border-2 border-dashed border-border rounded-md p-6 items-center justify-center">
                <View className="w-12 h-12 rounded-full bg-primary/10 items-center justify-center mb-2">
                  <FileText size={24} color="#4F46E5" />
                </View>
                <Text className="text-sm font-sans-bold text-text-primary mb-1">
                  Upload Resume File
                </Text>
                <Text className="text-xs font-sans text-text-muted text-center mb-4">
                  Docling will extract text from PDF, DOCX, or Image resumes automatically.
                </Text>

                <Button
                  label={uploading ? 'Processing File...' : 'Select File & Match'}
                  onPress={handlePickAndUploadFile}
                  loading={uploading}
                  disabled={uploading}
                  size="md"
                />
              </View>

              {!!statusMessage && (
                <Card className="bg-info/10 border-info/30 flex-row items-center gap-2">
                  {uploading && <ActivityIndicator size="small" color="#2563EB" />}
                  <Text className="text-xs text-info font-sans-medium">
                    {statusMessage}
                  </Text>
                </Card>
              )}

              {!!uploadError && (
                <Card className="bg-danger/10 border-danger/30">
                  <Text className="text-xs text-danger font-sans-medium">
                    {uploadError}
                  </Text>
                </Card>
              )}
            </View>
          )}

          {/* ANALYSIS RESULTS SECTION */}
          {currentAnalysis && (
            <View className="gap-4">
              <Text className="text-base font-sans-bold text-text-primary border-b border-border pb-2">
                Match Results Summary
              </Text>

              {/* Best Match Card */}
              {currentAnalysis.best_match ? (
                <Card className="border-primary/40 shadow-sm gap-3">
                  <View className="flex-row justify-between items-start">
                    <View className="flex-1 pr-2">
                      <View className="flex-row items-center gap-1 mb-1">
                        <Award size={14} color="#4F46E5" />
                        <Text className="text-xs font-sans-bold text-primary uppercase tracking-wider">
                          Best Matched Job
                        </Text>
                      </View>
                      <Text className="text-lg font-sans-bold text-text-primary">
                        {currentAnalysis.best_match.job_title}
                      </Text>
                      {!!currentAnalysis.best_match.department_name && (
                        <Text className="text-xs font-sans-medium text-text-muted">
                          Dept: {currentAnalysis.best_match.department_name}
                        </Text>
                      )}
                    </View>
                    <ScoreBadge
                      score={currentAnalysis.best_match.overall_score}
                      classification={currentAnalysis.best_match.classification}
                    />
                  </View>

                  {/* Ranking reason */}
                  <View className="bg-background p-2.5 rounded-sm border border-border">
                    <Text className="text-xs font-sans text-text-muted italic">
                      "{currentAnalysis.best_match.ranking_reason}"
                    </Text>
                  </View>

                  {/* LLM Reason if available */}
                  {!!currentAnalysis.best_match.llm_reason && (
                    <Card className="bg-info/10 border-info/30 p-3">
                      <View className="flex-row items-center gap-1.5 mb-1">
                        <AlertTriangle size={14} color="#2563EB" />
                        <Text className="text-xs font-sans-bold text-info">
                          LLM Reasoning & Synthesis:
                        </Text>
                      </View>
                      <Text className="text-xs font-sans text-info">
                        {currentAnalysis.best_match.llm_reason}
                      </Text>
                    </Card>
                  )}

                  {/* Mandatory Failures */}
                  {currentAnalysis.best_match.mandatory_fails?.length > 0 && (
                    <Card className="bg-danger/10 border-danger/30 p-3">
                      <View className="flex-row items-center gap-1.5 mb-1">
                        <CpuIcon size={14} color="#DC2626" />
                        <Text className="text-xs font-sans-bold text-danger">
                          Mandatory Requirement Failures:
                        </Text>
                      </View>
                      {currentAnalysis.best_match.mandatory_fails.map(
                        (fail: MandatoryFailure, idx: number) => (
                          <Text key={idx} className="text-xs font-sans-medium text-danger">
                            • {fail.requirement}: {fail.details}
                          </Text>
                        )
                      )}
                    </Card>
                  )}

                  {/* Component Breakdown */}
                  {!!currentAnalysis.best_match.component_scores && (
                    <View>
                      <Text className="text-xs font-sans-bold text-text-muted mb-1">
                        Sub-Score Breakdown:
                      </Text>
                      <ComponentScoreBar
                        scores={currentAnalysis.best_match.component_scores}
                      />
                    </View>
                  )}

                  {/* HR Feedback Trigger */}
                  <Button
                    label="Submit HR Review & Correction"
                    variant="secondary"
                    onPress={() => {
                      setSelectedJobForReview(currentAnalysis.best_match!);
                      setReviewModalVisible(true);
                    }}
                  />
                </Card>
              ) : (
                <Card>
                  <Text className="text-xs font-sans text-text-muted text-center">
                    No matching jobs met the minimum threshold criteria.
                  </Text>
                </Card>
              )}

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
                          <ScoreBadge
                            score={job.overall_score}
                            classification={job.classification}
                          />
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
