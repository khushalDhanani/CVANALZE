import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft, CheckCircle, Edit3,
  RefreshCw, X, Mail, Phone, UserCheck, Target, Sparkles,
  AlertTriangle, MapPin, Activity, Layers, Link, Code2
} from 'lucide-react-native';
import { candidateService } from '@/services/candidateService';
import { cvService } from '@/services/cvService';
import { matchService } from '@/services/matchService';
import { CandidateRecommendationsResponse, CVUploadResponse } from '@/types/api';
import {
  Card,
  Button,
  Badge,
  FieldConfidenceView,
  Breadcrumbs,
  ExperienceTimelineCard,
  ErrorBanner,
  VacancyEnrichmentPanel,
} from '@/components/ui';
import { VacancyMatchStatusBadge } from '@/components/ui/VacancyMatchStatusBadge';
import { HrReviewModal } from '@/components/ui/HrReviewModal';
import { StepProgressCard, StepState } from '@/components/ui/StepProgressCard';
import { usePageTitle } from '@/hooks/usePageTitle';
import { COLORS } from '@/constants/colors';
import { formatDateTime } from '@/utils/date';
import { getCvQueueStateMeta, resolveCvQueueUiState } from '@/utils/cvQueueState';
import {
  buildCandidateFiveSecondSummary,
  buildCandidateDetailViewModel,
  cleanCandidateText,
  cleanRecommendationText,
  humanizeRecruiterText,
  normalizeCandidateMatchAnalysis,
  normalizeCandidateRouteId,
  responseMatchesCandidateId,
} from '@/utils/candidateDetail';
import { getProcessingProvenanceRows } from '@/utils/processingProvenance';
import { getReanalysisErrorPresentation, type ReanalysisErrorPresentation } from '@/utils/reanalysisError';
import { reanalyzeCandidateAndCommit } from '@/utils/candidateReanalysis';
import { buildCandidateDecisionEvidence, buildCandidateSkillsSummaryPresentation, buildVacancyDecisionEvidence } from '@/utils/candidateDecisionEvidence';

type TabType = 'overview' | 'processing';

const normalizeRecruiterLabels = (value: unknown, objectKeys: string[] = []): string[] => {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value.reduce<string[]>((labels, item) => {
    const record = item && typeof item === 'object' && !Array.isArray(item) ? item as Record<string, unknown> : undefined;
    const label = cleanCandidateText(item) || objectKeys.map((key) => cleanCandidateText(record?.[key])).find(Boolean);
    if (!label) return labels;
    const normalizedLabel = label.toLocaleLowerCase();
    if (seen.has(normalizedLabel)) return labels;
    seen.add(normalizedLabel);
    labels.push(label);
    return labels;
  }, []);
};

export default function CandidateDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id: string | string[]; query?: string; classification?: string; department?: string }>();
  const { id, query, classification, department } = params;
  const candidateCvId = normalizeCandidateRouteId(id);

  const [activeTab, setActiveTab] = useState<TabType>('overview');

  const [data, setData] = useState<CVUploadResponse | null>(null);
  const candidateView = useMemo(() => data ? buildCandidateDetailViewModel(data) : null, [data]);
  const candName = candidateView?.name;
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
  const [reanalyzeError, setReanalyzeError] = useState<ReanalysisErrorPresentation | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const detailRequestRef = useRef<number>(0);
  const activeCandidateIdRef = useRef<string | undefined>(candidateCvId);
  activeCandidateIdRef.current = candidateCvId;

  const stopTimers = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    timerRef.current = null;
    pollTimerRef.current = null;
  }, []);

  const fetchDetail = useCallback(() => {
    const requestId = ++detailRequestRef.current;
    stopTimers();
    setData(null);
    setRecommendations(null);
    setShowFullText(false);
    setReviewModalVisible(false);
    setSelectedJobForReview(null);
    setIsReanalyzing(false);
    setReanalyzeError(null);
    setIsReprocessing(false);
    setReprocessError(null);
    setRecommendationsError(null);

    if (!candidateCvId) {
      setLoading(false);
      setRecommendationsLoading(false);
      setError('The candidate CV ID is missing or invalid.');
      return;
    }

    setLoading(true);
    setError(null);
    candidateService
      .getCandidateById(candidateCvId)
      .then((res) => {
        if (requestId !== detailRequestRef.current) return;
        if (!res || typeof res !== 'object' || !responseMatchesCandidateId(res, candidateCvId)) {
          throw new Error('The API returned an empty or mismatched candidate record.');
        }
        setData(res);
        if (res.status === 'COMPLETED' || res.is_complete || res.progress === 100 || res.match_analysis) {
          setIsReprocessing(false);
          stopTimers();
        }
      })
      .catch((err) => {
        if (requestId === detailRequestRef.current) setError(err.message || 'Failed to load candidate details.');
      })
      .finally(() => {
        if (requestId === detailRequestRef.current) setLoading(false);
      });

    setRecommendationsLoading(true);
    candidateService
      .getCandidateRecommendations(candidateCvId)
      .then((rec) => {
        if (requestId !== detailRequestRef.current) return;
        setRecommendations(rec);
        setRecommendationsError(null);
      })
      .catch((err) => {
        if (requestId !== detailRequestRef.current) return;
        setRecommendationsError(err.message || 'Failed to load candidate recommendations.');
        setRecommendations(null);
      })
      .finally(() => {
        if (requestId === detailRequestRef.current) setRecommendationsLoading(false);
      });
  }, [candidateCvId, stopTimers]);

  useEffect(() => {
    fetchDetail();
    return () => {
      detailRequestRef.current += 1;
      stopTimers();
    };
  }, [fetchDetail, stopTimers]);

  const handleConfirmReprocess = async () => {
    if (!candidateCvId) return;
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
      await candidateService.reprocessCandidate(candidateCvId);

      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      let errorCount = 0;
      pollTimerRef.current = setInterval(async () => {
        try {
          const statusRes: any = await cvService.getCvStatus(candidateCvId);
          const queueState = resolveCvQueueUiState(statusRes);
          const queueStateMeta = getCvQueueStateMeta(queueState);
          const msg = statusRes.error_message || statusRes.message || statusRes.error || '';
          const pct = statusRes.progress || 0;

          setReprocessStatusMsg(msg || queueStateMeta.label);

          if (queueState === 'FAILED') {
            stopTimers();
            setIsReprocessing(false);
            setReprocessError(
              statusRes.error_code ? `${statusRes.error_code}: ${msg || 'Reprocessing failed.'}` : msg || 'Reprocessing failed.'
            );
            return;
          }

          if (queueState === 'COMPLETED') {
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
    const requestedCandidateId = candidateCvId;
    setIsReanalyzing(true);
    setReanalyzeError(null);
    try {
      await reanalyzeCandidateAndCommit({
        scanId,
        reanalyze: matchService.reanalyzeScan,
        commit: setData,
        isCurrent: () => activeCandidateIdRef.current === requestedCandidateId,
      });
      if (activeCandidateIdRef.current !== requestedCandidateId) return;
      setError(null);
    } catch (requestError: unknown) {
      if (activeCandidateIdRef.current === requestedCandidateId) {
        setReanalyzeError(getReanalysisErrorPresentation(requestError));
      }
    } finally {
      if (activeCandidateIdRef.current === requestedCandidateId) setIsReanalyzing(false);
    }
  };

  const rawAnalysis = data?.enriched_match_analysis || data?.match_analysis;
  const analysis: any = useMemo(() => normalizeCandidateMatchAnalysis(rawAnalysis), [rawAnalysis]);
  const bestMatch = analysis?.best_match;
  const suggestedRoles = useMemo(
    () => normalizeRecruiterLabels(analysis?.suitable_job_roles, ['suggested_role', 'role', 'job_title', 'title', 'name']),
    [analysis],
  );
  const interviewFocusAreas = useMemo(
    () => normalizeRecruiterLabels(recommendations?.interview_focus_areas, ['focus', 'focus_area', 'area', 'title', 'name']),
    [recommendations],
  );
  const talentPools = useMemo(
    () => normalizeRecruiterLabels(recommendations?.talent_pools, ['talent_pool', 'pool', 'title', 'name']),
    [recommendations],
  );
  const candidateSummary = useMemo(
    () => data && candidateView ? buildCandidateFiveSecondSummary(data, candidateView, analysis, recommendations) : null,
    [analysis, candidateView, data, recommendations],
  );
  const decisionEvidence = useMemo(
    () => data && candidateView ? buildCandidateDecisionEvidence(data, candidateView, analysis, recommendations) : null,
    [analysis, candidateView, data, recommendations],
  );
  const skillsSummary = useMemo(
    () => decisionEvidence ? buildCandidateSkillsSummaryPresentation(decisionEvidence.skills) : null,
    [decisionEvidence],
  );
  const additionalConcerns = useMemo(() => {
    const primaryConcern = candidateSummary?.mainConcern.toLocaleLowerCase();
    return decisionEvidence?.concerns.filter((concern) => concern.toLocaleLowerCase() !== primaryConcern) || [];
  }, [candidateSummary, decisionEvidence]);
  const vacancyMatches = useMemo(() => {
    const matches = [bestMatch, ...(analysis?.suitable_openings || []), ...(analysis?.unsuitable_openings || [])].filter(Boolean);
    const seen = new Set<string>();
    return matches.filter((match: any) => {
      const key = String(match.vacancy_id || match.job_id || `${match.job_title}:${match.department_name || match.department}`);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [analysis, bestMatch]);
  const experienceAnalysis = (data as any)?.experience_gap_analysis
    || (data as any)?.experience_summary?.gap_analysis
    || (analysis as any)?.experience_gap_analysis
    || (recommendations as any)?.experience_gap_analysis;
  const scanId = data?.scan_id || data?.id || candidateCvId || '';

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

  const recommendationTone = candidateSummary?.recommendation === 'STRONG MATCH'
    ? 'success'
    : candidateSummary?.recommendation === 'POTENTIAL MATCH'
      ? 'warning'
      : candidateSummary?.recommendation === 'MANUAL REVIEW'
        ? 'info'
        : 'neutral';
  const recommendationAction = candidateSummary?.recommendation === 'STRONG MATCH'
    ? 'Continue to the next screening step.'
    : candidateSummary?.recommendation === 'POTENTIAL MATCH'
      ? 'Continue with a focused review.'
      : candidateSummary?.recommendation === 'MANUAL REVIEW'
        ? 'Continue after completing the highlighted checks.'
        : 'Review only if broader role alignment is relevant.';

  // -------------------------------------------------------------
  // TAB RENDERERS
  // -------------------------------------------------------------

  const renderProcessingProvenance = () => {
    if (!data) return null;
    const provenanceRows = getProcessingProvenanceRows(data);
    const hasRecordedVersion = provenanceRows.some(({ recorded }) => recorded);
    return (
      <Card className="p-3 shadow-none border-border">
        <Text className="mb-1 text-xs tracking-wider uppercase font-sans-bold text-text-muted">Debug Information</Text>
        <Text className="mb-3 text-[11px] font-sans text-text-muted">
          {hasRecordedVersion
            ? 'Versions used to produce this stored result. These identifiers help administrators verify cache freshness and reproduce decisions.'
            : 'This legacy result does not contain version provenance. Reprocess the candidate to record the current rule, prompt, and model versions.'}
        </Text>
        <View className="gap-2">
          {provenanceRows.map(({ key, label, value }) => {
            return (
              <View key={key} className="flex-row items-start justify-between gap-3">
                <Text className="text-xs text-text-muted">{label}:</Text>
                <Text selectable={Boolean(value)} className={`max-w-[65%] font-mono text-xs text-right ${value ? 'text-text-primary' : 'text-text-faint'}`}>
                  {value || 'Not recorded'}
                </Text>
              </View>
            );
          })}
        </View>
      </Card>
    );
  };

  const renderOverviewTab = () => (
    <View className="w-full gap-4">
      {/* 2. Skills Match */}
      {decisionEvidence ? (
        <Card className="gap-3 p-3 shadow-none border-border">
          <View className="flex-row items-center justify-between pb-2 border-b border-border">
            <View className="flex-row items-center gap-1.5">
              <CheckCircle size={14} color={COLORS.primary} />
              <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Skills Match</Text>
            </View>
            {skillsSummary?.matchedLabel || skillsSummary?.missingLabel ? (
              <View className="flex-row flex-wrap gap-1">
                {skillsSummary.matchedLabel ? <Badge label={skillsSummary.matchedLabel} tone="success" /> : null}
                {skillsSummary.missingLabel ? <Badge label={skillsSummary.missingLabel} tone={decisionEvidence.skills.missingRequired.length ? 'warning' : 'neutral'} /> : null}
              </View>
            ) : null}
          </View>
          <View className="flex-row flex-wrap gap-3">
            <View className="flex-1 min-w-[200px] gap-1.5">
              <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-success">Matched Skills</Text>
              {decisionEvidence.skills.matched.length > 0
                ? decisionEvidence.skills.matched.map((skill) => <Text key={skill} className="text-xs text-text-primary">✓ {skill}</Text>)
                : skillsSummary?.missingLabel
                  ? <Text className="text-xs text-text-muted">No required skill matches were found in the CV.</Text>
                  : <Text className="text-xs text-text-muted">Required skills were not identified for this vacancy.</Text>}
            </View>
            <View className="flex-1 min-w-[200px] gap-1.5">
              <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-danger">Missing Required Skills</Text>
              {decisionEvidence.skills.missingRequired.length > 0
                ? decisionEvidence.skills.missingRequired.map((skill) => <Text key={skill} className="text-xs text-text-primary">• {skill}</Text>)
                : skillsSummary?.matchedLabel
                  ? <Text className="text-xs text-success">All identified required skills are matched.</Text>
                  : <Text className="text-xs text-text-muted">Missing-skill evidence is not available.</Text>}
            </View>
            <View className="flex-1 min-w-[200px] gap-1.5">
              <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Additional Candidate Skills</Text>
              {decisionEvidence.skills.additional.length > 0
                ? <View className="flex-row flex-wrap gap-1">{decisionEvidence.skills.additional.map((skill) => <Badge key={skill} label={skill} tone="neutral" />)}</View>
                : <Text className="text-xs text-text-muted">Additional skills were not identified from the CV.</Text>}
            </View>
          </View>
        </Card>
      ) : null}

      {/* 3. Experience */}
      {data && experienceAnalysis ? (
        <ExperienceTimelineCard
          analysis={experienceAnalysis}
          candidateData={data}
        />
      ) : candidateView && candidateView.experience.length > 0 ? (
        <Card className="gap-3 p-3 shadow-none border-border">
          <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Experience</Text>
          {candidateView.experience.map((experience, index) => (
            <View key={`${experience.title || 'role'}-${index}`} className="gap-1 pb-3 pl-3 border-l-2 border-border">
              {experience.title ? <Text className="text-sm font-sans-bold text-text-primary">{experience.title}</Text> : null}
              {experience.company ? <Text className="text-xs font-sans-bold text-text-muted">{experience.company}</Text> : null}
              {experience.dates ? <Text className="text-xs text-text-muted">{experience.dates}</Text> : null}
              {experience.responsibilities.map((responsibility) => <Text key={responsibility} className="text-[11px] leading-4 text-text-primary">• {responsibility}</Text>)}
            </View>
          ))}
        </Card>
      ) : (
        <Card className="gap-2 p-3 shadow-none border-border">
          <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Experience</Text>
          <Text className="text-xs text-text-muted">Employment history was not identified from the CV.</Text>
        </Card>
      )}

      {/* 4. Education */}
      {candidateView && decisionEvidence ? (
        <Card className="gap-3 p-3 shadow-none border-border">
          <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Education</Text>
          {candidateView.education.length > 0 ? candidateView.education.map((education, index) => (
            <View key={`${education.degree || 'education'}-${index}`} className="gap-0.5 pb-2 border-b border-border last:border-b-0">
              {education.degree ? <Text className="text-sm font-sans-bold text-text-primary">{education.degree}</Text> : null}
              {education.institution ? <Text className="text-xs font-sans-medium text-text-muted">{education.institution}</Text> : null}
              {education.dates ? <Text className="text-xs text-text-muted">{education.dates}</Text> : null}
              {education.grade ? <Text className="text-[11px] text-text-primary">{education.grade}</Text> : null}
              {education.details ? <Text className="text-[11px] text-text-primary">{education.details}</Text> : null}
            </View>
          )) : <Text className="text-xs text-text-muted">Education was not identified from the CV.</Text>}
          {decisionEvidence?.education ? (
            <View className={`gap-1 p-2 border rounded ${decisionEvidence.education.status === 'MATCHED' ? 'bg-success/5 border-success/20' : 'bg-warning/10 border-warning/30'}`}>
              <Text className={`text-xs font-sans-bold ${decisionEvidence.education.status === 'MATCHED' ? 'text-success' : 'text-warning'}`}>
                {decisionEvidence.education.status === 'MATCHED' ? '✓ Education Match' : decisionEvidence.education.status === 'CONFLICT' ? '⚠ Education Concern' : 'Education Review'}
              </Text>
              {decisionEvidence.education.requirement ? <Text className="text-xs text-text-primary">Vacancy requirement: {decisionEvidence.education.requirement}</Text> : null}
              {decisionEvidence.education.candidateEvidence ? <Text className="text-xs text-text-primary">CV evidence: {decisionEvidence.education.candidateEvidence}</Text> : null}
              {decisionEvidence.education.explanation ? <Text className="text-[11px] text-text-muted">{decisionEvidence.education.explanation}</Text> : null}
            </View>
          ) : null}
          {candidateView.certifications.length > 0 ? (
            <View className="gap-1.5 pt-2 border-t border-border">
              <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Certifications</Text>
              <View className="flex-row flex-wrap gap-1">{candidateView.certifications.map((certification) => <Badge key={certification} label={certification} tone="neutral" />)}</View>
            </View>
          ) : null}
        </Card>
      ) : null}

      {/* 5. Strengths & Risks */}
      {decisionEvidence ? (
        <Card className="gap-3 p-3 shadow-none border-border">
          <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Strengths & Risks</Text>
          {recommendationsLoading ? <Text className="text-xs text-text-muted">Loading supporting hiring insights…</Text> : null}
          {recommendationsError ? <Text className="text-xs text-danger">Additional hiring insights are unavailable: {recommendationsError}</Text> : null}
          <View className="flex-row flex-wrap gap-3">
            <View className="flex-1 min-w-[240px] gap-1.5">
              <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-success">Key Strengths</Text>
              {decisionEvidence.strengths.length > 0
                ? decisionEvidence.strengths.map((strength) => <Text key={strength} className="text-xs leading-4 text-text-primary">✓ {strength}</Text>)
                : <Text className="text-xs text-text-muted">Not enough evidence was available to identify key strengths.</Text>}
            </View>
            <View className="flex-1 min-w-[240px] gap-1.5">
              <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-danger">Key Concerns</Text>
              {additionalConcerns.length > 0
                ? additionalConcerns.map((concern) => <Text key={concern} className="text-xs leading-4 text-text-primary">⚠ {concern}</Text>)
                : decisionEvidence.concerns.length > 0
                  ? <Text className="text-xs text-text-muted">The primary concern is summarized above; no additional concern was identified.</Text>
                  : vacancyMatches.length > 0
                    ? <Text className="text-xs text-success">No major concern was identified in the current evidence.</Text>
                    : <Text className="text-xs text-text-muted">Not enough vacancy evidence is available to assess candidate concerns.</Text>}
            </View>
          </View>
        </Card>
      ) : null}

      {/* 6. Vacancy Analysis */}
      <Card className="gap-3 p-3 shadow-none border-border">
        <View className="flex-row items-center justify-between pb-2 border-b border-border">
          <View className="flex-row items-center gap-1.5">
            <Target size={14} color={COLORS.primary} />
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Vacancy Analysis</Text>
          </View>
          <Badge label={`${vacancyMatches.length} Evaluated`} tone="neutral" />
        </View>
        {vacancyMatches.length > 0 ? vacancyMatches.map((match: any, index: number) => {
          const evidence = buildVacancyDecisionEvidence(match);
          const rawStatus = match.vacancy_match_status || match.match_status || match.classification;
          const vacancyDepartment = cleanCandidateText(match.department_name || match.department);
          return (
            <View key={String(match.vacancy_id || match.job_id || index)} className="gap-2 p-3 border rounded bg-background border-border">
              <View className="flex-row flex-wrap items-start justify-between gap-2">
                <View className="flex-1 min-w-[200px]">
                  <Text className="text-sm font-sans-bold text-text-primary">{cleanCandidateText(match.job_title) || 'Vacancy title not available'}</Text>
                  {vacancyDepartment ? <Text className="text-xs text-text-muted">{vacancyDepartment}</Text> : null}
                </View>
                <VacancyMatchStatusBadge status={rawStatus} score={evidence.overallFit} />
              </View>
              <View className="flex-row flex-wrap gap-2">
                {[['Skills', evidence.skillsFit], ['Experience', evidence.experienceFit], ['Education', evidence.educationFit]].map(([label, value]) => value != null ? (
                  <View key={String(label)} className="flex-1 min-w-[110px] p-2 border rounded bg-surface border-border">
                    <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-text-muted">{label}</Text>
                    <Text className="text-sm font-sans-bold text-text-primary">{Math.round(Number(value))}%</Text>
                  </View>
                ) : null)}
              </View>
              {evidence.whyItFits ? (
                <View>
                  <Text className="text-[11px] font-sans-bold text-success">Why it fits</Text>
                  <Text className="text-xs leading-4 text-text-primary">{evidence.whyItFits}</Text>
                </View>
              ) : null}
              {evidence.mainGap ? (
                <View>
                  <Text className="text-[11px] font-sans-bold text-danger">Main gap</Text>
                  <Text className="text-xs leading-4 text-text-primary">{evidence.mainGap}</Text>
                </View>
              ) : null}
              <View className="flex-row justify-end">
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
            </View>
          );
        }) : <Text className="text-xs text-text-muted">No active vacancy evaluation is available for this candidate.</Text>}
      </Card>

      {/* 7. AI Reasoning */}
      <Card className="gap-3 p-3 shadow-none border-info/30 bg-info/5">
        <View className="flex-row items-center gap-1.5 pb-2 border-b border-info/20">
          <Sparkles size={14} color={COLORS.info} />
          <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">AI Match Explanation</Text>
        </View>
        <Text className="text-[11px] leading-4 text-text-muted">AI-generated interpretation is not confirmed CV evidence. Verify it against the factual skills, experience, and education above.</Text>
        {analysis?.ai_career_summary ? <Text className="text-xs leading-5 text-text-primary">{humanizeRecruiterText(analysis.ai_career_summary)}</Text> : null}
        {recommendations?.experience_assessment ? (
          <View className="gap-1">
            <Text className="text-[11px] font-sans-bold text-text-primary">Experience interpretation</Text>
            <Text className="text-xs leading-4 text-text-primary">{humanizeRecruiterText(recommendations.experience_assessment)}</Text>
          </View>
        ) : null}
        {vacancyMatches.some((match: any) => cleanCandidateText(match.llm_reason || match.semantic_reason))
          ? vacancyMatches.map((match: any, index: number) => cleanCandidateText(match.llm_reason || match.semantic_reason) ? (
              <View key={String(match.vacancy_id || match.job_id || index)} className="gap-1">
                <Text className="text-xs font-sans-bold text-text-primary">{cleanCandidateText(match.job_title) || `Vacancy ${index + 1}`}</Text>
                <VacancyEnrichmentPanel match={match} showDecisionMetadata={false} />
              </View>
            ) : null)
          : !analysis?.ai_career_summary ? <Text className="text-xs text-text-muted">An AI match explanation is not available for this analysis.</Text> : null}
      </Card>

      {/* 8. Secondary Information */}
      <Card className="gap-3 p-3 shadow-none border-border">
        <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-muted">Secondary Information</Text>
        {candidateView && (candidateView.email || candidateView.phone || candidateView.location || candidateView.linkedin || candidateView.github) ? (
          <View className="gap-2">
            <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Contact</Text>
            {candidateView.email ? <FieldConfidenceView fieldName="email" value={candidateView.email} icon={<Mail size={14} color={COLORS.textFaint} />} /> : null}
            {candidateView.phone ? <FieldConfidenceView fieldName="phone" value={candidateView.phone} icon={<Phone size={14} color={COLORS.textFaint} />} /> : null}
            {candidateView.location ? (
              <FieldConfidenceView
                fieldName="location"
                value={candidateView.location}
                tier={data?.location_confidence_tier || data?.field_confidence_tiers?.location}
                icon={<MapPin size={14} color={COLORS.textFaint} />}
              />
            ) : null}
            {candidateView.linkedin ? <FieldConfidenceView fieldName="linkedin" value={candidateView.linkedin} icon={<Link size={14} color={COLORS.textFaint} />} /> : null}
            {candidateView.github ? <FieldConfidenceView fieldName="github" value={candidateView.github} icon={<Code2 size={14} color={COLORS.textFaint} />} /> : null}
          </View>
        ) : null}
        {candidateView?.projects.length ? (
          <View className="gap-2 pt-2 border-t border-border">
            <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Projects</Text>
            {candidateView.projects.slice(0, 4).map((project, index) => (
              <View key={`${project.name || 'project'}-${index}`} className="gap-1">
                {project.name ? <Text className="text-xs font-sans-bold text-text-primary">{project.name}</Text> : null}
                {project.description ? <Text className="text-[11px] leading-4 text-text-primary">{project.description}</Text> : null}
              </View>
            ))}
          </View>
        ) : null}
        {interviewFocusAreas.length ? (
          <View className="gap-1.5 pt-2 border-t border-border">
            <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Interview Focus Areas</Text>
            {interviewFocusAreas.slice(0, 4).map((focus) => <Text key={focus} className="text-xs leading-4 text-text-primary">• {cleanRecommendationText(focus)}</Text>)}
          </View>
        ) : null}
        {suggestedRoles.length || talentPools.length ? (
          <View className="gap-1.5 pt-2 border-t border-border">
            {suggestedRoles.length ? (
              <View className="gap-1">
                <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Suggested Roles</Text>
                <View className="flex-row flex-wrap gap-1">{suggestedRoles.map((role) => <Badge key={role} label={role} tone="neutral" />)}</View>
              </View>
            ) : null}
            {talentPools.length ? (
              <View className="gap-1">
                <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Talent Pools</Text>
                <View className="flex-row flex-wrap gap-1">{talentPools.map((pool) => <Badge key={pool} label={pool} tone="info" />)}</View>
              </View>
            ) : null}
          </View>
        ) : null}
        {data?.similar_candidates?.length ? (
          <View className="gap-2 pt-2 border-t border-border">
            <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Similar Candidates</Text>
            {data.similar_candidates.slice(0, 5).map((similar: any, index: number) => {
              const similarCandidateId = cleanCandidateText(similar.candidate_id || similar.id);
              const similarCandidateName = cleanCandidateText(similar.full_name || similar.filename || similarCandidateId);
              const rawSimilarity = Number(similar.similarity_score ?? similar.score);
              const similarity = Number.isFinite(rawSimilarity) ? Math.round((rawSimilarity <= 1 ? rawSimilarity * 100 : rawSimilarity)) : undefined;
              if (!similarCandidateId || !similarCandidateName) return null;
              return (
                <View key={`${similarCandidateId}-${index}`} className="flex-row items-center justify-between gap-2 p-2 border rounded bg-background border-border">
                  <Text className="text-xs cursor-pointer font-sans-bold text-text-primary" onPress={() => router.push(`/candidates/${encodeURIComponent(similarCandidateId)}` as any)}>{similarCandidateName}</Text>
                  {similarity != null ? <Badge label={`${similarity}%`} tone="neutral" /> : null}
                </View>
              );
            })}
          </View>
        ) : null}
        {candidateView?.extractedText ? (
          <View className="gap-2 pt-2 border-t border-border">
            <View className="flex-row items-center justify-between">
              <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Extracted CV Text</Text>
              <Button label={showFullText ? 'Collapse' : 'Expand Full'} variant="ghost" size="sm" onPress={() => setShowFullText(!showFullText)} />
            </View>
            <Text numberOfLines={showFullText ? undefined : 8} className="text-[11px] font-mono text-text-primary leading-5">{candidateView.extractedText}</Text>
          </View>
        ) : null}
        <Text className="text-[11px] text-text-muted">Administrative processing details are available in the Processing Details tab.</Text>
      </Card>
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

      {data && (cleanCandidateText(data.filename || data.id) || rawTimestamp || typeof data.ocr_applied === 'boolean' || data.page_count != null || cleanCandidateText(data.status)) ? <Card className="p-3 shadow-none border-border">
        <Text className="mb-2 text-xs tracking-wider uppercase font-sans-bold text-text-muted">Technical Details</Text>
        <View className="gap-2">
          {cleanCandidateText(data.filename || data.id) ? (
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Filename:</Text>
            <Text className="font-mono text-xs text-text-primary">{data?.filename || data?.id}</Text>
          </View>
          ) : null}
          {rawTimestamp ? (
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Analyzed At:</Text>
            <Text className="font-mono text-xs text-text-primary">{formattedParsedAt}</Text>
          </View>
          ) : null}
          {typeof data.ocr_applied === 'boolean' ? (
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Extraction Method:</Text>
            <Badge label={data?.ocr_applied ? 'RapidOCR' : 'Native PDF'} tone="info" />
          </View>
          ) : null}
          {data.page_count != null ? (
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Pages:</Text>
            <Text className="font-mono text-xs text-text-primary">{data.page_count} pg</Text>
          </View>
          ) : null}
          {cleanCandidateText(data.status) ? (
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Status:</Text>
            <Badge label={data.status!} tone={getStatusTone(data.status || undefined)} />
          </View>
          ) : null}
        </View>
      </Card> : null}

      {renderProcessingProvenance()}
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
          { label: candName || candidateCvId || 'Candidate Profile' },
        ]}
      />
      {/* 1. Recruiter 5-second summary */}
      <View className="z-10 px-4 py-3 border-b shadow-sm bg-surface border-border">
        <View className="flex-row flex-wrap items-center justify-between gap-2">
          <View className="flex-row items-center gap-2">
            <Pressable
              onPress={handleBack}
              accessibilityRole="button"
              accessibilityLabel="Back to Candidate Directory"
              className="min-h-[44px] min-w-[44px] items-center justify-center -ml-2"
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <ArrowLeft size={18} color={COLORS.textPrimary} />
            </Pressable>
            <Text className="text-xs font-sans-bold text-text-muted">Candidate Summary</Text>
          </View>
          <View className="flex-row items-center gap-2">
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

        {candidateSummary ? (
          <View className="gap-3 pt-3 mt-3 border-t border-border">
            <View className="flex-col justify-between gap-3 md:flex-row md:items-start">
              <View className="flex-row items-center flex-1 min-w-0 gap-3">
                <View className="items-center justify-center w-11 h-11 rounded-full bg-primary/10">
                  <UserCheck size={20} color={COLORS.primary} />
                </View>
                <View className="flex-1 min-w-0">
                  <Text numberOfLines={1} ellipsizeMode="tail" className="text-xl font-sans-bold text-text-primary">{candidateSummary.name}</Text>
                  <Text numberOfLines={1} ellipsizeMode="tail" className="text-sm font-sans-bold text-text-primary">
                    {candidateSummary.role || 'Latest role not identified from CV'}
                  </Text>
                  {candidateSummary.company ? <Text numberOfLines={1} ellipsizeMode="tail" className="text-xs text-text-muted">{candidateSummary.company}</Text> : null}
                </View>
              </View>
              <View className="items-start gap-1 md:items-end">
                <Badge label={candidateSummary.recommendation} tone={recommendationTone} />
                <Text className="text-[11px] font-sans-medium text-text-muted">{recommendationAction}</Text>
              </View>
            </View>

            <View className="flex-row flex-wrap gap-2">
              <View className="min-w-[138px] flex-1 p-2 border rounded bg-background border-border">
                <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-text-muted">Overall Match</Text>
                <Text className="text-base font-sans-bold text-primary">{candidateSummary.overallFit != null ? `${Math.round(candidateSummary.overallFit)}%` : 'Not enough evidence'}</Text>
                {candidateSummary.matchConfidence != null ? <Text className="text-[10px] text-text-muted">Match Confidence {Math.round(candidateSummary.matchConfidence)}%</Text> : null}
              </View>
              <View className="min-w-[138px] flex-1 p-2 border rounded bg-background border-border">
                <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-text-muted">Experience</Text>
                <Text className="text-sm font-sans-bold text-text-primary">{candidateSummary.totalExperience || 'Not identified from CV'}</Text>
                <Text className="text-[10px] text-text-muted">Relevant: {candidateSummary.relevantExperience || 'Not enough evidence'}</Text>
              </View>
              <View className="min-w-[138px] flex-1 p-2 border rounded bg-background border-border">
                <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-text-muted">Required Skills</Text>
                <Text className="text-base font-sans-bold text-text-primary">{skillsSummary?.scoreLabel || 'Not enough evidence'}</Text>
                <Text className="text-[10px] text-text-muted">
                  {candidateSummary.requiredSkillsCount != null
                    ? `${candidateSummary.matchedSkillsCount} / ${candidateSummary.requiredSkillsCount} required skills matched`
                    : 'Required skills not identified'}
                </Text>
              </View>
              <View className="min-w-[138px] flex-1 p-2 border rounded bg-background border-border">
                <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-text-muted">Candidate Domain</Text>
                <Text className="text-sm font-sans-bold text-text-primary">{candidateSummary.domain || 'Not identified from CV'}</Text>
                {candidateSummary.department ? <Text className="text-[10px] text-text-muted">Department: {candidateSummary.department}</Text> : null}
              </View>
            </View>

            <View className="flex-row items-start gap-2 p-2 border rounded bg-warning/10 border-warning/30">
              <AlertTriangle size={15} color={COLORS.warning} />
              <View className="flex-1 gap-0.5">
                <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-warning">Main Concern</Text>
                <Text className="text-xs leading-4 text-text-primary">{candidateSummary.mainConcern}</Text>
              </View>
            </View>
          </View>
        ) : null}
      </View>

      {/* 2. Tab Navigation */}
      <View className="flex-row gap-4 px-4 overflow-x-auto border-b bg-surface border-border">
        {[
          { id: 'overview', label: 'Overview', icon: <Activity size={14} color={activeTab === 'overview' ? COLORS.primary : COLORS.textMuted} /> },
          { id: 'processing', label: 'Processing Details', icon: <Layers size={14} color={activeTab === 'processing' ? COLORS.primary : COLORS.textMuted} /> },
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
        {reanalyzeError ? <ErrorBanner title={reanalyzeError.title} message={reanalyzeError.message} /> : null}
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
                <Text className="text-sm font-sans-bold text-text-primary">Reprocess Source CV</Text>
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
                This clears the stored analysis for this CV and restarts candidate processing. The current result will be replaced when processing completes.
              </Text>
            </View>
            <View className="flex-row justify-end gap-2 mt-2">
              <Button label="Cancel" variant="ghost" size="sm" onPress={() => setReprocessModalVisible(false)} />
              <Button label="Reprocess CV" variant="destructive" size="sm" onPress={handleConfirmReprocess} />
            </View>
          </Card>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
