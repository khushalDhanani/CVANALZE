import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ArrowLeft, Award, FileText, CheckCircle, AlertCircle, CpuIcon, Edit3, RefreshCw, X, Clock, Mail, Phone, UserCheck, Briefcase, Target, CheckCircle2, Sparkles, AlertTriangle, Users } from 'lucide-react-native';
import { candidateService } from '@/services/candidateService';
import { cvService } from '@/services/cvService';
import { CandidateRecommendationsResponse, CVUploadResponse, JobMatchScore } from '@/types/api';
import { Card, Button, Badge, DenseRow } from '@/components/ui';
import { ComponentScoreBar } from '@/components/ui/ComponentScoreBar';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { HrReviewModal } from '@/components/ui/HrReviewModal';
import { StepProgressCard, StepState } from '@/components/ui/StepProgressCard';
import { COLORS } from '@/constants/colors';

export default function CandidateDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [data, setData] = useState<CVUploadResponse | null>(null);
  const [recommendations, setRecommendations] = useState<CandidateRecommendationsResponse | null>(null);
  const [recommendationsLoading, setRecommendationsLoading] = useState<boolean>(true);
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showFullText, setShowFullText] = useState<boolean>(false);
  const [reviewModalVisible, setReviewModalVisible] = useState<boolean>(false);

  // Reprocessing state
  const [reprocessModalVisible, setReprocessModalVisible] = useState<boolean>(false);
  const [isReprocessing, setIsReprocessing] = useState<boolean>(false);
  const [reprocessError, setReprocessError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [reprocessStatusMsg, setReprocessStatusMsg] = useState<string>('Initializing re-analysis...');
  const [stepStates, setStepStates] = useState<StepState[]>([
    'pending',
    'pending',
    'pending',
    'pending',
    'pending',
    'pending',
    'pending',
    'pending',
  ]);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchDetail = () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    candidateService
      .getCandidateById(id)
      .then((res) => {
        setData(res);
        if (res.status === 'COMPLETED' || res.is_complete || res.progress === 100 || res.match_analysis) {
          setIsReprocessing(false);
          stopTimers();
        }
      })
      .catch((err) => setError(err.message || 'Failed to load candidate details.'))
      .finally(() => setLoading(false));

    setRecommendationsLoading(true);
    setRecommendationsError(null);
    candidateService
      .getCandidateRecommendations(id)
      .then((rec) => {
        setRecommendations(rec);
        setRecommendationsError(null);
      })
      .catch((err) => {
        setRecommendationsError(err.message || 'Failed to load candidate recommendations.');
        setRecommendations(null);
      })
      .finally(() => setRecommendationsLoading(false));
  };

  useEffect(() => {
    fetchDetail();

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [id]);

  const stopTimers = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const handleConfirmReprocess = async () => {
    if (!id) return;
    setReprocessModalVisible(false);
    setIsReprocessing(true);
    setReprocessError(null);
    setRecommendations(null);
    setRecommendationsLoading(true);
    setRecommendationsError(null);
    setElapsedSeconds(0);
    setCurrentStepIndex(1);
    setReprocessStatusMsg('Caches purged. Re-running CV analysis pipeline...');
    setStepStates(['completed', 'active', 'pending', 'pending', 'pending', 'pending', 'pending', 'pending']);

    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    try {
      await candidateService.reprocessCandidate(id);
      
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      let pollCount = 0;
      pollTimerRef.current = setInterval(async () => {
        pollCount++;
        try {
          const statusRes: any = await cvService.getCvStatus(id);
          const statusStr = statusRes.status;
          const msg = statusRes.message || statusRes.error || '';
          const pct = statusRes.progress || 0;

          if (msg) setReprocessStatusMsg(msg);

          if (statusStr === 'FAILED') {
            stopTimers();
            setIsReprocessing(false);
            setReprocessError(msg || 'Reprocessing failed.');
            return;
          }

          // Completion check: when job is finished and result contains parsed data or COMPLETED status or max timeout reached (60s)
          const isTerminated =
            statusStr === 'COMPLETED' ||
            statusStr === 'NEW_CV' ||
            statusStr === 'REPROCESSED' ||
            pct >= 100 ||
            statusRes.is_complete ||
            pollCount >= 40 ||
            (statusStr !== 'processing' && (statusRes.match_analysis || statusRes.text || statusRes.markdown));

          if (isTerminated) {
            stopTimers();
            setCurrentStepIndex(7);
            setStepStates(['completed', 'completed', 'completed', 'completed', 'completed', 'completed', 'completed', 'completed']);
            setIsReprocessing(false);
            fetchDetail();
            return;
          }

          // Compute step states
          let nextIdx = 1;
          if (pct >= 85 || statusRes.match_analysis) {
            nextIdx = 6;
          } else if (pct >= 65) {
            nextIdx = 5;
          } else if (pct >= 45) {
            nextIdx = 4;
          } else if (pct >= 25) {
            nextIdx = 3;
          } else if (pct >= 15) {
            nextIdx = 2;
          }

          setCurrentStepIndex(nextIdx);
          setStepStates((prev) => {
            const updated = [...prev];
            for (let i = 0; i < nextIdx; i++) {
              if (updated[i] !== 'skipped') updated[i] = 'completed';
            }
            updated[nextIdx] = 'active';
            return updated;
          });
        } catch (err: any) {
          // Keep polling unless explicit 404
        }
      }, 1500);

    } catch (err: any) {
      stopTimers();
      setIsReprocessing(false);
      setReprocessError(err.message || 'Failed to trigger re-analysis.');
    }
  };

  const analysis = data?.enriched_match_analysis || data?.match_analysis;
  const bestMatch = analysis?.best_match;
  const scanId = data?.scan_id || data?.id || id || '';

  const rawTimestamp = data?.parsed_at || data?.scanned_at || data?.created_at;
  const formattedParsedAt = rawTimestamp
    ? new Date(rawTimestamp).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      })
    : 'N/A';

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
        <View className="flex-row items-center gap-2">
          <Button
            label="Re-run Analysis"
            variant="secondary"
            size="sm"
            icon={<RefreshCw size={14} color={COLORS.primary} />}
            onPress={() => setReprocessModalVisible(true)}
            disabled={isReprocessing}
          />
          <Badge label={data?.is_scanned ? 'OCR Scanned' : 'Native PDF'} tone="info" />
        </View>
      </View>

      <ScrollView className="flex-1 px-3 py-4">
        {/* Active Processing Step Card */}
        {isReprocessing && (
          <View className="mb-4">
            <StepProgressCard
              currentStepIndex={currentStepIndex}
              stepStates={stepStates}
              statusMessage={reprocessStatusMsg}
              elapsedSeconds={elapsedSeconds}
              isComplete={false}
              useLlmEnrichment={true}
            />
          </View>
        )}


        {reprocessError && (
          <Card className="bg-danger/10 border-danger/30 mb-4 flex-row items-center justify-between">
            <View className="flex-row items-center gap-2 flex-1 pr-2">
              <AlertCircle size={16} color={COLORS.danger} />
              <Text className="text-xs font-sans-medium text-danger flex-1">
                {reprocessError}
              </Text>
            </View>
            <Button
              label="Retry"
              variant="secondary"
              size="sm"
              onPress={() => setReprocessModalVisible(true)}
            />
          </Card>
        )}

        {loading && !isReprocessing ? (
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
              <View className="flex-row items-center gap-3">
                <View className="w-10 h-10 rounded-full bg-primary/10 items-center justify-center">
                  <UserCheck size={20} color={COLORS.primary} />
                </View>
                <View className="flex-1">
                  {(data.full_name || data.candidate_name) ? (
                    <Text className="text-base font-sans-bold text-text-primary">
                      {data.full_name || data.candidate_name}
                    </Text>
                  ) : (
                    <Text className="text-base font-sans-bold text-text-faint">
                      Name not detected
                    </Text>
                  )}
                  
                  <View className="flex-row items-center gap-3 mt-1">
                    <View className="flex-row items-center gap-1">
                      <Mail size={12} color="#9CA3AF" />
                      <Text className="text-xs font-sans text-text-muted">{data.email || "—"}</Text>
                    </View>
                    <View className="flex-row items-center gap-1">
                      <Phone size={12} color="#9CA3AF" />
                      <Text className="text-xs font-sans text-text-muted">{data.phone || "—"}</Text>
                    </View>
                  </View>
                </View>
              </View>

              <View className="flex-row items-center gap-1.5 mt-2 flex-wrap">
                <FileText size={12} color={COLORS.textMuted} />
                <Text className="text-[11px] font-sans text-text-muted">
                  File: {data.filename || data.id}
                </Text>
                <Text className="text-[11px] text-text-muted">•</Text>
                <Clock size={12} color={COLORS.textMuted} />
                <Text className="text-[11px] font-sans text-text-muted">
                  Analyzed: {formattedParsedAt}
                </Text>
              </View>

              <View className="flex-row gap-2 mt-1 flex-wrap">
                <Badge label={`${data.page_count || 1} Page(s)`} tone="neutral" />
                {data.ocr_applied && <Badge label="RapidOCR Applied" tone="warning" />}
                {data.status === 'REPROCESSED' && <Badge label="Fresh Analysis" tone="success" />}
              </View>
            </Card>

            {/* AI Career Summary Card */}
            <Card className="border-primary/30 gap-3">
              <View className="flex-row items-center gap-2 border-b border-border pb-2">
                <Briefcase size={16} color={COLORS.primary} />
                <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
                  AI Career Summary
                </Text>
              </View>

              <View className="gap-2">
                <View className="flex-row items-center justify-between flex-wrap gap-1">
                  <Text className="text-xs font-sans-medium text-text-muted">Recommended Dept:</Text>
                  <Badge
                    label={analysis?.recommended_department || analysis?.primary_department || 'General'}
                    tone="info"
                  />
                </View>

                {!!analysis?.professional_domain && (
                  <View className="flex-row items-center justify-between flex-wrap gap-1">
                    <Text className="text-xs font-sans-medium text-text-muted">Professional Domain:</Text>
                    <Text className="text-xs font-sans-bold text-text-primary">
                      {analysis.professional_domain}
                    </Text>
                  </View>
                )}

                {!!analysis?.suitable_job_roles && analysis.suitable_job_roles.length > 0 && (
                  <View className="gap-1 mt-1">
                    <Text className="text-xs font-sans-medium text-text-muted">Suitable Job Roles:</Text>
                    <View className="flex-row flex-wrap gap-1.5">
                      {analysis.suitable_job_roles.map((role, idx) => (
                        <Badge key={idx} label={role} tone="neutral" />
                      ))}
                    </View>
                  </View>
                )}

                {!!analysis?.strengths && analysis.strengths.length > 0 && (
                  <View className="gap-1 mt-1">
                    <Text className="text-xs font-sans-medium text-text-muted">Key Strengths:</Text>
                    {analysis.strengths.map((str, idx) => (
                      <View key={idx} className="flex-row items-center gap-1.5">
                        <CheckCircle2 size={12} color={COLORS.success} />
                        <Text className="text-xs font-sans text-text-primary flex-1">{str}</Text>
                      </View>
                    ))}
                  </View>
                )}

                {!!analysis?.ai_career_summary && (
                  <View className="bg-background p-3 rounded-md border border-border mt-1">
                    <Text className="text-xs font-sans text-text-primary leading-5">
                      {analysis.ai_career_summary}
                    </Text>
                  </View>
                )}
              </View>
            </Card>

            {/* AI Recommendations Panel */}
            {recommendationsLoading ? (
              <Card className="border-info/30 gap-3">
                <View className="flex-row items-center justify-between border-b border-border pb-2">
                  <View className="flex-row items-center gap-2">
                    <Sparkles size={16} color={COLORS.info} />
                    <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
                      AI Recommendations & Talent Intelligence
                    </Text>
                  </View>
                  <Badge label="Analyzing..." tone="info" />
                </View>
                <View className="py-6 items-center justify-center">
                  <ActivityIndicator size="small" color={COLORS.info} />
                  <Text className="text-xs font-sans text-text-muted mt-2">
                    Generating dynamic evidence-based recommendations...
                  </Text>
                </View>
              </Card>
            ) : recommendationsError ? (
              <Card className="border-warning/30 bg-warning/5 gap-2">
                <View className="flex-row items-center gap-2">
                  <AlertTriangle size={16} color={COLORS.warning} />
                  <Text className="text-xs font-sans-medium text-warning flex-1">
                    {recommendationsError}
                  </Text>
                </View>
              </Card>
            ) : !recommendations || (
              (!recommendations.talent_pools || recommendations.talent_pools.length === 0) &&
              (!recommendations.career_transitions || recommendations.career_transitions.length === 0) &&
              (!recommendations.missing_qualifications || recommendations.missing_qualifications.length === 0) &&
              (!recommendations.recommended_certifications || recommendations.recommended_certifications.length === 0) &&
              (!recommendations.related_skills || recommendations.related_skills.length === 0) &&
              (!recommendations.actionable_suggestions || recommendations.actionable_suggestions.length === 0) &&
              (!recommendations.strengths || recommendations.strengths.length === 0)
            ) ? (
              <Card className="border-border bg-surface/50 gap-2">
                <View className="flex-row items-center justify-between border-b border-border pb-2">
                  <View className="flex-row items-center gap-2">
                    <Sparkles size={16} color={COLORS.textMuted} />
                    <Text className="text-sm font-sans-bold text-text-muted uppercase tracking-wider">
                      AI Recommendations & Talent Intelligence
                    </Text>
                  </View>
                  <Badge label="Career Insights" tone="neutral" />
                </View>
                <Text className="text-xs font-sans text-text-muted py-2 leading-5">
                  No specific recommendations or skill gaps identified for this profile. The candidate's background fully matches evaluated requirements or has no unassigned target opportunities.
                </Text>
              </Card>
            ) : (
              <Card className="border-info/40 gap-3">
                <View className="flex-row items-center justify-between border-b border-border pb-2">
                  <View className="flex-row items-center gap-2">
                    <Sparkles size={16} color={COLORS.info} />
                    <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
                      AI Recommendations & Talent Intelligence
                    </Text>
                  </View>
                  {recommendations.overall_match_confidence ? (
                    <Badge label={`${Math.round(recommendations.overall_match_confidence)}% Confidence`} tone="info" />
                  ) : (
                    <Badge label="Career Insights" tone="info" />
                  )}
                </View>

                {/* Candidate Strengths & Highlights */}
                {recommendations.strengths && recommendations.strengths.length > 0 && (
                  <View className="gap-1">
                    <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                      Key Strengths & Highlights:
                    </Text>
                    {recommendations.strengths.map((str, idx) => (
                      <View key={idx} className="flex-row items-center gap-1.5">
                        <CheckCircle2 size={12} color={COLORS.success} />
                        <Text className="text-xs font-sans text-text-primary flex-1">{str}</Text>
                      </View>
                    ))}
                  </View>
                )}

                {/* Actionable Suggestions */}
                {recommendations.actionable_suggestions && recommendations.actionable_suggestions.length > 0 && (
                  <View className="gap-1 mt-1">
                    <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                      Actionable Insights & Guidance:
                    </Text>
                    {recommendations.actionable_suggestions.map((sug, idx) => (
                      <View key={idx} className="bg-info/10 p-2 rounded-md border border-info/20 flex-row items-start gap-1.5">
                        <Text className="text-xs">💡</Text>
                        <Text className="text-xs font-sans text-text-primary flex-1 leading-4">{sug}</Text>
                      </View>
                    ))}
                  </View>
                )}

                {/* Assigned Talent Pools */}
                {recommendations.talent_pools && recommendations.talent_pools.length > 0 && (
                  <View className="gap-1 mt-1">
                    <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                      Assigned Talent Pools:
                    </Text>
                    <View className="flex-row flex-wrap gap-1.5">
                      {recommendations.talent_pools.map((pool, idx) => (
                        <Badge key={idx} label={pool} tone="success" />
                      ))}
                    </View>
                  </View>
                )}

                {/* Career Transition Opportunities */}
                {recommendations.career_transitions && recommendations.career_transitions.length > 0 && (
                  <View className="gap-1.5 mt-1">
                    <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                      Career Transition Opportunities:
                    </Text>
                    {recommendations.career_transitions.map((trans, idx) => (
                      <View key={idx} className="bg-background p-2.5 rounded-md border border-border gap-1">
                        <View className="flex-row justify-between items-center">
                          <Text className="text-xs font-sans-bold text-primary">
                            ➜ {trans.target_role}
                          </Text>
                          <Badge label={`${Math.round(trans.feasibility_score)}% Feasibility`} tone="info" />
                        </View>
                        <Text className="text-[11px] font-sans text-text-muted">
                          {trans.growth_note}
                        </Text>
                      </View>
                    ))}
                  </View>
                )}

                {/* Identified Skill Gaps */}
                {recommendations.missing_qualifications && recommendations.missing_qualifications.length > 0 && (
                  <View className="gap-1 mt-1">
                    <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                      Identified Skill Gaps:
                    </Text>
                    {recommendations.missing_qualifications.map((qual, idx) => (
                      <View key={idx} className="bg-background p-2 rounded-md border border-border gap-1">
                        <View className="flex-row items-center gap-1.5">
                          <AlertTriangle size={12} color={COLORS.warning} />
                          <Text className="text-xs font-sans-medium text-warning flex-1">
                            {qual.requirement} — <Text className="font-sans text-text-muted">{qual.impact}</Text>
                          </Text>
                        </View>
                        {qual.actionable_suggestion && (
                          <Text className="text-[11px] font-sans text-text-muted pl-4">
                            💡 {qual.actionable_suggestion}
                          </Text>
                        )}
                      </View>
                    ))}
                  </View>
                )}

                {/* Recommended Certifications */}
                {recommendations.recommended_certifications && recommendations.recommended_certifications.length > 0 && (
                  <View className="gap-1 mt-1">
                    <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                      Recommended Certifications:
                    </Text>
                    <View className="flex-row flex-wrap gap-1.5">
                      {recommendations.recommended_certifications.map((cert, idx) => (
                        <Badge key={idx} label={`📜 ${cert}`} tone="neutral" />
                      ))}
                    </View>
                  </View>
                )}

                {/* Related Skills Expansion */}
                {recommendations.related_skills && recommendations.related_skills.length > 0 && (
                  <View className="gap-1 mt-1">
                    <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">
                      Semantically Related Skills:
                    </Text>
                    <View className="flex-row flex-wrap gap-1.5">
                      {recommendations.related_skills.map((skill, idx) => (
                        <Badge key={idx} label={skill} tone="neutral" />
                      ))}
                    </View>
                  </View>
                )}
              </Card>
            )}

            {/* Active Vacancy Summary Card */}
            <Card className="gap-3">
              <View className="flex-row items-center justify-between border-b border-border pb-2">
                <View className="flex-row items-center gap-2">
                  <Target size={16} color={analysis?.has_genuine_match ? COLORS.success : COLORS.warning} />
                  <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
                    Active Vacancy Summary
                  </Text>
                </View>
                <Badge
                  label={analysis?.has_genuine_match ? 'Genuine Match' : 'No Active Match'}
                  tone={analysis?.has_genuine_match ? 'success' : 'warning'}
                />
              </View>

              {!analysis?.has_genuine_match ? (
                <View className="bg-warning/10 p-3 rounded-md border border-warning/30 gap-1.5">
                  <View className="flex-row items-center gap-2">
                    <AlertCircle size={16} color={COLORS.warning} />
                    <Text className="text-xs font-sans-bold text-warning">
                      {analysis?.active_vacancy_summary || 'No suitable active vacancy found.'}
                    </Text>
                  </View>
                  <Text className="text-xs font-sans text-text-muted leading-4">
                    None of the active job openings match this candidate's specialized domain ({analysis?.professional_domain || analysis?.recommended_department || 'Current Domain'}). The CV has not been forced to match an unrelated job.
                  </Text>
                </View>
              ) : (
                <View className="gap-2">
                  <View className="bg-success/10 p-3 rounded-md border border-success/30">
                    <Text className="text-xs font-sans text-text-primary leading-5">
                      {analysis?.active_vacancy_summary}
                    </Text>
                  </View>
                </View>
              )}
            </Card>

            {/* Best Job Match Card (Shown if genuine match exists) */}
            {bestMatch && analysis?.has_genuine_match ? (
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

            {/* Semantically Similar Candidates Card */}
            {data?.similar_candidates && data.similar_candidates.length > 0 && (
              <Card className="gap-3">
                <View className="flex-row items-center justify-between border-b border-border pb-2">
                  <View className="flex-row items-center gap-2">
                    <Users size={16} color={COLORS.primary} />
                    <Text className="text-sm font-sans-bold text-text-primary uppercase tracking-wider">
                      Semantically Similar Candidates (pgvector)
                    </Text>
                  </View>
                  <Badge label={`${data.similar_candidates.length} Profiles`} tone="info" />
                </View>

                <View className="gap-2">
                  {data.similar_candidates.map((sim: any, idx: number) => {
                    const simScore = Math.round((sim.similarity_score || sim.score || 0) * 100);
                    return (
                      <DenseRow
                        key={idx}
                        title={sim.full_name || sim.filename || sim.candidate_id || `Candidate ${idx + 1}`}
                        subtitle={sim.primary_department ? `Dept: ${sim.primary_department}` : 'Vector Similarity Match'}
                        onPress={() => router.push(`/candidates/${encodeURIComponent(sim.candidate_id || sim.id)}` as any)}
                        trailing={
                          <Badge
                            label={`${simScore}% Vector Similarity`}
                            tone={simScore >= 80 ? 'success' : simScore >= 60 ? 'info' : 'neutral'}
                          />
                        }
                      />
                    );
                  })}
                </View>
              </Card>
            )}

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

      {/* Reprocess Confirmation Modal */}
      <Modal
        animationType="fade"
        transparent={true}
        visible={reprocessModalVisible}
        onRequestClose={() => setReprocessModalVisible(false)}
      >
        <View className="flex-1 justify-center items-center bg-black/60 px-4">
          <Card className="w-full max-w-md bg-surface p-4 border-border gap-3">
            <View className="flex-row items-center justify-between border-b border-border pb-2">
              <View className="flex-row items-center gap-2">
                <RefreshCw size={18} color={COLORS.primary} />
                <Text className="text-base font-sans-bold text-text-primary">
                  Re-run CV Analysis
                </Text>
              </View>
              <Pressable onPress={() => setReprocessModalVisible(false)}>
                <X size={18} color={COLORS.textMuted} />
              </Pressable>
            </View>

            <Text className="text-xs font-sans text-text-primary leading-5">
              Are you sure you want to re-run analysis for{' '}
              <Text className="font-sans-bold">{data?.filename || scanId}</Text>?
            </Text>

            <View className="bg-warning/10 p-2.5 rounded-md border border-warning/30">
              <Text className="text-xs font-sans text-warning">
                ⚠️ This will purge all cached results (Resume JSON, LLM reasoning, embeddings, match rankings) and reprocess the resume from scratch using the latest pipeline.
              </Text>
            </View>

            <View className="flex-row justify-end gap-2 mt-2">
              <Button
                label="Cancel"
                variant="ghost"
                size="sm"
                onPress={() => setReprocessModalVisible(false)}
              />
              <Button
                label="Confirm & Reprocess"
                variant="primary"
                size="sm"
                icon={<RefreshCw size={14} color="#FFF" />}
                onPress={handleConfirmReprocess}
              />
            </View>
          </Card>
        </View>
      </Modal>
    </SafeAreaView>
  );
}


