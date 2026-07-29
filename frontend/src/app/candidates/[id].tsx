import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, Award, FileText, CheckCircle, AlertCircle, CpuIcon, Edit3 } from 'lucide-react-native';
import { candidateService } from '@/services/candidateService';
import { CVUploadResponse, JobMatchScore } from '@/types/api';
import { Card, Button, Badge, DenseRow } from '@/components/ui';
import { ComponentScoreBar } from '@/components/ui/ComponentScoreBar';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { HrReviewModal } from '@/components/ui/HrReviewModal';
import { COLORS } from '@/constants/colors';

export default function CandidateDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [data, setData] = useState<CVUploadResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showFullText, setShowFullText] = useState<boolean>(false);
  const [reviewModalVisible, setReviewModalVisible] = useState<boolean>(false);

  const fetchDetail = () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    candidateService
      .getCandidateById(id)
      .then((res) => setData(res))
      .catch((err) => setError(err.message || 'Failed to load candidate details.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  const analysis = data?.enriched_match_analysis || data?.match_analysis;
  const bestMatch = analysis?.best_match;
  const scanId = data?.scan_id || data?.id || id || '';

  return (
    <SafeAreaView className="flex-1 bg-background">
      {/* Top Header */}
      <View className="flex-row items-center justify-between px-3 py-2 bg-surface border-b border-border">
        <View className="flex-row items-center gap-2">
          <Button
            icon={<ArrowLeft size={18} color={COLORS.primary} />}
            variant="ghost"
            size="sm"
            onPress={() => router.back()}
          />
          <Text className="text-base font-sans-bold text-text-primary">
            Candidate Profile
          </Text>
        </View>
        <Badge label={data?.is_scanned ? 'OCR Scanned' : 'Native PDF'} tone="info" />
      </View>

      <ScrollView className="flex-1 px-3 py-4">
        {loading ? (
          <View className="flex-1 justify-center items-center py-16">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">Loading candidate profile...</Text>
          </View>
        ) : error || !data ? (
          <Card className="bg-danger/10 border-danger/30">
            <Text className="text-xs font-sans-medium text-danger">
              {error || 'Candidate record not found.'}
            </Text>
            <View className="mt-3 self-start">
              <Button label="Back to Directory" variant="secondary" onPress={() => router.back()} />
            </View>
          </Card>
        ) : (
          <View className="gap-4 pb-8">
            {/* Candidate Metadata Banner */}
            <Card className="gap-2">
              <View className="flex-row items-center gap-2">
                <View className="w-10 h-10 rounded-full bg-primary/10 items-center justify-center">
                  <FileText size={20} color={COLORS.primary} />
                </View>
                <View className="flex-1">
                  <Text className="text-base font-sans-bold text-text-primary">
                    {data.filename || data.id}
                  </Text>
                  <Text className="text-xs font-sans text-text-muted">
                    ID: {data.id} • Parsed: {data.parsed_at ? new Date(data.parsed_at).toLocaleDateString() : 'N/A'}
                  </Text>
                </View>
              </View>

              <View className="flex-row gap-2 mt-1">
                <Badge label={`${data.page_count || 1} Page(s)`} tone="neutral" />
                <Badge label={`${data.characters || 0} Chars`} tone="neutral" />
                {data.ocr_applied && <Badge label="RapidOCR Applied" tone="warning" />}
              </View>
            </Card>

            {/* Best Job Match Card */}
            {bestMatch ? (
              <Card className="border-primary/40 gap-3">
                <View className="flex-row justify-between items-start">
                  <View className="flex-1 pr-2">
                    <View className="flex-row items-center gap-2 mb-1 flex-wrap">
                      <View className="flex-row items-center gap-1">
                        <Award size={14} color={COLORS.primary} />
                        <Text className="text-xs font-sans-bold text-primary uppercase tracking-wider">
                          Top Job Match
                        </Text>
                      </View>
                      {!!bestMatch.retrieval_source && (
                        <Badge
                          label={
                            bestMatch.retrieval_source === 'both' || bestMatch.retrieval_source === 'hybrid'
                              ? 'Hybrid (Keyword + Vector)'
                              : bestMatch.retrieval_source === 'vector'
                                ? 'pgvector Match'
                                : 'Keyword Match'
                          }
                          tone={
                            bestMatch.retrieval_source === 'both' || bestMatch.retrieval_source === 'hybrid'
                              ? 'success'
                              : bestMatch.retrieval_source === 'vector'
                                ? 'info'
                                : 'neutral'
                          }
                        />
                      )}
                    </View>
                    <Text className="text-lg font-sans-bold text-text-primary">
                      {bestMatch.job_title}
                    </Text>
                    {!!bestMatch.department_name && (
                      <Text className="text-xs font-sans-medium text-text-muted">
                        Dept: {bestMatch.department_name}
                      </Text>
                    )}
                  </View>
                  <ScoreBadge
                    score={bestMatch.overall_score || bestMatch.score || 0}
                    classification={bestMatch.classification}
                  />
                </View>

                {/* Sub-Score Breakdown */}
                {!!bestMatch.component_scores && (
                  <View>
                    <Text className="text-xs font-sans-bold text-text-muted mb-1">
                      Sub-Score Breakdown:
                    </Text>
                    <ComponentScoreBar scores={bestMatch.component_scores} />
                  </View>
                )}

                {/* Recommendation */}
                {!!bestMatch.recommendation && (
                  <View className="bg-background p-2.5 rounded-md border border-border">
                    <Text className="text-xs font-sans text-text-primary">
                      💡 {bestMatch.recommendation}
                    </Text>
                  </View>
                )}

                <View className="pt-2 border-t border-border flex-row justify-end">
                  <Button
                    label="Submit HR Review"
                    variant="secondary"
                    size="sm"
                    icon={<Edit3 size={14} color={COLORS.primary} />}
                    onPress={() => setReviewModalVisible(true)}
                  />
                </View>
              </Card>
            ) : null}

            {/* Extracted Raw Text / Markdown */}
            <Card>
              <View className="flex-row justify-between items-center mb-2">
                <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider">
                  Extracted CV Text
                </Text>
                <Button
                  label={showFullText ? 'Collapse Text' : 'Expand Full Text'}
                  variant="ghost"
                  size="sm"
                  onPress={() => setShowFullText(!showFullText)}
                />
              </View>

              <Text
                numberOfLines={showFullText ? undefined : 10}
                className="text-xs font-sans text-text-primary bg-background p-3 rounded-md font-mono"
              >
                {data.markdown || data.text || 'No text extracted.'}
              </Text>
            </Card>

            {/* HR Review Modal */}
            {bestMatch && (
              <HrReviewModal
                visible={reviewModalVisible}
                scanId={scanId}
                job={bestMatch}
                onClose={() => setReviewModalVisible(false)}
                onSubmitted={fetchDetail}
              />
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

