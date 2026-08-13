import type { DualEvidence, EnrichedJobEvaluation } from '@/types/api';
import { humanizeRecruiterText } from '@/utils/candidateDetail';

export const VACANCY_AI_EXPLANATION_LABEL = 'AI Match Explanation';
export const RELATED_SKILLS_LABEL = 'Related Skills Identified';

export interface VacancyEvidencePresentation {
  label: string;
  evidence: DualEvidence;
}

export interface VacancyEnrichmentPresentation {
  reasoning: string;
  recommendation: string;
  inferredSkills: string[];
  qualityFlags: string[];
  evidence: VacancyEvidencePresentation[];
  metadata: string[];
}

const cleanText = (value: unknown): string => typeof value === 'string' ? value.trim() : '';

const QUALITY_FLAG_LABELS: Record<string, string> = {
  LOW_CALIBRATED_CONFIDENCE: 'Match Confidence Needs Review',
  UNSUPPORTED_LLM_CLAIMS_REMOVED: 'Unsupported AI Claims Excluded',
  LLM_VACANCY_EVALUATION_MISSING: 'AI Vacancy Review Unavailable',
};

export function getVacancyEnrichmentPresentation(match: Partial<EnrichedJobEvaluation>): VacancyEnrichmentPresentation {
  const inferredSkills = Array.isArray(match.inferred_skills) ? match.inferred_skills.filter((skill) => cleanText(skill)) : [];
  const qualityFlags = Array.isArray(match.quality_flags)
    ? match.quality_flags.map((flag) => QUALITY_FLAG_LABELS[cleanText(flag)]).filter((flag): flag is string => Boolean(flag))
    : [];
  const requirementLabels = new Map((match.llm_classified_requirements || []).map((item) => [item.requirement_id, cleanText(item.description)]));
  const evidence = Object.entries(match.llm_evidence_snippets || {})
    .filter(([, item]) => item?.cv_evidence || item?.vacancy_evidence)
    .map(([requirementId, item], index) => ({ label: requirementLabels.get(requirementId) || `Requirement ${index + 1}`, evidence: item }));
  const initialScreeningRank = Number(match.retrieval_provenance?.prefilter_rank);
  const confidence = typeof match.calibrated_confidence === 'number'
    ? `Match Confidence ${Math.round(match.calibrated_confidence * 100)}%`
    : typeof match.confidence === 'number'
      ? `Match Confidence ${Math.round(match.confidence * 100)}%`
      : '';
  const metadata = [
    confidence,
    match.llm_classified_requirements?.length ? `${match.llm_classified_requirements.length} grounded requirements` : '',
    Number.isInteger(initialScreeningRank) && initialScreeningRank > 0 ? `Ranked #${initialScreeningRank} During Initial Screening` : '',
  ].filter(Boolean);

  return {
    reasoning: humanizeRecruiterText(match.llm_reason) || humanizeRecruiterText(match.semantic_reason) || '',
    recommendation: humanizeRecruiterText(match.recommendation) || '',
    inferredSkills,
    qualityFlags,
    evidence,
    metadata,
  };
}
