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
import { Card, Button, Badge, DenseRow, FieldConfidenceView, Breadcrumbs } from '@/components/ui';
import { ComponentScoreBar } from '@/components/ui/ComponentScoreBar';
import { ScoreBadge } from '@/components/ui/ScoreBadge';
import { HrReviewModal } from '@/components/ui/HrReviewModal';
import { StepProgressCard, StepState } from '@/components/ui/StepProgressCard';
import { usePageTitle } from '@/hooks/usePageTitle';
import { COLORS } from '@/constants/colors';

type TabType = 'overview' | 'timeline';

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
    setActiveTab('timeline'); // Jump to timeline to see progress

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

          const isTerminated =
            statusStr === 'COMPLETED' || statusStr === 'NEW_CV' || statusStr === 'REPROCESSED' ||
            pct >= 100 || statusRes.is_complete || pollCount >= 40 ||
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
        } catch (err: any) { }
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
      // Wait a bit before fetching to allow backend processing
      setTimeout(() => {
        fetchDetail();
        setIsReanalyzing(false);
      }, 1500);
    } catch (err: any) {
      console.warn("Reanalysis failed:", err);
      setIsReanalyzing(false);
    }
  };

  const rawAnalysis = data?.enriched_match_analysis || data?.match_analysis;
  const analysis: any = rawAnalysis;
  const bestMatch = rawAnalysis?.best_match;
  const scanId = data?.scan_id || data?.id || id || '';

  const rawTimestamp = data?.parsed_at || data?.scanned_at || data?.created_at;
  const formattedParsedAt = rawTimestamp
    ? new Date(rawTimestamp).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
    : 'N/A';

  const formatHiringRecLabel = (rec: string | undefined) => {
    if (!rec) return 'Needs Further Review';
    if (rec === 'HIRE') return 'Highly Recommended';
    if (rec === 'CONSIDER') return 'Potential Fit';
    if (rec === 'REJECT') return 'Needs Further Review';
    return rec;
  };

  const getHiringRecTone = (rec: string | undefined) => {
    const formatted = formatHiringRecLabel(rec);
    if (formatted === 'Highly Recommended') return 'success';
    if (formatted === 'Recommended') return 'info';
    if (formatted === 'Potential Fit') return 'warning';
    if (formatted === 'Needs Further Review') return 'danger';
    return 'neutral';
  };

  // -------------------------------------------------------------
  // TAB RENDERERS
  // -------------------------------------------------------------

  const renderOverviewTab = () => (
    <View className="flex-row gap-4 flex-wrap md:flex-nowrap">
      {/* Left Column (Candidate Data) */}
      <View className="w-full md:w-[45%] lg:w-5/12 gap-4">

        {/* Contact Info Card */}
        <Card className="p-3 gap-2 border-border shadow-none">
          <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider mb-1">Contact Information</Text>
          <View className="flex-row items-center gap-2">
            <Mail size={14} color={COLORS.textMuted} />
            <Text className="text-sm font-sans text-text-primary">{data?.email || "—"}</Text>
          </View>
          <View className="flex-row items-center gap-2">
            <Phone size={14} color={COLORS.textMuted} />
            <Text className="text-sm font-sans text-text-primary">{data?.phone || "—"}</Text>
          </View>
          <View className="flex-row items-center gap-2">
            <MapPin size={14} color={COLORS.textMuted} />
            <Text className="text-sm font-sans text-text-primary">
              {data?.location || data?.resume_json?.contact_info?.location || "—"}
            </Text>
          </View>
        </Card>

        {/* Experience Timeline */}
        {((data?.resume_json?.work_experience && data.resume_json.work_experience.length > 0) ||
          (data?.resume_json?.experience && data.resume_json.experience.length > 0) ||
          (data?.normalized_resume?.employment && data.normalized_resume.employment.length > 0)) && (
          <Card className="p-3 gap-3 border-border shadow-none">
            <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider">Experience</Text>
            {(
              data?.resume_json?.work_experience ||
              data?.resume_json?.experience ||
              data?.normalized_resume?.employment ||
              []
            ).slice(0, 5).map((exp: any, idx: number) => {
              const title = exp.job_title?.normalized_value || exp.job_title || 'Untitled Role';
              const company = exp.company?.normalized_value || exp.company || exp.company_name || 'Organization';
              const dates = exp.interval?.raw_value || exp.dates || exp.duration || 'N/A';
              return (
                <View key={idx} className="border-l-2 border-border pl-3 pb-3">
                  <Text className="text-xs font-sans-bold text-text-primary">{title}</Text>
                  <Text className="text-xs font-sans text-text-muted">{company} • {dates}</Text>
                </View>
              );
            })}
            {(
              (data?.resume_json?.work_experience || data?.resume_json?.experience || data?.normalized_resume?.employment || []).length > 5
            ) && (
              <Text className="text-[10px] text-primary font-sans-medium cursor-pointer" onPress={() => setShowFullText(true)}>
                + {(data?.resume_json?.work_experience || data?.resume_json?.experience || data?.normalized_resume?.employment || []).length - 5} more roles
              </Text>
            )}
          </Card>
        )}

        {/* Education & Certs */}
        <Card className="p-3 gap-3 border-border shadow-none">
          <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider">Education</Text>
          {(data?.resume_json?.education || []).length > 0 ? (
            data!.resume_json!.education!.slice(0, 3).map((edu: any, idx: number) => (
              <View key={idx}>
                <Text className="text-xs font-sans-bold text-text-primary">{edu.degree}</Text>
                <Text className="text-[10px] font-sans text-text-muted">{edu.institution} • {edu.passing_year}</Text>
              </View>
            ))
          ) : (
            <Text className="text-xs text-text-muted">No education history found.</Text>
          )}

          {(data?.resume_json?.certifications || []).length > 0 && (
            <View className="mt-2 border-t border-border pt-2 gap-1.5">
              <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider">Certifications</Text>
              <View className="flex-row flex-wrap gap-1">
                {data!.resume_json!.certifications!.slice(0, 5).map((cert: string, idx: number) => (
                  <Badge key={idx} label={cert} tone="neutral" />
                ))}
              </View>
            </View>
          )}
        </Card>

        {/* Candidate Skills */}
        {(data?.resume_json?.skills || []).length > 0 && (
          <Card className="p-3 gap-2 border-border shadow-none">
            <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider">Skills</Text>
            <View className="flex-row flex-wrap gap-1">
              {data!.resume_json!.skills!.map((skill: string, idx: number) => (
                <Badge key={idx} label={skill} tone="neutral" />
              ))}
            </View>
          </Card>
        )}

        {/* Suitable Openings */}
        {analysis?.suitable_openings && analysis.suitable_openings.length > 0 ? (
          analysis.suitable_openings.map((match: any, idx: number) => {
            const matchLabel = match.classification === 'HIGH'
              ? (idx === 0 ? 'Top Job Match' : 'Strong Match')
              : 'Potential Match';
            const isTop = idx === 0 && match.classification === 'HIGH';
            return (
            <Card key={idx} className={`p-3 border-primary/40 shadow-none gap-2 ${idx > 0 ? 'mt-3 opacity-90 border-border' : ''}`}>
              <View className="flex-row justify-between items-start">
                <View className="flex-1">
                  <View className="flex-row items-center gap-1.5 mb-1">
                    <Award size={14} color={isTop ? COLORS.primary : COLORS.textMuted} />
                    <Text className={`text-xs font-sans-bold uppercase tracking-wider ${isTop ? 'text-primary' : 'text-text-muted'}`}>
                      {matchLabel}
                    </Text>
                  </View>
                  <Text className="text-sm font-sans-bold text-text-primary">{match.job_title}</Text>
                  <Text className="text-[11px] font-sans-medium text-text-muted">{match.department_name || match.department}</Text>
                </View>
                <ScoreBadge score={match.overall_score || match.score || 0} classification={match.classification} />
              </View>
              
              {match.component_scores ? (
                 <ComponentScoreBar scores={match.component_scores} />
              ) : null}

              {match.llm_reason ? (
                <View className="bg-primary/5 p-2 mt-1 rounded border border-primary/10">
                  <Text className="text-xs text-text-primary leading-4 font-sans-bold mb-1">AI Reasoning:</Text>
                  <Text className="text-xs text-text-primary leading-4">{match.llm_reason}</Text>
                </View>
              ) : null}
              
              {match.missing_skills && match.missing_skills.length > 0 && (
                 <View className="mt-1">
                   <Text className="text-[10px] font-sans-bold text-danger uppercase mb-1">Skill Gaps:</Text>
                   <View className="flex-row flex-wrap gap-1">
                     {match.missing_skills.map((s: string, sIdx: number) => (
                       <Badge key={sIdx} label={s} tone="danger" />
                     ))}
                   </View>
                 </View>
              )}

              {(match.recommendation && !match.llm_reason) ? (
                <View className="bg-primary/5 p-2 mt-1 rounded border border-primary/10">
                  <Text className="text-xs text-text-primary leading-4">💡 {match.recommendation}</Text>
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
          );})
        ) : bestMatch && analysis?.has_genuine_match ? (
          <Card className="p-3 border-primary/40 shadow-none gap-2">
            <View className="flex-row justify-between items-start">
              <View className="flex-1">
                <View className="flex-row items-center gap-1.5 mb-1">
                  <Award size={14} color={COLORS.primary} />
                  <Text className="text-xs font-sans-bold text-primary uppercase tracking-wider">Top Job Match</Text>
                </View>
                <Text className="text-sm font-sans-bold text-text-primary">{bestMatch.job_title}</Text>
                <Text className="text-[11px] font-sans-medium text-text-muted">{bestMatch.department_name}</Text>
              </View>
              <ScoreBadge score={bestMatch.overall_score || bestMatch.score || 0} classification={bestMatch.classification} />
            </View>
            
            {bestMatch.component_scores ? (
               <ComponentScoreBar scores={bestMatch.component_scores} />
            ) : null}

            {bestMatch.recommendation ? (
              <View className="bg-primary/5 p-2 mt-1 rounded border border-primary/10">
                <Text className="text-xs text-text-primary leading-4">💡 {bestMatch.recommendation}</Text>
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
          <Card className="p-3 border-warning/30 shadow-none gap-2 bg-warning/5">
            <View className="flex-row items-center gap-1.5 mb-1 border-b border-warning/20 pb-2">
              <AlertTriangle size={14} color={COLORS.warning} />
              <Text className="text-xs font-sans-bold text-warning uppercase tracking-wider">
                Manual Review Required ({analysis.unsuitable_openings.length})
              </Text>
            </View>
            <Text className="text-[10px] text-text-muted mb-1">
              These vacancies scored below the suitability threshold. HR review is recommended before any decision.
            </Text>
            {analysis.unsuitable_openings.map((match: any, idx: number) => (
              <View key={idx} className="flex-row justify-between items-center p-2 bg-background border border-border rounded">
                <View className="flex-1 pr-2">
                  <Text className="text-xs font-sans-bold text-text-primary">{match.job_title}</Text>
                  <Text className="text-[10px] text-text-muted">{match.department_name || match.department}</Text>
                </View>
                <View className="flex-row items-center gap-2">
                  <ScoreBadge score={match.overall_score || match.score || 0} classification={match.classification} />
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

        {/* Active Vacancy Summary Card */}
        <Card className="p-3 border-border shadow-none">
          <View className="flex-row items-center justify-between border-b border-border pb-2 mb-2">
            <View className="flex-row items-center gap-1.5">
              <Target size={14} color={analysis?.has_genuine_match ? COLORS.success : COLORS.warning} />
              <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">Active Vacancy Summary</Text>
            </View>
            <Badge label={analysis?.has_genuine_match ? 'Genuine Match' : 'No Match'} tone={analysis?.has_genuine_match ? 'success' : 'warning'} />
          </View>
          <View className={`p-2 rounded ${analysis?.has_genuine_match ? 'bg-success/5 border border-success/20' : 'bg-warning/5 border border-warning/20'}`}>
            <Text className="text-xs text-text-primary leading-5">{analysis?.active_vacancy_summary || 'No suitable active vacancy found.'}</Text>
          </View>
        </Card>

        {/* Similar Candidates (pgvector) */}
        {data?.similar_candidates && data.similar_candidates.length > 0 && (
          <Card className="p-3 border-border shadow-none gap-2">
            <View className="flex-row items-center justify-between border-b border-border pb-2 mb-1">
              <View className="flex-row items-center gap-1.5">
                <Users size={14} color={COLORS.primary} />
                <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">Similar Candidates</Text>
              </View>
              <Badge label={`${data.similar_candidates.length} Profiles`} tone="info" />
            </View>
            <View className="gap-2">
              {data.similar_candidates.map((sim: any, idx: number) => {
                const simScore = Math.round((sim.similarity_score || sim.score || 0) * 100);
                return (
                  <View key={idx} className="flex-row justify-between items-center p-2 bg-background border border-border rounded">
                    <View>
                      <Text className="text-xs font-sans-bold text-text-primary cursor-pointer" onPress={() => router.push(`/candidates/${encodeURIComponent(sim.candidate_id || sim.id)}` as any)}>
                        {sim.full_name || sim.filename || sim.candidate_id}
                      </Text>
                      <Text className="text-[10px] text-text-muted">{sim.primary_department ? `Dept: ${sim.primary_department}` : 'Vector Match'}</Text>
                    </View>
                    <Badge label={`${simScore}%`} tone={simScore >= 80 ? 'success' : simScore >= 60 ? 'info' : 'neutral'} />
                  </View>
                );
              })}
            </View>
          </Card>
        )}

        {/* Resume Extracted Text */}
        <Card className="p-0 border-border shadow-none overflow-hidden">
          <View className="flex-row justify-between items-center p-3 border-b border-border bg-background">
            <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider">Extracted CV Text</Text>
            <Button
              label={showFullText ? 'Collapse' : 'Expand Full'}
              variant="ghost"
              size="sm"
              onPress={() => setShowFullText(!showFullText)}
            />
          </View>
          <ScrollView className="p-3" style={{ maxHeight: showFullText ? undefined : 200 }}>
            <Text className="text-[11px] font-mono text-text-primary leading-5">
              {data?.markdown || data?.text || 'No text extracted.'}
            </Text>
          </ScrollView>
        </Card>

      </View>

      {/* Right Column (Hiring Intelligence & Matches) */}
      <View className="w-full md:w-[55%] lg:w-7/12 gap-4">

        {/* Recommendation Engine */}
        {recommendationsLoading ? (
          <Card className="p-3 border-info/30 shadow-none items-center justify-center py-8">
            <ActivityIndicator size="small" color={COLORS.info} />
            <Text className="text-xs font-sans text-text-muted mt-2">Running Hiring Intelligence...</Text>
          </Card>
        ) : recommendationsError ? (
          <Card className="p-3 bg-danger/5 border-danger/30 shadow-none">
            <Text className="text-xs text-danger">{recommendationsError}</Text>
          </Card>
        ) : recommendations ? (
          <Card className="p-3 border-info/40 shadow-none gap-3">
            <View className="flex-row justify-between items-center pb-2 border-b border-border">
              <View className="flex-row items-center gap-1.5">
                <Sparkles size={14} color={COLORS.info} />
                <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">Hiring Intelligence</Text>
              </View>
              <Badge
                label={formatHiringRecLabel(recommendations.hiring_recommendation)}
                tone={getHiringRecTone(recommendations.hiring_recommendation)}
              />
            </View>

            {/* 2-Column Insight Grid inside Card */}
            <View className="flex-row flex-wrap gap-2">
              <View className="flex-1 min-w-[140px] bg-background p-2 rounded border border-border">
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-0.5">Experience & Seniority</Text>
                <Text className="text-xs leading-4 text-text-primary">{recommendations.experience_assessment || 'N/A'}</Text>
              </View>
              <View className="flex-1 min-w-[140px] bg-background p-2 rounded border border-border">
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-0.5">Role & Dept Fit</Text>
                <Text className="text-xs leading-4 text-text-primary">{recommendations.role_department_fit || 'N/A'}</Text>
              </View>
            </View>

            {recommendations.risk_flags && recommendations.risk_flags.length > 0 && (
              <View className="bg-danger/5 p-2 border border-danger/20 rounded">
                <View className="flex-row items-center gap-1 mb-1">
                  <AlertTriangle size={12} color={COLORS.danger} />
                  <Text className="text-[10px] font-sans-bold text-danger uppercase">Risk Flags</Text>
                </View>
                {recommendations.risk_flags.map((flag, idx) => (
                  <Text key={idx} className="text-xs text-danger leading-4">• {flag}</Text>
                ))}
              </View>
            )}

            {recommendations.strengths && recommendations.strengths.length > 0 && (
              <View>
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-1">Key Strengths</Text>
                {recommendations.strengths.map((str, idx) => (
                  <Text key={idx} className="text-xs text-text-primary leading-4 mb-0.5"><Text className="text-success">✓</Text> {str}</Text>
                ))}
              </View>
            )}

            {recommendations.interview_focus_areas && recommendations.interview_focus_areas.length > 0 && (
              <View className="pt-2 border-t border-border">
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase mb-1">Interview Focus Areas</Text>
                {recommendations.interview_focus_areas.map((focus, idx) => (
                  <Text key={idx} className="text-xs text-text-primary leading-4 mb-0.5">• {focus}</Text>
                ))}
              </View>
            )}
          </Card>
        ) : null}

        {/* AI Career Summary & Domain Insights */}
        {(analysis?.ai_career_summary || analysis?.recommended_department || analysis?.professional_domain) && (
          <Card className="p-3 border-border shadow-none gap-3">
            <View className="flex-row items-center gap-1.5 border-b border-border pb-2">
              <CpuIcon size={14} color={COLORS.textMuted} />
              <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider">AI Domain Analysis</Text>
            </View>

            {analysis?.ai_career_summary ? (
              <Text className="text-xs font-sans text-text-primary leading-5 mb-2">{analysis.ai_career_summary}</Text>
            ) : null}

            <View className="flex-row items-center justify-between">
              <Text className="text-xs font-sans-medium text-text-muted">Recommended Dept:</Text>
              <Badge label={analysis?.recommended_department || analysis?.primary_department || 'General'} tone="info" />
            </View>
            <View className="flex-row items-center justify-between mt-1">
              <Text className="text-xs font-sans-medium text-text-muted">Professional Domain:</Text>
              <Text className="text-xs font-sans-bold text-text-primary">{analysis?.professional_domain || "N/A"}</Text>
            </View>
            {analysis?.suitable_job_roles && (
              <View className="mt-2 border-t border-border pt-2">
                <Text className="text-xs font-sans-medium text-text-muted mb-1">Suitable Job Roles:</Text>
                <View className="flex-row flex-wrap gap-1">
                  {analysis.suitable_job_roles.map((role: string, idx: number) => (
                    <Badge key={idx} label={role} tone="neutral" />
                  ))}
                </View>
              </View>
            )}
            {recommendations?.talent_pools && (
              <View className="mt-2 border-t border-border pt-2">
                <Text className="text-xs font-sans-medium text-text-muted mb-1">Assigned Talent Pools:</Text>
                <View className="flex-row flex-wrap gap-1">
                  {recommendations.talent_pools.map((pool: string, idx: number) => (
                    <Badge key={idx} label={pool} tone="success" />
                  ))}
                </View>
              </View>
            )}
            {recommendations?.related_skills && (
              <View className="mt-2 border-t border-border pt-2">
                <Text className="text-[10px] font-sans-bold text-text-muted uppercase tracking-wider mb-1">Semantically Related Skills:</Text>
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

  const renderTimelineTab = () => (
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
        <Card className="bg-danger/10 border-danger/30 p-3 flex-row items-center justify-between">
          <View className="flex-row items-center gap-2 flex-1 pr-2">
            <AlertCircle size={14} color={COLORS.danger} />
            <Text className="text-xs font-sans-medium text-danger flex-1">{reprocessError}</Text>
          </View>
          <Button label="Retry" variant="secondary" size="sm" onPress={() => setReprocessModalVisible(true)} />
        </Card>
      )}

      <Card className="p-3 border-border shadow-none">
        <Text className="text-xs font-sans-bold text-text-muted uppercase tracking-wider mb-2">Processing Metadata</Text>
        <View className="gap-2">
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Filename:</Text>
            <Text className="text-xs font-mono text-text-primary">{data?.filename || data?.id}</Text>
          </View>
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Analyzed At:</Text>
            <Text className="text-xs font-mono text-text-primary">{formattedParsedAt}</Text>
          </View>
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Extraction Method:</Text>
            <Badge label={data?.ocr_applied ? 'RapidOCR' : 'Native PDF'} tone="info" />
          </View>
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Pages:</Text>
            <Text className="text-xs font-mono text-text-primary">{data?.page_count || 1}</Text>
          </View>
          <View className="flex-row items-center justify-between">
            <Text className="text-xs text-text-muted">Status:</Text>
            <Badge label={data?.status || 'UNKNOWN'} tone={data?.status === 'FAILED' ? 'danger' : 'success'} />
          </View>
        </View>
      </Card>
    </View>
  );

  // -------------------------------------------------------------
  // MAIN RENDER
  // -------------------------------------------------------------

  return (
    <SafeAreaView className="flex-1 bg-[#F8FAFC]">
      <Breadcrumbs
        items={[
          { label: 'Candidate Directory', href: getReturnHref() },
          { label: candName || id || 'Candidate Profile' },
        ]}
      />
      {/* 1. Header Area (Compact & Sticky) */}
      <View className="bg-white border-b border-border shadow-sm z-10 px-4 py-3">
        <View className="flex-row items-start justify-between">

          {/* Left Side: Back Button & High-Level Identity */}
          <View className="flex-row gap-3 flex-1">
            <Pressable onPress={handleBack} className="mt-1">
              <ArrowLeft size={16} color={COLORS.textMuted} />
            </Pressable>
            <View className="flex-row gap-3 items-center flex-1 pr-4">
              <View className="w-10 h-10 rounded-full bg-primary/10 items-center justify-center">
                <UserCheck size={18} color={COLORS.primary} />
              </View>
              <View>
                <Text className="text-sm font-sans-bold text-text-primary line-clamp-1">
                  {data?.full_name || data?.candidate_name || data?.resume_json?.contact_info?.name || 'Unknown Candidate'}
                </Text>
                <Text className="text-[11px] font-sans-medium text-text-muted line-clamp-1">
                  {data?.job_title || data?.resume_json?.contact_info?.job_title || data?.match_analysis?.best_match?.job_title || 'No Title'} • {data?.company_name || 'No Company'}
                </Text>
              </View>
            </View>
          </View>

          {/* Right Side: Primary Metric & Actions */}
          <View className="flex-row items-center gap-3">
            {/* Hiring Recommendation Badge placed prominently */}
            {recommendations && !recommendationsLoading && recommendations.hiring_recommendation ? (
              <View className="hidden md:flex">
                <Badge
                  label={formatHiringRecLabel(recommendations.hiring_recommendation)}
                  tone={getHiringRecTone(recommendations.hiring_recommendation)}
                />
              </View>
            ) : null}
            {data?.experience_years != null ? (
              <View className="items-center px-3 py-1 bg-background border border-border rounded">
                <Text className="text-[10px] text-text-muted uppercase font-sans-bold">Experience</Text>
                <Text className="text-xs font-sans-bold text-text-primary">{data.experience_years} Yrs • {data.seniority || 'Assessed'}</Text>
              </View>
            ) : null}
            {bestMatch?.overall_score != null ? (
              <View className="items-center px-3 py-1 bg-background border border-border rounded">
                <Text className="text-[10px] text-text-muted uppercase font-sans-bold">AI Match</Text>
                <Text className="text-xs font-sans-bold text-primary">{Math.round(bestMatch.overall_score)}%</Text>
              </View>
            ) : null}
            <View className="flex-row gap-2">
              <View className="h-8 rounded-md overflow-hidden bg-secondary">
                <Button
                  variant="secondary"
                  size="sm"
                  label={isReanalyzing ? "Analyzing..." : "Reanalyze"}
                  icon={!isReanalyzing ? <Sparkles size={14} color={COLORS.primary} /> : undefined}
                  onPress={handleReanalyze}
                  disabled={isReanalyzing || isReprocessing}
                />
              </View>
              <View className="w-8 h-8 rounded-md overflow-hidden bg-secondary border border-border">
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<RefreshCw size={14} color={COLORS.textMuted} />}
                  onPress={() => setReprocessModalVisible(true)}
                  disabled={isReprocessing}
                />
              </View>
            </View>
          </View>

        </View>
      </View>

      {/* 2. Tab Navigation */}
      <View className="bg-white border-b border-border px-4 flex-row gap-4 overflow-x-auto">
        {[
          { id: 'overview', label: 'Overview', icon: <Activity size={14} color={activeTab === 'overview' ? COLORS.primary : COLORS.textMuted} /> },
          { id: 'timeline', label: 'Timeline', icon: <Layers size={14} color={activeTab === 'timeline' ? COLORS.primary : COLORS.textMuted} /> },
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
          <View className="flex-1 justify-center items-center py-16">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">Loading profile dashboard...</Text>
          </View>
        ) : error || !data ? (
          <Card className="bg-danger/10 border-danger/30 p-4">
            <Text className="text-xs font-sans-medium text-danger">{error || 'Candidate record not found.'}</Text>
          </Card>
        ) : (
          <View className="pb-8">
            {activeTab === 'overview' && renderOverviewTab()}
            {activeTab === 'timeline' && renderTimelineTab()}
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

      <Modal animationType="fade" transparent={true} visible={reprocessModalVisible} onRequestClose={() => setReprocessModalVisible(false)}>
        <View className="flex-1 justify-center items-center bg-black/60 px-4">
          <Card className="w-full max-w-md bg-surface p-4 border-border gap-3">
            <View className="flex-row items-center justify-between border-b border-border pb-2">
              <View className="flex-row items-center gap-2">
                <RefreshCw size={16} color={COLORS.primary} />
                <Text className="text-sm font-sans-bold text-text-primary">Re-run CV Analysis</Text>
              </View>
              <Pressable onPress={() => setReprocessModalVisible(false)}>
                <X size={16} color={COLORS.textMuted} />
              </Pressable>
            </View>
            <Text className="text-xs font-sans text-text-primary leading-5">
              Are you sure you want to re-run analysis for <Text className="font-sans-bold">{data?.filename || scanId}</Text>?
            </Text>
            <View className="bg-warning/10 p-2.5 rounded-md border border-warning/30">
              <Text className="text-[11px] font-sans text-warning leading-4">
                ⚠️ This purges all cached results (Resume JSON, LLM reasoning, embeddings, match rankings) and restarts the pipeline.
              </Text>
            </View>
            <View className="flex-row justify-end gap-2 mt-2">
              <Button label="Cancel" variant="ghost" size="sm" onPress={() => setReprocessModalVisible(false)} />
              <Button label="Confirm" variant="primary" size="sm" onPress={handleConfirmReprocess} />
            </View>
          </Card>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
