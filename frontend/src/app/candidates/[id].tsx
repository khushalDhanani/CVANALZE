import React, { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft, Award, FileText, CheckCircle, AlertCircle, CpuIcon, Edit3,
  RefreshCw, X, Clock, Mail, Phone, UserCheck, Briefcase, Target,
  CheckCircle2, Sparkles, AlertTriangle, Users, MapPin, Building,
  Activity, Search, BookOpen, Layers
} from 'lucide-react-native';
import { candidateService } from '@/services/candidateService';
import { cvService } from '@/services/cvService';
import { matchService } from '@/services/matchService';
import { CandidateRecommendationsResponse, CVUploadResponse } from '@/types/api';
import {
  Card,
  Button,
  Badge,
  DenseRow,
  FieldConfidenceView,
  Breadcrumbs,
  ExperienceTimelineCard,
  ComponentScoreBar,
  ErrorBanner,
} from '@/components/ui';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import {
  VacancyMatchStatusBadge,
  VacancyFitScoreBreakdownCard,
  getCanonicalMatchStatusMeta,
  normalizeCanonicalMatchStatus,
  resolveVacancyFitScore,
} from '@/components/ui/VacancyMatchStatusBadge';
import { HrReviewModal } from '@/components/ui/HrReviewModal';
import { StepProgressCard, StepState } from '@/components/ui/StepProgressCard';
import { usePageTitle } from '@/hooks/usePageTitle';
import { COLORS } from '@/constants/colors';
import { formatDateTime } from '@/utils/date';

type TabType = 'overview' | 'processing';

export default function CandidateDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id: string; query?: string; classification?: string; department?: string }>();
  const { id, query, classification, department } = params;

  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const [data, setData] = useState<CVUploadResponse | null>(null);
  const candName = data?.full_name || data?.candidate_name || data?.resume_json?.contact_info?.name;
  usePageTitle(candName ? `Candidate: ${candName} | AIRIS` : 'Candidate Profile | AIRIS');

  const getReturnHref = () => {
    const q = new URLSearchParams();
    if (query) q.set('query', query);
    if (classification) q.set('classification', classification);
    if (department) q.set('department', department);
    const str = q.toString();
    return `/candidates${str ? `?${str}` : ''}`;
  };

  const handleBack = () => {
    router.push(getReturnHref() as any);
  };
  const [recommendations, setRecommendations] = useState<CandidateRecommendationsResponse | null>(null);
  const [recommendationsLoading, setRecommendationsLoading] = useState<boolean>(true);
  const [recommendationsError, setRecommendationsError] = useState<string | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showFullText, setShowFullText] = useState<boolean>(false);
  const [showAllExperience, setShowAllExperience] = useState<boolean>(false);
  const [reviewModalVisible, setReviewModalVisible] = useState<boolean>(false);
  const [selectedJobForReview, setSelectedJobForReview] = useState<any>(null);

  // Reprocessing state
  const [reprocessModalVisible, setReprocessModalVisible] = useState<boolean>(false);
  const [isReprocessing, setIsReprocessing] = useState<boolean>(false);
  const [reprocessError, setReprocessError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [reprocessStatusMsg, setReprocessStatusMsg] = useState<string>('Initializing re-analysis...');
  const [stepStates, setStepStates] = useState<StepState[]>(Array(8).fill('pending'));
  const [isReanalyzing, setIsReanalyzing] = useState<boolean>(false);

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
      stopTimers();
    };
  }, [id]);

  const stopTimers = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    timerRef.current = null;
    pollTimerRef.current = null;
  };

  const handleConfirmReprocess = async () => {
    if (!id) return;
    stopTimers();
    setReprocessModalVisible(false);
    setIsReprocessing(true);
    setReprocessError(null);
    setRecommendations(null);
    setRecommendationsLoading(true);
    setRecommendationsError(null);
    setElapsedSeconds(0);
    setCurrentStepIndex(1);
    setReprocessStatusMsg('Caches purged. Re-running CV analysis pipeline...');
    setStepStates(['completed', 'active', ...Array(6).fill('pending')]);
    setActiveTab('processing');

    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    try {
      await candidateService.reprocessCandidate(id);

      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      let pollCount = 0;
      let errorCount = 0;
      pollTimerRef.current = setInterval(async () => {
        pollCount++;

        if (pollCount >= 40) {
          stopTimers();
          setIsReprocessing(false);
          setReprocessError('Reprocessing timed out (TIMED_OUT). Pipeline is taking longer than expected. Please try again.');
          return;
        }

        try {
          const statusRes: any = await cvService.getCvStatus(id);
          const statusStr = statusRes.status;
          const msg = statusRes.message || statusRes.error || '';
          const pct = statusRes.progress || 0;

          if (msg) setReprocessStatusMsg(msg);

          if (statusStr === 'FAILED') {
            stopTimers();
            setIsReprocessing(false);
            setReprocessError(msg || 'Reprocessing failed (FAILED).');
            return;
          }

          const isTerminated =
            statusStr === 'COMPLETED' || statusStr === 'NEW_CV' || statusStr === 'REPROCESSED' ||
            pct >= 100 || statusRes.is_complete ||
            (statusStr !== 'processing' && (statusRes.match_analysis || statusRes.text || statusRes.markdown));

          if (isTerminated) {
            stopTimers();
            setCurrentStepIndex(7);
            setStepStates(Array(8).fill('completed'));
            setIsReprocessing(false);
            fetchDetail();
            return;
          }

          let nextIdx = 1;
          if (pct >= 85 || statusRes.match_analysis) nextIdx = 6;
          else if (pct >= 65) nextIdx = 5;
          else if (pct >= 45) nextIdx = 4;
          else if (pct >= 25) nextIdx = 3;
          else if (pct >= 15) nextIdx = 2;

          setCurrentStepIndex(nextIdx);
          setStepStates((prev) => {
            const updated = [...prev];
            for (let i = 0; i < nextIdx; i++) {
              if (updated[i] !== 'skipped') updated[i] = 'completed';
            }
            updated[nextIdx] = 'active';
            return updated;
          });

          errorCount = 0;
        } catch (err: any) {
          errorCount++;
          if (errorCount >= 3) {
            stopTimers();
            setIsReprocessing(false);
            setReprocessError(err.message || 'Connection lost during polling (CONNECTION_LOST).');
          }
        }
      }, 1500);

    } catch (err: any) {
      stopTimers();
      setIsReprocessing(false);
      setReprocessError(err.message || 'Failed to trigger re-analysis.');
    }
  };

  const handleReanalyze = async () => {
    if (!scanId) return;
    setIsReanalyzing(true);
    try {
      await matchService.reanalyzeScan(scanId);
      setTimeout(() => {
        fetchDetail();
        setIsReanalyzing(false);
      }, 1500);
    } catch (err: any) {
      console.warn('Reanalysis failed:', err);
      setIsReanalyzing(false);
    }
  };

  const rawAnalysis = data?.enriched_match_analysis || data?.match_analysis;
  const analysis: any = rawAnalysis;
  const bestMatch = rawAnalysis?.best_match;
  const scanId = data?.scan_id || data?.id || id || '';

  const rawTimestamp = data?.parsed_at || data?.scanned_at || data?.created_at;
  const formattedParsedAt = formatDateTime(rawTimestamp);

  const getStatusTone = (status?: string): 'success' | 'info' | 'warning' | 'danger' | 'neutral' => {
    if (!status) return 'neutral';
    const s = status.toUpperCase();
    if (s === 'COMPLETED' || s === 'REPROCESSED') return 'success';
    if (s === 'PROCESSING' || s === 'PENDING' || s === 'NEW_CV') return 'info';
    if (s === 'FAILED' || s === 'TIMED_OUT' || s === 'CONNECTION_LOST') return 'danger';
    return 'neutral';
  };

  // -------------------------------------------------------------
  // TAB RENDERERS
  // -------------------------------------------------------------

  const renderOverviewTab = () => (
    <View className="flex-col lg:flex-row gap-4">
      {/* Left Column (Candidate Data) */}
      <View className="w-full lg:w-5/12 gap-4">

        {/* Active Vacancy Summary Card */}
        <Card className="gap-2 p-3 shadow-none border-border">
          <View className="flex-row items-center justify-between pb-2 mb-1 border-b border-border">
            <View className="flex-row items-center gap-1.5">
              <Target size={14} color={analysis?.has_genuine_match ? COLORS.success : COLORS.warning} />
              <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Active Vacancy Summary</Text>
            </View>
            <VacancyMatchStatusBadge
              status={analysis?.match_status || (analysis?.has_genuine_match ? 'MATCHED' : (analysis?.active_vacancy_summary?.includes('NO_ACTIVE_VACANCIES') ? 'NO_ACTIVE_VACANCIES' : 'NO_STRONG_MATCH'))}
              score={resolveVacancyFitScore(bestMatch)}
            />
          </View>
          <View className={`p-2 rounded ${analysis?.has_genuine_match ? 'bg-success/5 border border-success/20' : 'bg-surface border border-border'}`}>
            <Text className="text-xs leading-5 text-text-primary">{analysis?.active_vacancy_summary || 'No suitable active vacancy found.'}</Text>
          </View>

          {/* Render canonical score breakdown if available on best match */}
          {bestMatch?.score_breakdown ? (
            <VacancyFitScoreBreakdownCard
              breakdown={bestMatch.score_breakdown}
              penalty={bestMatch.score_breakdown.hierarchy_mismatch_penalty}
              rejectionReason={bestMatch.domain_mismatch_reason || bestMatch.reason}
            />
          ) : null}
        </Card>

        {/* Contact Info Card with FieldConfidenceView */}
        <Card className="gap-2 p-3 shadow-none border-border">
          <Text className="mb-1 text-xs tracking-wider uppercase font-sans-bold text-text-muted">Contact Information</Text>
          <FieldConfidenceView
            fieldName="email"
            value={data?.email}
            tier={data?.field_confidence_tiers?.name}
            icon={<Mail size={14} color={COLORS.textFaint} />}
            fallbackLabel="Email not specified"
          />
          <FieldConfidenceView
            fieldName="phone"
            value={data?.phone}
            icon={<Phone size={14} color={COLORS.textFaint} />}
            fallbackLabel="Phone not specified"
          />
          <FieldConfidenceView
            fieldName="location"
            value={data?.location || data?.resume_json?.contact_info?.location}
            tier={data?.location_confidence_tier || data?.field_confidence_tiers?.location}
            icon={<MapPin size={14} color={COLORS.textFaint} />}
            fallbackLabel="Location not specified"
          />
        </Card>

        {/* Experience Timeline */}
        {(() => {
          const allExp =
            data?.work_experience ||
            data?.resume_json?.work_experience ||
            data?.resume_json?.experience ||
            data?.normalized_resume?.employment ||
            [];

          if (allExp.length === 0) return null;

          const displayedExp = showAllExperience ? allExp : allExp.slice(0, 5);

          return (
            <Card className="gap-3 p-3 shadow-none border-border">
              <View className="flex-row items-center justify-between">
                <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-muted">Experience History</Text>
                <Text className="text-[11px] font-sans text-text-muted">{allExp.length} roles</Text>
              </View>

              {displayedExp.map((exp: any, idx: number) => {
                const title = typeof exp.job_title === 'object'
                  ? (exp.job_title?.normalized_value || exp.job_title?.raw_value || 'Not specified')
                  : (exp.job_title || exp.role || 'Not specified');
                const company = typeof exp.company === 'object'
                  ? (exp.company?.normalized_value || exp.company?.raw_value || 'Not specified')
                  : (exp.company || exp.company_name || 'Not specified');
                const dates = exp.interval?.raw_value || exp.dates || exp.duration || 'Not specified';
                return (
                  <View key={idx} className="pb-3 pl-3 border-l-2 border-border">
                    <Text className="text-xs font-sans-bold text-text-primary">{title}</Text>
                    <Text className="font-sans text-xs text-text-muted">{company} • {dates}</Text>
                  </View>
                );
              })}

              {allExp.length > 5 && (
                <Pressable
                  onPress={() => setShowAllExperience(!showAllExperience)}
                  className="py-1 min-h-[36px] justify-center"
                  accessibilityRole="button"
                >
                  <Text className="text-xs text-primary font-sans-medium">
                    {showAllExperience ? 'Show fewer roles' : `+ ${allExp.length - 5} more roles`}
                  </Text>
                </Pressable>
              )}
            </Card>
          );
        })()}

        {/* Education & Certs */}
        <Card className="gap-3 p-3 shadow-none border-border">
          <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-muted">Education</Text>
          {(data?.resume_json?.education || []).length > 0 ? (
            data!.resume_json!.education!.slice(0, 3).map((edu: any, idx: number) => (
              <View key={idx}>
                <Text className="text-xs font-sans-bold text-text-primary">{edu.degree || 'Degree not specified'}</Text>
                <Text className="text-[11px] font-sans text-text-muted">{edu.institution || 'Institution not specified'} • {edu.passing_year || 'Year not specified'}</Text>
              </View>
            ))
          ) : (
            <Text className="text-xs text-text-muted">No education history found.</Text>
          )}

          {(data?.resume_json?.certifications || []).length > 0 && (
            <View className="mt-2 border-t border-border pt-2 gap-1.5">
              <Text className="text-[11px] font-sans-bold text-text-muted uppercase tracking-wider">Certifications</Text>
              <View className="flex-row flex-wrap gap-1">
                {data!.resume_json!.certifications!.slice(0, 5).map((cert: string, idx: number) => (
                  <Badge key={idx} label={cert} tone="neutral" />
                ))}
              </View>
            </View>
          )}
        </Card>

        {/* Candidate Skills */}
        {(() => {
          const rawSkills = data?.resume_json?.skills;
          const skillsList: string[] = Array.isArray(rawSkills)
            ? rawSkills.filter((s: any) => typeof s === 'string' && s.trim())
            : (rawSkills?.all_skills || []).filter((s: any) => typeof s === 'string' && s.trim());
          return skillsList.length > 0 ? (
            <Card className="gap-2 p-3 shadow-none border-border">
              <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-muted">Skills</Text>
              <View className="flex-row flex-wrap gap-1">
                {skillsList.map((skill: string, idx: number) => (
                  <Badge key={idx} label={skill} tone="neutral" />
                ))}
              </View>
            </Card>
          ) : null;
        })()}

        {/* Suitable Openings */}
        {analysis?.suitable_openings && analysis.suitable_openings.length > 0 ? (
          analysis.suitable_openings.map((match: any, idx: number) => {
            const rawStatus = match.vacancy_match_status || match.match_status || match.classification;
            const fitScore = resolveVacancyFitScore(match);
            const isTop = idx === 0 && (rawStatus === 'MATCHED' || rawStatus === 'HIGH');
            return (
              <Card key={idx} className={`p-3 border-primary/40 shadow-none gap-2 ${idx > 0 ? 'mt-3 opacity-90 border-border' : ''}`}>
                <View className="flex-row items-start justify-between">
                  <View className="flex-1 pr-2">
                    <View className="flex-row items-center gap-1.5 mb-1">
                      <Award size={14} color={isTop ? COLORS.primary : COLORS.textMuted} />
                      <Text className={`text-xs font-sans-bold uppercase tracking-wider ${isTop ? 'text-primary' : 'text-text-muted'}`}>
                        {isTop ? 'Top Job Match' : 'Evaluated Match'}
                      </Text>
                    </View>
                    <Text className="text-sm font-sans-bold text-text-primary">{match.job_title}</Text>
                    <Text className="text-[11px] font-sans-medium text-text-muted">{match.department_name || match.department}</Text>
                  </View>
                  <VacancyMatchStatusBadge
                    status={rawStatus}
                    score={fitScore}
                  />
                </View>

                {/* Score Breakdown if present */}
                {match.score_breakdown ? (
                  <VacancyFitScoreBreakdownCard
                    breakdown={match.score_breakdown}
                    penalty={match.score_breakdown.hierarchy_mismatch_penalty}
                    rejectionReason={match.domain_mismatch_reason || match.reason}
                  />
                ) : match.component_scores ? (
                  <ComponentScoreBar scores={match.component_scores} />
                ) : null}

                {match.llm_reason ? (
                  <View className="p-2 mt-1 border rounded bg-primary/5 border-primary/10">
                    <Text className="mb-1 text-xs leading-4 text-text-primary font-sans-bold">AI Reasoning:</Text>
                    <Text className="text-xs leading-4 text-text-primary">{match.llm_reason}</Text>
                  </View>
                ) : null}

                {match.missing_skills && match.missing_skills.length > 0 && (
                  <View className="mt-1">
                    <Text className="text-[11px] font-sans-bold text-danger uppercase mb-1">Skill Gaps:</Text>
                    <View className="flex-row flex-wrap gap-1">
                      {match.missing_skills.map((s: string, sIdx: number) => (
                        <Badge key={sIdx} label={s} tone="danger" />
                      ))}
                    </View>
                  </View>
                )}

                {(match.recommendation && !match.llm_reason) ? (
                  <View className="p-2 mt-1 border rounded bg-primary/5 border-primary/10">
                    <Text className="text-xs leading-4 text-text-primary">💡 {match.recommendation}</Text>
                  </View>
                ) : null}

                <View className="flex-row justify-end mt-2">
                  <Button
                    label="HR Review"
                    variant="secondary"
                    size="sm"
                    icon={<Edit3 size={12} color={COLORS.primary} />}
                    onPress={() => {
                      setSelectedJobForReview(match);
                      setReviewModalVisible(true);
                    }}
                  />
                </View>
              </Card>
            );
          })
        ) : bestMatch && analysis?.has_genuine_match ? (
          <Card className="gap-2 p-3 shadow-none border-primary/40">
            <View className="flex-row items-start justify-between">
              <View className="flex-1 pr-2">
                <View className="flex-row items-center gap-1.5 mb-1">
                  <Award size={14} color={COLORS.primary} />
                  <Text className="text-xs tracking-wider uppercase font-sans-bold text-primary">Top Job Match</Text>
                </View>
                <Text className="text-sm font-sans-bold text-text-primary">{bestMatch.job_title}</Text>
                <Text className="text-[11px] font-sans-medium text-text-muted">{bestMatch.department_name}</Text>
              </View>
              <VacancyMatchStatusBadge
                status={bestMatch.vacancy_match_status || (bestMatch as any).match_status || bestMatch.classification}
                score={resolveVacancyFitScore(bestMatch)}
              />
            </View>

            {bestMatch.score_breakdown ? (
              <VacancyFitScoreBreakdownCard
                breakdown={bestMatch.score_breakdown}
                penalty={bestMatch.score_breakdown.hierarchy_mismatch_penalty}
                rejectionReason={bestMatch.domain_mismatch_reason || bestMatch.reason}
              />
            ) : bestMatch.component_scores ? (
              <ComponentScoreBar scores={bestMatch.component_scores} />
            ) : null}

            {bestMatch.recommendation ? (
              <View className="p-2 mt-1 border rounded bg-primary/5 border-primary/10">
                <Text className="text-xs leading-4 text-text-primary">💡 {bestMatch.recommendation}</Text>
              </View>
            ) : null}
            <View className="flex-row justify-end mt-2">
              <Button
                label="HR Review"
                variant="secondary"
                size="sm"
                icon={<Edit3 size={12} color={COLORS.primary} />}
                onPress={() => {
                  setSelectedJobForReview(bestMatch);
                  setReviewModalVisible(true);
                }}
              />
            </View>
          </Card>
        ) : null}

        {/* Unsuitable Openings — Manual Review Required */}
        {analysis?.unsuitable_openings && analysis.unsuitable_openings.length > 0 && (
          <Card className="gap-2 p-3 shadow-none border-warning/30 bg-warning/5">
            <View className="flex-row items-center gap-1.5 mb-1 border-b border-warning/20 pb-2">
              <AlertTriangle size={14} color={COLORS.warning} />
              <Text className="text-xs tracking-wider uppercase font-sans-bold text-warning">
                Manual Review Required ({analysis.unsuitable_openings.length})
              </Text>
            </View>
            <Text className="text-[11px] text-text-muted mb-1">
              These vacancies scored below the suitability threshold. HR review is recommended before any decision.
            </Text>
            {analysis.unsuitable_openings.map((match: any, idx: number) => (
              <View key={idx} className="flex-row items-center justify-between p-2 border rounded bg-background border-border">
                <View className="flex-1 pr-2">
                  <Text className="text-xs font-sans-bold text-text-primary">{match.job_title}</Text>
                  <Text className="text-[11px] text-text-muted">{match.department_name || match.department}</Text>
                </View>
                <View className="flex-row items-center gap-2">
                  <ScoreBadge score={resolveVacancyFitScore(match) ?? 0} classification={match.classification} />
                  <Button
                    label="Review"
                    variant="ghost"
                    size="sm"
                    onPress={() => {
                      setSelectedJobForReview(match);
                      setReviewModalVisible(true);
                    }}
                  />
                </View>
              </View>
            ))}
          </Card>
        )}

        {/* Similar Candidates (pgvector) */}
        {data?.similar_candidates && data.similar_candidates.length > 0 && (
          <Card className="gap-2 p-3 shadow-none border-border">
            <View className="flex-row items-center justify-between pb-2 mb-1 border-b border-border">
              <View className="flex-row items-center gap-1.5">
                <Users size={14} color={COLORS.primary} />
                <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Similar Candidates</Text>
              </View>
              <Badge label={`${data.similar_candidates.length} Profiles`} tone="info" />
            </View>
            <View className="gap-2">
              {data.similar_candidates.map((sim: any, idx: number) => {
                const simScore = Math.round((sim.similarity_score || sim.score || 0) * 100);
                return (
                  <View key={idx} className="flex-row items-center justify-between p-2 border rounded bg-background border-border">
                    <View>
                      <Text className="text-xs cursor-pointer font-sans-bold text-text-primary" onPress={() => router.push(`/candidates/${encodeURIComponent(sim.candidate_id || sim.id)}` as any)}>
                        {sim.full_name || sim.filename || sim.candidate_id}
                      </Text>
                      <Text className="text-[11px] text-text-muted">{sim.primary_department ? `Dept: ${sim.primary_department}` : 'Vector Match'}</Text>
                    </View>
                    <Badge label={`${simScore}%`} tone={simScore >= 80 ? 'success' : simScore >= 60 ? 'info' : 'neutral'} />
                  </View>
                );
              })}
            </View>
          </Card>
        )}

        {/* Resume Extracted Text without Nested ScrollView */}
        <Card className="p-0 overflow-hidden shadow-none border-border">
          <View className="flex-row items-center justify-between p-3 border-b border-border bg-background">
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-muted">Extracted CV Text</Text>
            <Button
              label={showFullText ? 'Collapse' : 'Expand Full'}
              variant="ghost"
              size="sm"
              onPress={() => setShowFullText(!showFullText)}
            />
          </View>
          <View className="p-3 bg-surface">
            <Text
              numberOfLines={showFullText ? undefined : 8}
              className="text-[11px] font-mono text-text-primary leading-5"
            >
              {data?.markdown || data?.text || 'No text extracted.'}
            </Text>
          </View>
        </Card>

      </View>

      {/* Right Column (Hiring Intelligence & Matches) */}
      <View className="w-full lg:w-7/12 gap-4">

        {/* Recommendation Engine */}
        {recommendationsLoading ? (
          <Card className="items-center justify-center p-3 py-8 shadow-none border-info/30">
            <ActivityIndicator size="small" color={COLORS.info} />
            <Text className="mt-2 font-sans text-xs text-text-muted">Running Hiring Intelligence...</Text>
          </Card>
        ) : recommendationsError ? (
          <Card className="gap-1 p-3 shadow-none bg-danger/5 border-danger/30">
            <View className="flex-row items-center justify-between">
              <Text className="text-xs font-sans-bold text-danger">Hiring Intelligence Error</Text>
              <VacancyMatchStatusBadge status="FAILED" />
            </View>
            <Text className="text-xs text-danger">{recommendationsError}</Text>
          </Card>
        ) : recommendations ? (
          <Card className="gap-3 p-3 shadow-none border-info/40">
            <View className="flex-row items-center justify-between pb-2 border-b border-border">
              <View className="flex-row items-center gap-1.5">
                <Sparkles size={14} color={COLORS.info} />
                <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Hiring Intelligence</Text>
              </View>
              <VacancyMatchStatusBadge
                status={recommendations.hiring_recommendation}
                score={recommendations.overall_match_confidence}
              />
            </View>

            {/* 2-Column Insight Grid inside Card */}
            <View className="flex-row flex-wrap gap-2">
              <View className="flex-1 min-w-[140px] bg-background p-2 rounded border border-border">
                <Text className="text-[11px] font-sans-bold text-text-muted uppercase mb-0.5">Experience & Seniority</Text>
                <Text className="text-xs leading-4 text-text-primary">{recommendations.experience_assessment || 'Not specified'}</Text>
              </View>
              <View className="flex-1 min-w-[140px] bg-background p-2 rounded border border-border">
                <Text className="text-[11px] font-sans-bold text-text-muted uppercase mb-0.5">Role & Dept Fit</Text>
                <Text className="text-xs leading-4 text-text-primary">{recommendations.role_department_fit || 'Not specified'}</Text>
              </View>
            </View>

            {recommendations.risk_flags && recommendations.risk_flags.length > 0 && (
              <View className="p-2 border rounded bg-danger/5 border-danger/20">
                <View className="flex-row items-center gap-1 mb-1">
                  <AlertTriangle size={12} color={COLORS.danger} />
                  <Text className="text-[11px] font-sans-bold text-danger uppercase">Risk Flags</Text>
                </View>
                {recommendations.risk_flags.map((flag, idx) => (
                  <Text key={idx} className="text-xs leading-4 text-danger">• {flag}</Text>
                ))}
              </View>
            )}

            {recommendations.strengths && recommendations.strengths.length > 0 && (
              <View>
                <Text className="text-[11px] font-sans-bold text-text-muted uppercase mb-1">Key Strengths</Text>
                {recommendations.strengths.map((str, idx) => (
                  <Text key={idx} className="text-xs text-text-primary leading-4 mb-0.5"><Text className="text-success">✓</Text> {str}</Text>
                ))}
              </View>
            )}

            {recommendations.interview_focus_areas && recommendations.interview_focus_areas.length > 0 && (
              <View className="pt-2 border-t border-border">
                <Text className="text-[11px] font-sans-bold text-text-muted uppercase mb-1">Interview Focus Areas</Text>
                {recommendations.interview_focus_areas.map((focus, idx) => (
                  <Text key={idx} className="text-xs text-text-primary leading-4 mb-0.5">• {focus}</Text>
                ))}
              </View>
            )}
          </Card>
        ) : null}

        {/* Experience Timeline & Gaps Section */}
        <ExperienceTimelineCard
          analysis={(data as any)?.experience_gap_analysis || (data as any)?.experience_summary?.gap_analysis || (analysis as any)?.experience_gap_analysis || (recommendations as any)?.experience_gap_analysis}
          experienceAssessment={(data as any)?.experience_summary?.experience_assessment || recommendations?.experience_assessment}
          candidateData={data}
        />

        {/* AI Career Summary & Domain Insights */}
        {(analysis?.ai_career_summary || analysis?.recommended_department || analysis?.professional_domain) && (
          <Card className="gap-3 p-3 shadow-none border-border">
            <View className="flex-row items-center gap-1.5 border-b border-border pb-2">
              <CpuIcon size={14} color={COLORS.textMuted} />
              <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-muted">AI Domain Analysis</Text>
            </View>

            {analysis?.ai_career_summary ? (
              <Text className="mb-2 font-sans text-xs leading-5 text-text-primary">{analysis.ai_career_summary}</Text>
            ) : null}

            <View className="flex-row items-center justify-between">
              <Text className="text-xs font-sans-medium text-text-muted">Recommended Dept:</Text>
              <Badge label={analysis?.recommended_department || analysis?.primary_department || 'General'} tone="info" />
            </View>
            <View className="flex-row items-center justify-between mt-1">
              <Text className="text-xs font-sans-medium text-text-muted">Professional Domain:</Text>
              <Text className="text-xs font-sans-bold text-text-primary">{analysis?.professional_domain || 'Not specified'}</Text>
            </View>
            {analysis?.suitable_job_roles && (
              <View className="pt-2 mt-2 border-t border-border">
                <Text className="mb-1 text-xs font-sans-medium text-text-muted">Suitable Job Roles:</Text>
                <View className="flex-row flex-wrap gap-1">
                  {analysis.suitable_job_roles.map((role: string, idx: number) => (
                    <Badge key={idx} label={role} tone="neutral" />
                  ))}
                </View>
              </View>
            )}
            {recommendations?.talent_pools && (
              <View className="pt-2 mt-2 border-t border-border">
                <Text className="mb-1 text-xs font-sans-medium text-text-muted">Assigned Talent Pools:</Text>
                <View className="flex-row flex-wrap gap-1">
                  {recommendations.talent_pools.map((pool: string, idx: number) => (
                    <Badge key={idx} label={pool} tone="success" />
                  ))}
                </View>
              </View>
            )}
            {recommendations?.related_skills && (
              <View className="pt-2 mt-2 border-t border-border">
                <Text className="text-[11px] font-sans-bold text-text-muted uppercase tracking-wider mb-1">Semantically Related Skills:</Text>
                <View className="flex-row flex-wrap gap-1">
                  {recommendations.related_skills.map((skill, idx) => (
                    <Badge key={idx} label={skill} tone="neutral" />
                  ))}
                </View>
              </View>
            )}
          </Card>
        )}

      </View>
    </View>
  );

  const renderProcessingTab = () => (
    <View className="gap-4">
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
        <ErrorBanner title="Reprocessing Error" message={reprocessError} />
      )}

      <Card className="p-3 shadow-none border-border">
        <Text className="mb-2 text-xs tracking-wider uppercase font-sans-bold text-text-muted">Processing Metadata</Text>
        <View className="gap-2">
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Filename:</Text>
            <Text className="font-mono text-xs text-text-primary">{data?.filename || data?.id}</Text>
          </View>
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Analyzed At:</Text>
            <Text className="font-mono text-xs text-text-primary">{formattedParsedAt}</Text>
          </View>
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Extraction Method:</Text>
            <Badge label={data?.ocr_applied ? 'RapidOCR' : 'Native PDF'} tone="info" />
          </View>
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Pages:</Text>
            <Text className="font-mono text-xs text-text-primary">{data?.page_count != null ? `${data.page_count} pg` : 'Unknown'}</Text>
          </View>
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Status:</Text>
            <Badge label={data?.status || 'UNKNOWN'} tone={getStatusTone(data?.status)} />
          </View>
        </View>
      </Card>
    </View>
  );

  // -------------------------------------------------------------
  // MAIN RENDER
  // -------------------------------------------------------------

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs
        items={[
          { label: 'Candidate Directory', href: getReturnHref() },
          { label: candName || id || 'Candidate Profile' },
        ]}
      />
      {/* 1. Header Area (Responsive & Tokenized) */}
      <View className="z-10 px-4 py-3 bg-surface border-b shadow-sm border-border">
        <View className="flex-col sm:flex-row items-start sm:items-center justify-between gap-3">

          {/* Left Side: Back Button & High-Level Identity */}
          <View className="flex-row flex-1 gap-2 items-center">
            <Pressable
              onPress={handleBack}
              accessibilityRole="button"
              accessibilityLabel="Back to Candidate Directory"
              className="min-h-[44px] min-w-[44px] items-center justify-center -ml-2"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <ArrowLeft size={18} color={COLORS.textPrimary} />
            </Pressable>
            <View className="flex-row items-center flex-1 gap-3 pr-2">
              <View className="items-center justify-center w-10 h-10 rounded-full bg-primary/10">
                <UserCheck size={18} color={COLORS.primary} />
              </View>
              <View className="flex-1">
                <Text numberOfLines={1} ellipsizeMode="tail" className="text-sm font-sans-bold text-text-primary">
                  {data?.full_name || data?.candidate_name || data?.resume_json?.contact_info?.name || 'Unknown Candidate'}
                </Text>
                <Text numberOfLines={1} ellipsizeMode="tail" className="text-[11px] font-sans-medium text-text-muted">
                  {data?.job_title || data?.resume_json?.contact_info?.job_title || data?.match_analysis?.best_match?.job_title || 'No Title'} • {data?.company_name || 'No Company'}
                </Text>
              </View>
            </View>
          </View>

          {/* Right Side: Primary Metric & Actions */}
          <View className="flex-row items-center gap-2 flex-wrap self-end sm:self-auto">
            {/* Hiring Recommendation Badge */}
            {recommendations && !recommendationsLoading && recommendations.hiring_recommendation ? (
              <View className="hidden md:flex">
                <VacancyMatchStatusBadge
                  status={recommendations.hiring_recommendation}
                  score={recommendations.overall_match_confidence}
                />
              </View>
            ) : null}
            {data?.experience_years != null ? (
              <View className="items-center px-2.5 py-1 border rounded bg-background border-border">
                <Text className="text-[11px] text-text-muted uppercase font-sans-bold">Experience</Text>
                <Text className="text-xs font-sans-bold text-text-primary">{data.experience_years} Yrs • {data.seniority || 'Assessed'}</Text>
              </View>
            ) : null}
            {bestMatch?.overall_score != null ? (
              <View className="items-center px-2.5 py-1 border rounded bg-background border-border">
                <Text className="text-[11px] text-text-muted uppercase font-sans-bold">AI Match</Text>
                <Text className="text-xs font-sans-bold text-primary">{Math.round(bestMatch.overall_score)}%</Text>
              </View>
            ) : null}
            <View className="flex-row gap-2 items-center">
              <Button
                variant="secondary"
                size="sm"
                label={isReanalyzing ? 'Matching...' : 'Re-run Matching'}
                icon={!isReanalyzing ? <Sparkles size={14} color={COLORS.primary} /> : undefined}
                onPress={handleReanalyze}
                disabled={isReanalyzing || isReprocessing}
              />
              <Button
                variant="ghost"
                size="sm"
                label="Reprocess"
                icon={<RefreshCw size={14} color={COLORS.textMuted} />}
                onPress={() => setReprocessModalVisible(true)}
                disabled={isReprocessing}
              />
            </View>
          </View>

        </View>
      </View>

      {/* 2. Tab Navigation */}
      <View className="flex-row gap-4 px-4 overflow-x-auto bg-surface border-b border-border">
        {[
          { id: 'overview', label: 'Overview', icon: <Activity size={14} color={activeTab === 'overview' ? COLORS.primary : COLORS.textMuted} /> },
          { id: 'processing', label: 'Processing Pipeline', icon: <Layers size={14} color={activeTab === 'processing' ? COLORS.primary : COLORS.textMuted} /> },
        ].map(tab => (
          <Pressable
            key={tab.id}
            className={`py-3 border-b-2 flex-row items-center gap-1.5 ${activeTab === tab.id ? 'border-primary' : 'border-transparent'}`}
            onPress={() => setActiveTab(tab.id as TabType)}
          >
            {tab.icon}
            <Text className={`text-xs font-sans-bold ${activeTab === tab.id ? 'text-primary' : 'text-text-muted'}`}>
              {tab.label}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* 3. Main Content Area */}
      <ScrollView className="flex-1 px-4 py-4">
        {loading && !isReprocessing ? (
          <View className="items-center justify-center flex-1 py-16">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="mt-2 font-sans text-xs text-text-muted">Loading profile dashboard...</Text>
          </View>
        ) : error || !data ? (
          <View className="gap-2">
            <ErrorBanner title="Profile Load Error" message={error || 'Candidate record not found.'} />
            <View className="self-start">
              <Button label="Retry Loading" variant="ghost" size="sm" onPress={fetchDetail} />
            </View>
          </View>
        ) : (
          <View className="pb-8">
            {activeTab === 'overview' && renderOverviewTab()}
            {activeTab === 'processing' && renderProcessingTab()}
          </View>
        )}
      </ScrollView>

      {/* Modals */}
      {selectedJobForReview && (
        <HrReviewModal
          visible={reviewModalVisible}
          scanId={scanId}
          job={selectedJobForReview}
          onClose={() => {
            setReviewModalVisible(false);
            setSelectedJobForReview(null);
          }}
          onSubmitted={fetchDetail}
        />
      )}

      {/* Destructive Cache-Purge Confirmation Modal */}
      <Modal animationType="fade" transparent={true} visible={reprocessModalVisible} onRequestClose={() => setReprocessModalVisible(false)}>
        <View className="items-center justify-center flex-1 px-4 bg-black/60">
          <Card className="w-full max-w-md gap-3 p-4 bg-surface border-border">
            <View className="flex-row items-center justify-between pb-2 border-b border-border">
              <View className="flex-row items-center gap-2">
                <AlertTriangle size={16} color={COLORS.danger} />
                <Text className="text-sm font-sans-bold text-text-primary">Reprocess Source CV & Purge Cache</Text>
              </View>
              <Pressable
                onPress={() => setReprocessModalVisible(false)}
                className="min-h-[36px] min-w-[36px] items-center justify-center"
                hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
              >
                <X size={16} color={COLORS.textMuted} />
              </Pressable>
            </View>
            <Text className="font-sans text-xs leading-5 text-text-primary">
              Are you sure you want to completely reprocess <Text className="font-sans-bold">{data?.filename || scanId}</Text>?
            </Text>
            <View className="bg-danger/10 p-2.5 rounded-md border border-danger/30">
              <Text className="text-[11px] font-sans text-danger leading-4">
                ⚠️ This permanently purges cached extraction JSON, LLM reasoning, embeddings, and match score breakdowns, and restarts the complete multi-stage pipeline.
              </Text>
            </View>
            <View className="flex-row justify-end gap-2 mt-2">
              <Button label="Cancel" variant="ghost" size="sm" onPress={() => setReprocessModalVisible(false)} />
              <Button label="Purge Cache & Reprocess" variant="destructive" size="sm" onPress={handleConfirmReprocess} />
            </View>
          </Card>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
