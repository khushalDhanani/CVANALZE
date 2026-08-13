import type { DualEvidence, EnrichedJobEvaluation } from '@/types/api';

export interface VacancyEvidencePresentation {
  requirementId: string;
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

export function getVacancyEnrichmentPresentation(match: Partial<EnrichedJobEvaluation>): VacancyEnrichmentPresentation {
  const inferredSkills = Array.isArray(match.inferred_skills) ? match.inferred_skills.filter((skill) => cleanText(skill)) : [];
  const qualityFlags = Array.isArray(match.quality_flags) ? match.quality_flags.filter((flag) => cleanText(flag)) : [];
  const evidence = Object.entries(match.llm_evidence_snippets || {})
    .filter(([, item]) => item?.cv_evidence || item?.vacancy_evidence)
    .map(([requirementId, item]) => ({ requirementId, evidence: item }));
  const provenance = Object.entries(match.retrieval_provenance || {})
    .filter(([, value]) => typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean')
    .slice(0, 4)
    .map(([key, value]) => `${key.replaceAll('_', ' ')} ${String(value)}`);
  const confidence = typeof match.calibrated_confidence === 'number'
    ? `Calibrated confidence ${Math.round(match.calibrated_confidence * 100)}%`
    : typeof match.confidence === 'number'
      ? `Match confidence ${Math.round(match.confidence * 100)}%`
      : '';
  const metadata = [
    confidence,
    cleanText(match.calibration_version) ? `Calibration ${match.calibration_version}` : '',
    cleanText(match.retrieval_source) ? `Retrieved via ${match.retrieval_source}` : '',
    typeof match.vector_score === 'number' ? `Vector ${Math.round(match.vector_score * 100)}%` : '',
    typeof match.semantic_score_boost === 'number' ? `Semantic boost ${match.semantic_score_boost}` : '',
    cleanText(match.llm_model_used) ? `Model ${match.llm_model_used}` : '',
    match.llm_classified_requirements?.length ? `${match.llm_classified_requirements.length} grounded requirements` : '',
    ...provenance,
  ].filter(Boolean);

  return {
    reasoning: cleanText(match.llm_reason) || cleanText(match.semantic_reason),
    recommendation: cleanText(match.recommendation),
    inferredSkills,
    qualityFlags,
    evidence,
    metadata,
  };
}
