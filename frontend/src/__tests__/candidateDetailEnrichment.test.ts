import { normalizeCandidateMatchAnalysis } from '../utils/candidateDetail';
import { getVacancyEnrichmentPresentation } from '../utils/vacancyEnrichment';
import type { EnrichedJobEvaluation } from '../types/api';

function assertEquals(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

function assertSame(actual: unknown, expected: unknown): void {
  if (actual !== expected) throw new Error('Expected normalization to preserve the original enriched vacancy object.');
}

const manualReviewOpening = {
  vacancy_id: 10,
  job_id: '10',
  job_title: 'Laboratory Analyst',
  score: 45,
  vacancy_match_status: 'POTENTIAL_MATCH',
  classification: 'MEDIUM',
  recommendation: 'Proceed with structured HR review.',
  llm_reason: 'Relevant skill overlap...',
  inferred_skills: ['HPLC'],
  calibrated_confidence: 0.72,
  calibration_version: 'calibration-2',
  quality_flags: ['LIMITED_EVIDENCE'],
  retrieval_provenance: { vector_rank: 2 },
  llm_classified_requirements: [{ requirement_id: 'chemistry', description: 'Chemistry education', tier: 'MANDATORY', status: 'SATISFIED' }],
  llm_evidence_snippets: { chemistry: { cv_evidence: 'BSc Chemistry', vacancy_evidence: 'Chemistry degree required' } },
};

const normalized = normalizeCandidateMatchAnalysis({
  match_status: 'POTENTIAL_MATCH',
  has_genuine_match: false,
  best_match: manualReviewOpening,
  suitable_openings: [],
  unsuitable_openings: [manualReviewOpening],
});
const normalizedManualReview = (normalized?.unsuitable_openings as typeof manualReviewOpening[])[0];

assertEquals(normalized?.match_status, 'POTENTIAL_MATCH');
assertEquals(normalized?.has_genuine_match, false);
assertSame(normalized?.best_match, manualReviewOpening);
assertSame(normalizedManualReview, manualReviewOpening);
assertEquals(normalizedManualReview.llm_reason, manualReviewOpening.llm_reason);
assertEquals(normalizedManualReview.inferred_skills, manualReviewOpening.inferred_skills);
assertEquals(normalizedManualReview.recommendation, manualReviewOpening.recommendation);
assertEquals(normalizedManualReview.calibrated_confidence, manualReviewOpening.calibrated_confidence);
assertEquals(normalizedManualReview.llm_evidence_snippets, manualReviewOpening.llm_evidence_snippets);

const cardPresentation = getVacancyEnrichmentPresentation(normalizedManualReview as Partial<EnrichedJobEvaluation>);
assertEquals(cardPresentation.reasoning, manualReviewOpening.llm_reason);
assertEquals(cardPresentation.recommendation, manualReviewOpening.recommendation);
assertEquals(cardPresentation.inferredSkills, manualReviewOpening.inferred_skills);
assertEquals(cardPresentation.evidence[0].evidence, manualReviewOpening.llm_evidence_snippets.chemistry);
assertEquals(cardPresentation.metadata.includes('Calibrated confidence 72%'), true);
assertEquals(cardPresentation.metadata.includes('vector rank 2'), true);

const suitableOpening = { ...manualReviewOpening, vacancy_id: 11, job_id: '11', vacancy_match_status: 'MATCHED', classification: 'HIGH' };
const normalizedSuitable = normalizeCandidateMatchAnalysis({
  match_status: 'MATCHED',
  has_genuine_match: true,
  best_match: suitableOpening,
  suitable_openings: [suitableOpening],
  unsuitable_openings: [],
});

assertSame((normalizedSuitable?.suitable_openings as typeof suitableOpening[])[0], suitableOpening);
assertEquals(((normalizedSuitable?.suitable_openings as typeof suitableOpening[])[0]).llm_reason, suitableOpening.llm_reason);
