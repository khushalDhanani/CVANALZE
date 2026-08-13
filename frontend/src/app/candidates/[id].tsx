import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  ArrowLeft, CheckCircle, Edit3,
  RefreshCw, X, Mail, Phone, UserCheck, Target, Sparkles,
  AlertTriangle, MapPin, Link, Code2
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
  PageHeader,
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
  buildCandidateDecisionNarratives,
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

type TabType = 'overview' | 'skills' | 'experience' | 'education' | 'matches' | 'risks' | 'cv';

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
  const [showAllSkills, setShowAllSkills] = useState<boolean>(false);
  const [showExperienceDetails, setShowExperienceDetails] = useState<boolean>(false);
  const [showAllEducation, setShowAllEducation] = useState<boolean>(false);
  const [showAllMatches, setShowAllMatches] = useState<boolean>(false);
  const [showAllRisks, setShowAllRisks] = useState<boolean>(false);
  const [showAllAiReasoning, setShowAllAiReasoning] = useState<boolean>(false);
  const [showAllCvDetails, setShowAllCvDetails] = useState<boolean>(false);
  const [technicalDetailsExpanded, setTechnicalDetailsExpanded] = useState<boolean>(false);
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
    setShowAllSkills(false);
    setShowExperienceDetails(false);
    setShowAllEducation(false);
    setShowAllMatches(false);
    setShowAllRisks(false);
    setShowAllAiReasoning(false);
    setShowAllCvDetails(false);
    setTechnicalDetailsExpanded(false);
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
    setActiveTab('cv');

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
  const decisionNarratives = useMemo(
    () => data && candidateView ? buildCandidateDecisionNarratives(data, candidateView, analysis, recommendations) : null,
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

  const visibleLimit = 6;
  const visibleSkills = (skills: string[]) => showAllSkills ? skills : skills.slice(0, visibleLimit);
  const visibleMatches = showAllMatches ? vacancyMatches : vacancyMatches.slice(0, 3);
  const visibleConcerns = showAllRisks ? decisionEvidence?.concerns || [] : (decisionEvidence?.concerns || []).slice(0, 4);
  const visibleStrengths = showAllRisks ? decisionEvidence?.strengths || [] : (decisionEvidence?.strengths || []).slice(0, 4);
  const reasoningMatches = vacancyMatches.slice(1).filter((match: any) => cleanCandidateText(match.ai_match_explanation || match.llm_reason || match.semantic_reason));

  const renderAiReasoning = () => (
    <Card className="gap-2.5 shadow-none border-info/30 bg-info/5 lg:flex-1">
      <View className="flex-row items-center gap-1.5 pb-2 border-b border-info/20">
        <Sparkles size={14} color={COLORS.info} />
        <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Additional AI Context</Text>
      </View>
      <Text className="text-[11px] leading-4 text-text-muted">AI interpretation is not confirmed CV evidence. Verify it against the factual tabs.</Text>
      {analysis?.ai_career_summary ? (
        <Text numberOfLines={showAllAiReasoning ? undefined : 4} className="text-xs leading-5 text-text-primary">
          {humanizeRecruiterText(analysis.ai_career_summary)}
        </Text>
      ) : null}
      {showAllAiReasoning && recommendations?.experience_assessment ? (
        <View className="gap-1">
          <Text className="text-[11px] font-sans-bold text-text-primary">Experience interpretation</Text>
          <Text className="text-xs leading-4 text-text-primary">{humanizeRecruiterText(recommendations.experience_assessment)}</Text>
        </View>
      ) : null}
      {(showAllAiReasoning ? reasoningMatches : reasoningMatches.slice(0, 1)).map((match: any, index: number) => (
        <View key={String(match.vacancy_id || match.job_id || index)} className="gap-1">
          <Text className="text-xs font-sans-bold text-text-primary">{cleanCandidateText(match.job_title) || `Vacancy ${index + 1}`}</Text>
          <VacancyEnrichmentPanel match={match} showDecisionMetadata={false} />
        </View>
      ))}
      {!analysis?.ai_career_summary && reasoningMatches.length === 0 ? <Text className="text-xs text-text-muted">An AI match explanation is not available.</Text> : null}
      {(analysis?.ai_career_summary || recommendations?.experience_assessment || reasoningMatches.length > 1) ? (
        <View className="items-start">
          <Button label={showAllAiReasoning ? 'Show Less' : 'View Full Reasoning'} variant="ghost" size="sm" onPress={() => setShowAllAiReasoning(!showAllAiReasoning)} />
        </View>
      ) : null}
    </Card>
  );

  const renderOverviewTab = () => (
    <View className="flex-col gap-3 lg:flex-row lg:items-start">
      <Card className="gap-2.5 shadow-none border-border lg:flex-1">
        <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Recruiter Snapshot</Text>
        <View className="gap-1.5 p-2 border rounded bg-primary/5 border-primary/20">
          <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-primary">Recommended Next Step</Text>
          <Text className="text-xs leading-4 text-text-primary">{recommendationAction}</Text>
        </View>
        {candidateView && (candidateView.email || candidateView.phone || candidateView.location) ? (
          <View className="gap-1.5">
            <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Contact</Text>
            {candidateView.email ? <FieldConfidenceView fieldName="email" value={candidateView.email} icon={<Mail size={14} color={COLORS.textFaint} />} /> : null}
            {candidateView.phone ? <FieldConfidenceView fieldName="phone" value={candidateView.phone} icon={<Phone size={14} color={COLORS.textFaint} />} /> : null}
            {candidateView.location ? <FieldConfidenceView fieldName="location" value={candidateView.location} icon={<MapPin size={14} color={COLORS.textFaint} />} /> : null}
          </View>
        ) : null}
        <View className="flex-row flex-wrap gap-2 pt-2 border-t border-border">
          <Button label="Review Skills" variant="secondary" size="sm" onPress={() => setActiveTab('skills')} />
          <Button label="Review Matches" variant="secondary" size="sm" onPress={() => setActiveTab('matches')} />
          <Button label="Review Risks" variant="secondary" size="sm" onPress={() => setActiveTab('risks')} />
        </View>
      </Card>
      {renderAiReasoning()}
    </View>
  );

  const renderSkillsTab = () => (
    <View className="gap-3">
      <Card className="gap-3 shadow-none border-border">
        <View className="flex-row flex-wrap items-center justify-between gap-2 pb-2 border-b border-border">
          <View className="flex-row items-center gap-1.5">
            <CheckCircle size={14} color={COLORS.primary} />
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Skills Intelligence</Text>
          </View>
          <View className="flex-row flex-wrap gap-1">
            {skillsSummary?.matchedLabel ? <Badge label={skillsSummary.matchedLabel} tone="success" /> : null}
            {skillsSummary?.missingLabel ? <Badge label={skillsSummary.missingLabel} tone={decisionEvidence?.skills.missingRequired.length ? 'warning' : 'neutral'} /> : null}
          </View>
        </View>
        <View className="flex-col gap-3 lg:flex-row">
          <View className="flex-1 gap-1.5">
            <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-success">Matched Skills</Text>
            {decisionEvidence?.skills.matched.length ? visibleSkills(decisionEvidence.skills.matched).map((skill) => (
              <Text key={skill} className="text-xs text-text-primary">✓ {skill}</Text>
            )) : <Text className="text-xs text-text-muted">No confirmed required-skill matches were found.</Text>}
          </View>
          <View className="flex-1 gap-1.5">
            <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-danger">Missing Required Skills</Text>
            {decisionEvidence?.skills.missingRequired.length ? visibleSkills(decisionEvidence.skills.missingRequired).map((skill) => (
              <Text key={skill} className="text-xs text-text-primary">• {skill}</Text>
            )) : <Text className="text-xs text-success">No identified required-skill gaps.</Text>}
          </View>
          <View className="flex-1 gap-1.5">
            <Text className="text-[11px] tracking-wider uppercase font-sans-bold text-text-muted">Additional CV Skills</Text>
            {decisionEvidence?.skills.additional.length ? (
              <View className="flex-row flex-wrap gap-1">
                {visibleSkills(decisionEvidence.skills.additional).map((skill) => <Badge key={skill} label={skill} tone="neutral" />)}
              </View>
            ) : <Text className="text-xs text-text-muted">No additional skills were identified.</Text>}
          </View>
        </View>
        {decisionEvidence && Math.max(decisionEvidence.skills.matched.length, decisionEvidence.skills.missingRequired.length, decisionEvidence.skills.additional.length) > visibleLimit ? (
          <View className="items-start"><Button label={showAllSkills ? 'Show Top Skills' : 'View All Skills'} variant="ghost" size="sm" onPress={() => setShowAllSkills(!showAllSkills)} /></View>
        ) : null}
      </Card>
    </View>
  );

  const renderExperienceTab = () => (
    <View className="gap-3">
      {!showExperienceDetails ? (
        <Card className="gap-2.5 shadow-none border-border">
          <View className="flex-row flex-wrap items-center justify-between gap-2">
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Experience Snapshot</Text>
            <Badge label={candidateSummary?.totalExperience || 'Not identified'} tone="neutral" />
          </View>
          {candidateView?.experience.length ? candidateView.experience.slice(0, 2).map((experience, index) => (
            <View key={`${experience.title || 'role'}-${index}`} className="gap-0.5 p-2 border rounded bg-background border-border">
              {experience.title ? <Text className="text-sm font-sans-bold text-text-primary">{experience.title}</Text> : null}
              <Text className="text-xs text-text-muted">{[experience.company, experience.dates].filter(Boolean).join(' • ')}</Text>
              {experience.responsibilities[0] ? <Text numberOfLines={2} className="text-[11px] leading-4 text-text-primary">{experience.responsibilities[0]}</Text> : null}
            </View>
          )) : <Text className="text-xs text-text-muted">Employment history was not identified from the CV.</Text>}
          {(data && experienceAnalysis) || (candidateView?.experience.length || 0) > 2 ? (
            <View className="items-start">
              <Button label="View Full Timeline" variant="secondary" size="sm" onPress={() => setShowExperienceDetails(true)} />
            </View>
          ) : null}
        </Card>
      ) : data && experienceAnalysis ? (
        <View className="gap-2">
          <View className="items-start"><Button label="Collapse Timeline" variant="ghost" size="sm" onPress={() => setShowExperienceDetails(false)} /></View>
          <ExperienceTimelineCard analysis={experienceAnalysis} candidateData={data} />
        </View>
      ) : candidateView?.experience.length ? (
        <Card className="gap-2.5 shadow-none border-border">
          <View className="flex-row items-center justify-between">
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Full Experience</Text>
            <Button label="Collapse" variant="ghost" size="sm" onPress={() => setShowExperienceDetails(false)} />
          </View>
          {candidateView.experience.map((experience, index) => (
            <View key={`${experience.title || 'role'}-${index}`} className="gap-1 p-2 border rounded bg-background border-border">
              {experience.title ? <Text className="text-sm font-sans-bold text-text-primary">{experience.title}</Text> : null}
              <Text className="text-xs text-text-muted">{[experience.company, experience.dates].filter(Boolean).join(' • ')}</Text>
              {experience.responsibilities.map((responsibility) => (
                <Text key={responsibility} className="text-[11px] leading-4 text-text-primary">• {responsibility}</Text>
              ))}
            </View>
          ))}
        </Card>
      ) : null}
    </View>
  );

  const renderEducationTab = () => {
    const educationItems = candidateView?.education || [];
    const visibleEducation = showAllEducation ? educationItems : educationItems.slice(0, 2);
    const visibleCertifications = showAllEducation ? candidateView?.certifications || [] : (candidateView?.certifications || []).slice(0, visibleLimit);
    return (
      <View className="flex-col gap-3 lg:flex-row lg:items-start">
        <Card className="gap-2.5 shadow-none border-border lg:flex-1">
          <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Education</Text>
          {visibleEducation.length ? visibleEducation.map((education, index) => (
            <View key={`${education.degree || 'education'}-${index}`} className="gap-0.5 p-2 border rounded bg-background border-border">
              {education.degree ? <Text className="text-sm font-sans-bold text-text-primary">{education.degree}</Text> : null}
              {education.institution ? <Text className="text-xs font-sans-medium text-text-muted">{education.institution}</Text> : null}
              {education.dates ? <Text className="text-xs text-text-muted">{education.dates}</Text> : null}
              {education.grade ? <Text className="text-[11px] text-text-primary">{education.grade}</Text> : null}
              {education.details ? <Text className="text-[11px] text-text-primary">{education.details}</Text> : null}
            </View>
          )) : <Text className="text-xs text-text-muted">Education was not identified from the CV.</Text>}
          {Math.max(educationItems.length, candidateView?.certifications.length || 0) > visibleLimit || educationItems.length > 2 ? (
            <View className="items-start">
              <Button label={showAllEducation ? 'Show Less' : 'View All Education'} variant="ghost" size="sm" onPress={() => setShowAllEducation(!showAllEducation)} />
            </View>
          ) : null}
        </Card>
        <Card className="gap-2.5 shadow-none border-border lg:flex-1">
          <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Qualification Review</Text>
          {decisionEvidence?.education ? (
            <View className={`gap-1 p-2 border rounded ${decisionEvidence.education.status === 'MATCHED' ? 'bg-success/5 border-success/20' : 'bg-warning/10 border-warning/30'}`}>
              <Text className={`text-xs font-sans-bold ${decisionEvidence.education.status === 'MATCHED' ? 'text-success' : 'text-warning'}`}>
                {decisionEvidence.education.status === 'MATCHED' ? '✓ Education Match' : '⚠ Education Review'}
              </Text>
              {decisionEvidence.education.requirement ? <Text className="text-xs text-text-primary">Requirement: {decisionEvidence.education.requirement}</Text> : null}
              {decisionEvidence.education.candidateEvidence ? <Text className="text-xs text-text-primary">CV evidence: {decisionEvidence.education.candidateEvidence}</Text> : null}
              {decisionEvidence.education.explanation ? <Text className="text-[11px] text-text-muted">{decisionEvidence.education.explanation}</Text> : null}
            </View>
          ) : <Text className="text-xs text-text-muted">No vacancy-specific education assessment is available.</Text>}
          {visibleCertifications.length ? (
            <View className="flex-row flex-wrap gap-1">
              {visibleCertifications.map((certification) => <Badge key={certification} label={certification} tone="neutral" />)}
            </View>
          ) : <Text className="text-xs text-text-muted">No certifications were identified.</Text>}
        </Card>
      </View>
    );
  };

  const renderMatchesTab = () => (
    <View className="gap-3">
      <Card className="gap-2.5 shadow-none border-border">
        <View className="flex-row items-center justify-between pb-2 border-b border-border">
          <View className="flex-row items-center gap-1.5">
            <Target size={14} color={COLORS.primary} />
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Vacancy Matches</Text>
          </View>
          <Badge label={`${vacancyMatches.length} Evaluated`} tone="neutral" />
        </View>
        <View className="flex-row flex-wrap gap-2">
          {visibleMatches.length ? visibleMatches.map((match: any, index: number) => {
            const evidence = buildVacancyDecisionEvidence(match);
            const rawStatus = match.vacancy_match_status || match.match_status || match.classification;
            return (
              <View key={String(match.vacancy_id || match.job_id || index)} className="flex-1 min-w-[280px] gap-2 p-2.5 border rounded bg-background border-border">
                <View className="flex-row items-start justify-between gap-2">
                  <View className="flex-1">
                    <Text className="text-sm font-sans-bold text-text-primary">{cleanCandidateText(match.job_title) || 'Vacancy title not available'}</Text>
                    <Text className="text-xs text-text-muted">{cleanCandidateText(match.department_name || match.department)}</Text>
                  </View>
                  <VacancyMatchStatusBadge status={rawStatus} score={evidence.overallFit} />
                </View>
                <View className="flex-row gap-1.5">
                  {[['Skills', evidence.skillsFit], ['Experience', evidence.experienceFit], ['Education', evidence.educationFit]].map(([label, value]) => value != null ? (
                    <View key={String(label)} className="flex-1 p-1.5 border rounded bg-surface border-border">
                      <Text className="text-[10px] text-text-muted">{label}</Text>
                      <Text className="text-xs font-sans-bold text-text-primary">{Math.round(Number(value))}%</Text>
                    </View>
                  ) : null)}
                </View>
                {evidence.whyItFits ? (
                  <Text numberOfLines={2} className="text-xs leading-4 text-text-primary">
                    <Text className="font-sans-bold text-success">Fit: </Text>{evidence.whyItFits}
                  </Text>
                ) : null}
                {evidence.mainGap ? (
                  <Text numberOfLines={2} className="text-xs leading-4 text-text-primary">
                    <Text className="font-sans-bold text-danger">Gap: </Text>{evidence.mainGap}
                  </Text>
                ) : null}
                <View className="items-start">
                  <Button
                    label="View Details / HR Review"
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
          }) : <Text className="text-xs text-text-muted">No active vacancy evaluation is available.</Text>}
        </View>
        {vacancyMatches.length > 3 ? (
          <View className="items-start">
            <Button label={showAllMatches ? 'Show Top Matches' : 'View All Matches'} variant="ghost" size="sm" onPress={() => setShowAllMatches(!showAllMatches)} />
          </View>
        ) : null}
      </Card>
    </View>
  );

  const renderRisksTab = () => (
    <View className="flex-col gap-3 lg:flex-row lg:items-start">
      <Card className="gap-2 shadow-none border-success/30 lg:flex-1">
        <Text className="text-xs tracking-wider uppercase font-sans-bold text-success">Strengths</Text>
        {visibleStrengths.length ? visibleStrengths.map((strength) => (
          <Text key={strength} className="text-xs leading-4 text-text-primary">✓ {strength}</Text>
        )) : <Text className="text-xs text-text-muted">Not enough evidence to identify strengths.</Text>}
      </Card>
      <Card className="gap-2 shadow-none border-warning/30 lg:flex-1">
        <Text className="text-xs tracking-wider uppercase font-sans-bold text-warning">Risks & Concerns</Text>
        {recommendationsLoading ? <Text className="text-xs text-text-muted">Loading supporting hiring insights…</Text> : null}
        {recommendationsError ? <Text className="text-xs text-danger">Additional insights are unavailable: {recommendationsError}</Text> : null}
        {visibleConcerns.length ? visibleConcerns.map((concern) => (
          <Text key={concern} className="text-xs leading-4 text-text-primary">⚠ {concern}</Text>
        )) : <Text className="text-xs text-success">No major concern was identified in the available evidence.</Text>}
        {Math.max(decisionEvidence?.strengths.length || 0, decisionEvidence?.concerns.length || 0) > 4 ? (
          <View className="items-start">
            <Button label={showAllRisks ? 'Show Top Evidence' : 'View All Evidence'} variant="ghost" size="sm" onPress={() => setShowAllRisks(!showAllRisks)} />
          </View>
        ) : null}
      </Card>
    </View>
  );

  const renderTechnicalDetails = () => {
    if (!data) return null;
    const provenanceRows = getProcessingProvenanceRows(data);
    const technicalMatchRows = [
      ['Calibration Version', bestMatch?.calibration_version],
      ['Scoring Profile', bestMatch?.scoring_profile_code],
      ['RRF Score', bestMatch?.rrf_score],
      ['Stage 0 Compatible', bestMatch?.stage0_compatible],
      ['Stage 1 Compatible', bestMatch?.stage1_compatible],
      ['Retrieval Path', bestMatch?.retrieval_path || bestMatch?.retrieval_source],
      ['Taxonomy Path', bestMatch?.taxonomy_path],
      ['Retrieval Provenance', bestMatch?.retrieval_provenance],
    ].map(([label, value]) => ({
      label: String(label),
      value: value && typeof value === 'object' ? JSON.stringify(value) : value == null ? '' : String(value),
    })).filter(({ value }) => value !== '');
    return (
      <Card className="p-0 overflow-hidden shadow-none border-border">
        <Pressable
          onPress={() => setTechnicalDetailsExpanded(!technicalDetailsExpanded)}
          accessibilityRole="button"
          accessibilityLabel="Toggle technical details"
          accessibilityState={{ expanded: technicalDetailsExpanded }}
          className="flex-row items-center justify-between p-2.5 min-h-[44px] active:bg-background"
        >
          <View>
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-muted">Technical Details</Text>
            <Text className="text-[11px] text-text-faint">Processing, extraction, versions, calibration, and debug provenance</Text>
          </View>
          <Text className="text-xs font-sans-bold text-primary">{technicalDetailsExpanded ? 'Collapse' : 'View Details'}</Text>
        </Pressable>
        {technicalDetailsExpanded ? (
          <View className="gap-2 p-3 border-t border-border">
            {cleanCandidateText(data.filename || data.id) ? (
              <View className="flex-row justify-between gap-3">
                <Text className="text-xs text-text-muted">Filename</Text>
                <Text selectable className="max-w-[65%] font-mono text-xs text-right text-text-primary">{data.filename || data.id}</Text>
              </View>
            ) : null}
            {rawTimestamp ? (
              <View className="flex-row justify-between gap-3">
                <Text className="text-xs text-text-muted">Analyzed At</Text>
                <Text className="font-mono text-xs text-text-primary">{formattedParsedAt}</Text>
              </View>
            ) : null}
            {typeof data.ocr_applied === 'boolean' ? (
              <View className="flex-row justify-between gap-3">
                <Text className="text-xs text-text-muted">Extraction Method</Text>
                <Badge label={data.ocr_applied ? 'RapidOCR' : 'Native PDF'} tone="info" />
              </View>
            ) : null}
            {data.page_count != null ? (
              <View className="flex-row justify-between gap-3">
                <Text className="text-xs text-text-muted">Pages</Text>
                <Text className="font-mono text-xs text-text-primary">{data.page_count} pg</Text>
              </View>
            ) : null}
            {cleanCandidateText(data.status) ? (
              <View className="flex-row justify-between gap-3">
                <Text className="text-xs text-text-muted">Status</Text>
                <Badge label={data.status!} tone={getStatusTone(data.status || undefined)} />
              </View>
            ) : null}
            <View className="gap-2 pt-2 border-t border-border">
              {provenanceRows.map(({ key, label, value }) => (
                <View key={key} className="flex-row items-start justify-between gap-3">
                  <Text className="text-xs text-text-muted">{label}</Text>
                  <Text
                    selectable={Boolean(value)}
                    className={`max-w-[65%] font-mono text-xs text-right ${value ? 'text-text-primary' : 'text-text-faint'}`}
                  >
                    {value || 'Not recorded'}
                  </Text>
                </View>
              ))}
            </View>
            {technicalMatchRows.length ? (
              <View className="gap-2 pt-2 border-t border-border">
                {technicalMatchRows.map(({ label, value }) => (
                  <View key={label} className="flex-row items-start justify-between gap-3">
                    <Text className="text-xs text-text-muted">{label}</Text>
                    <Text selectable className="max-w-[65%] font-mono text-xs text-right text-text-primary">{value}</Text>
                  </View>
                ))}
              </View>
            ) : null}
          </View>
        ) : null}
      </Card>
    );
  };

  const renderCvTab = () => {
    const projectItems = showAllCvDetails ? candidateView?.projects || [] : (candidateView?.projects || []).slice(0, 2);
    const focusItems = showAllCvDetails ? interviewFocusAreas : interviewFocusAreas.slice(0, 3);
    const similarItems = showAllCvDetails ? data?.similar_candidates || [] : (data?.similar_candidates || []).slice(0, 3);
    return (
      <View className="gap-3">
        <View className="flex-col gap-3 lg:flex-row lg:items-start">
          <Card className="gap-2.5 shadow-none border-border lg:flex-1">
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Contact & Profile</Text>
            {candidateView?.email ? <FieldConfidenceView fieldName="email" value={candidateView.email} icon={<Mail size={14} color={COLORS.textFaint} />} /> : null}
            {candidateView?.phone ? <FieldConfidenceView fieldName="phone" value={candidateView.phone} icon={<Phone size={14} color={COLORS.textFaint} />} /> : null}
            {candidateView?.location ? <FieldConfidenceView fieldName="location" value={candidateView.location} icon={<MapPin size={14} color={COLORS.textFaint} />} /> : null}
            {candidateView?.linkedin ? <FieldConfidenceView fieldName="linkedin" value={candidateView.linkedin} icon={<Link size={14} color={COLORS.textFaint} />} /> : null}
            {candidateView?.github ? <FieldConfidenceView fieldName="github" value={candidateView.github} icon={<Code2 size={14} color={COLORS.textFaint} />} /> : null}
            {suggestedRoles.length ? (
              <View className="gap-1">
                <Text className="text-[11px] font-sans-bold text-text-muted">Suggested Roles</Text>
                <View className="flex-row flex-wrap gap-1">
                  {(showAllCvDetails ? suggestedRoles : suggestedRoles.slice(0, visibleLimit)).map((role) => (
                    <Badge key={role} label={role} tone="neutral" />
                  ))}
                </View>
              </View>
            ) : null}
            {talentPools.length ? (
              <View className="gap-1">
                <Text className="text-[11px] font-sans-bold text-text-muted">Talent Pools</Text>
                <View className="flex-row flex-wrap gap-1">
                  {(showAllCvDetails ? talentPools : talentPools.slice(0, visibleLimit)).map((pool) => (
                    <Badge key={pool} label={pool} tone="info" />
                  ))}
                </View>
              </View>
            ) : null}
          </Card>
          <Card className="gap-2.5 shadow-none border-border lg:flex-1">
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Projects & Interview Focus</Text>
            {projectItems.length ? projectItems.map((project, index) => (
              <View key={`${project.name || 'project'}-${index}`} className="gap-0.5">
                <Text className="text-xs font-sans-bold text-text-primary">{project.name || `Project ${index + 1}`}</Text>
                {project.description ? (
                  <Text numberOfLines={showAllCvDetails ? undefined : 2} className="text-[11px] leading-4 text-text-primary">{project.description}</Text>
                ) : null}
              </View>
            )) : <Text className="text-xs text-text-muted">No projects were identified.</Text>}
            {focusItems.length ? (
              <View className="gap-1 pt-2 border-t border-border">
                <Text className="text-[11px] font-sans-bold text-text-muted">Interview Focus</Text>
                {focusItems.map((focus) => (
                  <Text key={focus} className="text-xs leading-4 text-text-primary">• {cleanRecommendationText(focus)}</Text>
                ))}
              </View>
            ) : null}
          </Card>
        </View>
        {similarItems.length ? (
          <Card className="gap-2 shadow-none border-border">
            <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Similar Candidates</Text>
            <View className="flex-row flex-wrap gap-2">
              {similarItems.map((similar: any, index: number) => {
                const similarCandidateId = cleanCandidateText(similar.candidate_id || similar.id);
                const similarCandidateName = cleanCandidateText(similar.full_name || similar.filename || similarCandidateId);
                const rawSimilarity = Number(similar.similarity_score ?? similar.score);
                const similarity = Number.isFinite(rawSimilarity)
                  ? Math.round(rawSimilarity <= 1 ? rawSimilarity * 100 : rawSimilarity)
                  : undefined;
                if (!similarCandidateId || !similarCandidateName) return null;
                return (
                  <Pressable
                    key={`${similarCandidateId}-${index}`}
                    onPress={() => router.push(`/candidates/${encodeURIComponent(similarCandidateId)}` as any)}
                    accessibilityRole="button"
                    accessibilityLabel={`Open ${similarCandidateName}`}
                    className="flex-1 min-w-[220px] flex-row items-center justify-between gap-2 p-2 border rounded bg-background border-border active:bg-surface-hover"
                  >
                    <Text className="text-xs font-sans-bold text-text-primary">{similarCandidateName}</Text>
                    {similarity != null ? <Badge label={`${similarity}%`} tone="neutral" /> : null}
                  </Pressable>
                );
              })}
            </View>
          </Card>
        ) : null}
        {(candidateView?.projects.length || interviewFocusAreas.length || suggestedRoles.length > visibleLimit
          || talentPools.length > visibleLimit || (data?.similar_candidates?.length || 0) > 3) ? (
          <View className="items-start">
            <Button
              label={showAllCvDetails ? 'Show Compact CV Details' : 'View More CV Details'}
              variant="ghost"
              size="sm"
              onPress={() => setShowAllCvDetails(!showAllCvDetails)}
            />
          </View>
        ) : null}
        {candidateView?.extractedText ? (
          <Card className="gap-2 shadow-none border-border">
            <View className="flex-row items-center justify-between">
              <Text className="text-xs tracking-wider uppercase font-sans-bold text-text-primary">Extracted CV</Text>
              <Button label={showFullText ? 'Collapse' : 'View Full CV'} variant="ghost" size="sm" onPress={() => setShowFullText(!showFullText)} />
            </View>
            <Text numberOfLines={showFullText ? undefined : 6} className="text-[11px] font-mono text-text-primary leading-5">{candidateView.extractedText}</Text>
          </Card>
        ) : null}
        {renderTechnicalDetails()}
      </View>
    );
  };

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
      <PageHeader
        title="CV Intelligence Dashboard"
        leading={(
          <Pressable
            onPress={handleBack}
            accessibilityRole="button"
            accessibilityLabel="Back to Candidate Directory"
            className="min-h-[44px] min-w-[44px] sm:min-h-[36px] sm:min-w-[36px] items-center justify-center"
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <ArrowLeft size={18} color={COLORS.textPrimary} />
          </Pressable>
        )}
        actions={(
          <>
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
          </>
        )}
      />

      {/* 1. Recruiter 5-second summary */}
      <View className="z-10 px-3 py-2.5 border-b bg-surface border-border">
        {candidateSummary ? (
          <View className="gap-2.5">
            <View className="flex-col justify-between gap-2 md:flex-row md:items-start">
              <View className="flex-row items-center flex-1 min-w-0 gap-2">
                <View className="items-center justify-center w-9 h-9 rounded-full bg-primary/10">
                  <UserCheck size={18} color={COLORS.primary} />
                </View>
                <View className="flex-1 min-w-0">
                  <Text numberOfLines={1} ellipsizeMode="tail" className="text-lg font-sans-bold text-text-primary">{candidateSummary.name}</Text>
                  <Text numberOfLines={1} ellipsizeMode="tail" className="text-sm font-sans-bold text-text-primary">
                    {candidateSummary.role || 'Latest role not identified from CV'}
                  </Text>
                  {candidateSummary.company ? <Text numberOfLines={1} ellipsizeMode="tail" className="text-xs text-text-muted">{candidateSummary.company}</Text> : null}
                </View>
              </View>
              <View className="items-start gap-1 md:items-end">
                <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-text-muted">Recommendation</Text>
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
                <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-text-muted">Skills Match</Text>
                <Text className="text-base font-sans-bold text-text-primary">{skillsSummary?.scoreLabel || 'Not enough evidence'}</Text>
                <Text className="text-[10px] text-text-muted">
                  {candidateSummary.requiredSkillsCount != null
                    ? `${candidateSummary.matchedSkillsCount} / ${candidateSummary.requiredSkillsCount} required skills matched`
                    : 'Required skills not identified'}
                </Text>
              </View>
              <View className="min-w-[138px] flex-1 p-2 border rounded bg-background border-border">
                <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-text-muted">Domain</Text>
                <Text className="text-sm font-sans-bold text-text-primary">{candidateSummary.domain || 'Not identified from CV'}</Text>
                {candidateSummary.department ? <Text className="text-[10px] text-text-muted">Department: {candidateSummary.department}</Text> : null}
              </View>
            </View>

            <View className="flex-col gap-2 lg:flex-row">
              <View className="flex-row items-start flex-1 gap-2 p-2 border rounded bg-success/5 border-success/20">
                <CheckCircle size={15} color={COLORS.success} />
                <View className="flex-1 gap-0.5">
                  <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-success">Top Strength</Text>
                  <Text className="text-xs leading-5 text-text-primary">{decisionNarratives?.topStrength}</Text>
                </View>
              </View>
              <View className="flex-row items-start flex-1 gap-2 p-2 border rounded bg-warning/10 border-warning/30">
                <AlertTriangle size={15} color={COLORS.warning} />
                <View className="flex-1 gap-0.5">
                  <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-warning">Main Concern</Text>
                  <Text className="text-xs leading-5 text-text-primary">{decisionNarratives?.mainConcern}</Text>
                </View>
              </View>
              <View className="flex-row items-start flex-1 gap-2 p-2 border rounded bg-info/5 border-info/20">
                <Sparkles size={15} color={COLORS.info} />
                <View className="flex-1 gap-0.5">
                  <Text className="text-[10px] tracking-wider uppercase font-sans-bold text-info">AI Match Explanation</Text>
                  <Text className="text-xs leading-5 text-text-primary">{decisionNarratives?.aiMatchExplanation}</Text>
                </View>
              </View>
            </View>
          </View>
        ) : null}
      </View>

      {/* 2. Tab Navigation */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} className="flex-grow-0 border-b bg-surface border-border" contentContainerStyle={{ paddingHorizontal: 12, gap: 8 }}>
        {([
          ['overview', 'Overview'],
          ['skills', 'Skills'],
          ['experience', 'Experience'],
          ['education', 'Education'],
          ['matches', 'Matches'],
          ['risks', 'Risks'],
          ['cv', 'CV'],
        ] as [TabType, string][]).map(([tabId, label]) => (
          <Pressable
            key={tabId}
            className={`px-1.5 py-2 min-h-[44px] sm:min-h-[36px] border-b-2 items-center justify-center ${activeTab === tabId ? 'border-primary' : 'border-transparent'}`}
            onPress={() => setActiveTab(tabId)}
            accessibilityRole="tab"
            accessibilityLabel={label}
            accessibilityState={{ selected: activeTab === tabId }}
            hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
          >
            <Text className={`text-xs font-sans-bold ${activeTab === tabId ? 'text-primary' : 'text-text-muted'}`}>
              {label}
            </Text>
          </Pressable>
        ))}
      </ScrollView>

      {/* 3. Main Content Area */}
      <ScrollView className="flex-1 px-3 py-3">
        {reanalyzeError ? <ErrorBanner title={reanalyzeError.title} message={reanalyzeError.message} /> : null}
        {isReprocessing ? (
          <View className="mb-3">
            <StepProgressCard
              currentStepIndex={currentStepIndex}
              stepStates={stepStates}
              statusMessage={reprocessStatusMsg}
              elapsedSeconds={elapsedSeconds}
              isComplete={false}
              useLlmEnrichment={true}
            />
          </View>
        ) : null}
        {reprocessError ? <View className="mb-3"><ErrorBanner title="Reprocessing Error" message={reprocessError} /></View> : null}
        {loading && !isReprocessing ? (
          <View className="items-center justify-center flex-1 py-8">
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
          <View className="pb-4">
            {activeTab === 'overview' && renderOverviewTab()}
            {activeTab === 'skills' && renderSkillsTab()}
            {activeTab === 'experience' && renderExperienceTab()}
            {activeTab === 'education' && renderEducationTab()}
            {activeTab === 'matches' && renderMatchesTab()}
            {activeTab === 'risks' && renderRisksTab()}
            {activeTab === 'cv' && renderCvTab()}
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
          <Card className="w-full max-w-md gap-2.5 bg-surface border-border">
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
