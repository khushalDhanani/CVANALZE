import { buildCandidateDecisionNarratives, buildCandidateDetailViewModel, buildCandidateFiveSecondSummary, humanizeRecruiterText, normalizeCandidateMatchAnalysis } from '../utils/candidateDetail';
import { buildCandidateDecisionEvidence, buildCandidateSkillsSummaryPresentation, buildVacancyDecisionEvidence } from '../utils/candidateDecisionEvidence';
import { getVacancyEnrichmentPresentation, RELATED_SKILLS_LABEL, VACANCY_AI_EXPLANATION_LABEL } from '../utils/vacancyEnrichment';
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
  ai_match_explanation: 'Their HPLC experience directly supports the vacancy requirement. The rating remains limited because the resume does not quantify laboratory ownership.',
  inferred_skills: ['HPLC'],
  calibrated_confidence: 0.72,
  calibration_version: 'calibration-2',
  scoring_profile_code: 'baseline-identity-1.0.0',
  rrf_score: 0.8123,
  stage0_compatible: true,
  retrieval_path: 'taxonomy_vector_hybrid',
  quality_flags: ['LIMITED_EVIDENCE'],
  retrieval_provenance: { vector_rank: 2 },
  llm_classified_requirements: [{ requirement_id: 'chemistry', description: 'Chemistry education', tier: 'MANDATORY', status: 'SATISFIED' }],
  llm_evidence_snippets: { chemistry: { cv_evidence: 'BSc Chemistry', vacancy_evidence: 'Chemistry degree required' } },
  llm_requirement_assessments: [{
    requirement_id: 'chemistry',
    requirement: 'Chemistry degree required',
    category: 'EDUCATION',
    mandatory: true,
    cv_evidence: 'BSc Chemistry',
    jd_evidence: 'Chemistry degree required',
    rationale: 'The degree directly satisfies the education requirement.',
    match_type: 'DIRECT' as const,
    confidence: 0.96,
    impact: 'LOW' as const,
  }],
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
assertEquals(normalizedManualReview.llm_requirement_assessments, manualReviewOpening.llm_requirement_assessments);

const cardPresentation = getVacancyEnrichmentPresentation(normalizedManualReview as Partial<EnrichedJobEvaluation>);
assertEquals(cardPresentation.reasoning, manualReviewOpening.ai_match_explanation);
assertEquals(cardPresentation.recommendation, manualReviewOpening.recommendation);
assertEquals(cardPresentation.inferredSkills, manualReviewOpening.inferred_skills);
assertEquals(cardPresentation.evidence[0].evidence, manualReviewOpening.llm_evidence_snippets.chemistry);
assertEquals(cardPresentation.evidence[0].label, 'Chemistry degree required');
assertEquals(cardPresentation.evidence[0].assessment?.match_type, 'DIRECT');
assertEquals(cardPresentation.evidence[0].assessment?.mandatory, true);
assertEquals(cardPresentation.evidence[0].assessment?.confidence, 0.96);
assertEquals(cardPresentation.evidence[0].assessment?.impact, 'LOW');
assertEquals(cardPresentation.metadata.includes('Match Confidence 72%'), true);
assertEquals(cardPresentation.metadata.some((item) => item.includes('Calibration') || item.includes('vector rank')), false);
assertEquals(VACANCY_AI_EXPLANATION_LABEL, 'AI Match Explanation');
assertEquals(RELATED_SKILLS_LABEL, 'Related Skills Identified');
const normalRecruiterPresentation = JSON.stringify(cardPresentation);
['baseline-identity-1.0.0', 'rrf_score', 'stage0', 'retrieval_path', 'taxonomy_vector_hybrid'].forEach((technicalValue) => {
  assertEquals(normalRecruiterPresentation.includes(technicalValue), false);
});

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

const summaryAnalysis = {
  match_status: 'POTENTIAL_MATCH',
  professional_domain: null,
  best_match: {
    vacancy_fit_score: 50.3,
    vacancy_match_status: 'POTENTIAL_MATCH',
    skills_score: 100,
    matched_skills: ['Maintenance Work'],
    missing_skills: [],
    candidate_job_family: 'Production Team',
    calibrated_confidence: 0.35,
    hr_review_required: true,
    reason: 'Potential vacancy fit requires HR review.',
    preferred_requirements: [{
      requirement_id: 'req_education',
      description: 'Education Mismatch: SSC',
      status: 'FAILED',
      failure_reason: "Candidate's documented education does not satisfy vacancy requirement 'SSC'.",
    }],
  },
};
const summary = buildCandidateFiveSecondSummary(
  { scan_id: 'candidate-1', filename: 'candidate.pdf', parsed_at: '2026-08-13', markdown: '', gross_display: '0 years 0 months' },
  { name: 'Divyesh Patel', experience: [], education: [], certifications: [], skills: [], projects: [] },
  summaryAnalysis,
);
assertEquals(summary.recommendation, 'POTENTIAL MATCH');
assertEquals(summary.overallFit, 50.3);
assertEquals(summary.skillsFit, 100);
assertEquals([summary.matchedSkillsCount, summary.requiredSkillsCount], [1, 1]);
assertEquals(summary.domain, 'Production Team');
assertEquals(summary.matchConfidence, 35);
assertEquals(summary.mainConcern, "Candidate's documented education does not satisfy vacancy requirement 'SSC'.");
assertEquals(summary.totalExperience, undefined);

const detailedNarratives = buildCandidateDecisionNarratives(
  { scan_id: 'candidate-1', filename: 'candidate.pdf', parsed_at: '2026-08-13', markdown: '' },
  { name: 'Divyesh Patel', experience: [], education: [], certifications: [], skills: ['Maintenance Work', 'SAP'], projects: [] },
  summaryAnalysis,
);
assertEquals(detailedNarratives.topStrength.includes('Maintenance Work'), true);
assertEquals(detailedNarratives.mainConcern.includes("vacancy requirement 'SSC'"), true);
assertEquals(detailedNarratives.aiMatchExplanation.includes('50%'), true);
Object.values(detailedNarratives).forEach((narrative) => {
  assertEquals((narrative.match(/[.!?](?=\s|$)/g) || []).length >= 2, true);
  assertEquals((narrative.match(/\bCV\b/g) || []).length <= 1, true);
});

const decisionEvidence = buildCandidateDecisionEvidence(
  { scan_id: 'candidate-1', filename: 'candidate.pdf', parsed_at: '2026-08-13', markdown: '' },
  { name: 'Divyesh Patel', experience: [], education: [], certifications: [], skills: ['Maintenance Work', 'SAP', 'Fire Safety'], projects: [] },
  summaryAnalysis,
);
assertEquals(decisionEvidence.skills.score, 100);
assertEquals(decisionEvidence.skills.matched, ['Maintenance Work']);
assertEquals(decisionEvidence.skills.missingRequired, []);
assertEquals(decisionEvidence.skills.additional, ['SAP', 'Fire Safety']);
assertEquals(decisionEvidence.education?.status, 'CONFLICT');
assertEquals(decisionEvidence.education?.requirement, 'Education Mismatch: SSC');

const phaseThreeMatchedSkills = ['React', 'TypeScript', 'REST APIs', 'Git', 'Testing', 'HTML', 'CSS', 'SQL'];
const phaseThreeMissingSkills = ['Redux', 'AWS'];
const phaseThreeAnalysis = {
  professional_domain: 'Software Engineering',
  recommended_department: 'Product Engineering',
  best_match: {
    vacancy_fit_score: 78,
    vacancy_match_status: 'POTENTIAL_MATCH',
    skills_score: 80,
    matched_skills: phaseThreeMatchedSkills,
    missing_skills: phaseThreeMissingSkills,
    calibrated_confidence: 0.74,
    hiring_risks: [{ severity: 'MEDIUM', title: 'Limited leadership evidence' }],
  },
};
const phaseThreeCandidate = {
  name: 'Dinesh Patil',
  jobTitle: 'Production Engineer',
  company: 'ABC Industries',
  experience: [],
  education: [],
  certifications: [],
  skills: [...phaseThreeMatchedSkills, 'Next.js'],
  projects: [],
};
const phaseThreeData = {
  scan_id: 'candidate-phase-3',
  filename: 'candidate.pdf',
  parsed_at: '2026-08-13',
  markdown: '',
  gross_display: '7.5 Years',
  dynamic_profile: { relevant_experience_years: 6.5 },
};
const phaseThreeSummary = buildCandidateFiveSecondSummary(phaseThreeData, phaseThreeCandidate, phaseThreeAnalysis);
assertEquals([
  phaseThreeSummary.name,
  phaseThreeSummary.role,
  phaseThreeSummary.company,
  phaseThreeSummary.totalExperience,
  phaseThreeSummary.relevantExperience,
  phaseThreeSummary.overallFit,
  phaseThreeSummary.skillsFit,
  phaseThreeSummary.domain,
  phaseThreeSummary.recommendation,
  phaseThreeSummary.mainConcern,
], ['Dinesh Patil', 'Production Engineer', 'ABC Industries', '7.5 Years', '6.5 Years', 78, 80, 'Software Engineering', 'POTENTIAL MATCH', 'Limited leadership evidence']);

const phaseThreeEvidence = buildCandidateDecisionEvidence(phaseThreeData, phaseThreeCandidate, phaseThreeAnalysis);
const phaseThreeSkills = buildCandidateSkillsSummaryPresentation(phaseThreeEvidence.skills);
assertEquals(phaseThreeSkills, { scoreLabel: '80% Skills Match', matchedLabel: '8 Matched', missingLabel: '2 Missing' });

const missingDataCandidate = { name: 'Candidate Profile', experience: [], education: [], certifications: [], skills: [], projects: [] };
const missingDataSummary = buildCandidateFiveSecondSummary(
  { scan_id: 'candidate-missing', filename: 'candidate.pdf', parsed_at: '2026-08-13', markdown: '', gross_display: '0 years 0 months' },
  missingDataCandidate,
  {},
);
assertEquals([
  missingDataSummary.totalExperience,
  missingDataSummary.relevantExperience,
  missingDataSummary.overallFit,
  missingDataSummary.skillsFit,
  missingDataSummary.requiredSkillsCount,
  missingDataSummary.domain,
], [undefined, undefined, undefined, undefined, undefined, undefined]);
assertEquals(missingDataSummary.recommendation, 'MANUAL REVIEW');
assertEquals(missingDataSummary.mainConcern, 'Match analysis is not available for this candidate.');
const missingDataEvidence = buildCandidateDecisionEvidence(
  { scan_id: 'candidate-missing', filename: 'candidate.pdf', parsed_at: '2026-08-13', markdown: '', gross_display: '0 years 0 months' },
  missingDataCandidate,
  {},
);
assertEquals(missingDataEvidence.skills, { score: undefined, matched: [], missingRequired: [], additional: [] });
assertEquals(missingDataEvidence.education, undefined);
assertEquals(missingDataEvidence.strengths, []);
assertEquals(buildCandidateSkillsSummaryPresentation(missingDataEvidence.skills), {});

assertEquals(humanizeRecruiterText('mandatory_failure'), 'Mandatory Requirement Gap');
assertEquals(humanizeRecruiterText('domain_alignment'), 'Domain Match');
assertEquals(humanizeRecruiterText('cross_domain_guard'), 'Role/Domain Conflict');
assertEquals(humanizeRecruiterText('experience_gap'), 'Experience Gap');
assertEquals(humanizeRecruiterText('education_conflict'), 'Education Concern');

const semanticPotentialOpening = {
  ...manualReviewOpening,
  vacancy_id: 12,
  job_id: '12',
  llm_reason: undefined,
  ai_match_explanation: undefined,
  semantic_reason: 'Potential fit retained for manual review.',
  vacancy_match_status: 'POTENTIAL_MATCH',
};
const normalizedSemanticPotential = normalizeCandidateMatchAnalysis({
  match_status: 'POTENTIAL_MATCH',
  best_match: semanticPotentialOpening,
  suitable_openings: [],
  unsuitable_openings: [semanticPotentialOpening],
});
const semanticPotential = (normalizedSemanticPotential?.unsuitable_openings as typeof semanticPotentialOpening[])[0];
assertSame(semanticPotential, semanticPotentialOpening);
assertEquals(getVacancyEnrichmentPresentation(semanticPotential as Partial<EnrichedJobEvaluation>).reasoning, 'Potential fit retained for manual review.');

const explicitManualReviewOpening = {
  ...manualReviewOpening,
  vacancy_id: 13,
  job_id: '13',
  vacancy_match_status: 'MANUAL_REVIEW',
  llm_reason: 'AI explanation retained for explicit manual review.',
  ai_match_explanation: undefined,
};
const normalizedExplicitManualReview = normalizeCandidateMatchAnalysis({
  match_status: 'MANUAL_REVIEW',
  best_match: explicitManualReviewOpening,
  suitable_openings: [],
  unsuitable_openings: [explicitManualReviewOpening],
});
const explicitManualReview = (normalizedExplicitManualReview?.unsuitable_openings as typeof explicitManualReviewOpening[])[0];
assertSame(explicitManualReview, explicitManualReviewOpening);
assertEquals(getVacancyEnrichmentPresentation(explicitManualReview as Partial<EnrichedJobEvaluation>).reasoning, 'AI explanation retained for explicit manual review.');

const vacancyEvidence = buildVacancyDecisionEvidence({
  vacancy_fit_score: 78,
  skills_score: 82,
  experience_score: 75,
  education_score: 100,
  matched_criteria: ['Organic chemistry', 'Laboratory safety'],
  missing_skills: ['Industrial HPLC'],
});
assertEquals([vacancyEvidence.overallFit, vacancyEvidence.skillsFit, vacancyEvidence.experienceFit, vacancyEvidence.educationFit], [78, 82, 75, 100]);
assertEquals(vacancyEvidence.whyItFits, 'Matched evidence: Organic chemistry, Laboratory safety.');
assertEquals(vacancyEvidence.mainGap, 'Missing required skills: Industrial HPLC.');

const multiDegreeView = buildCandidateDetailViewModel({
  scan_id: 'candidate-education',
  filename: 'candidate.pdf',
  parsed_at: '2026-08-13',
  markdown: '',
  education: [
    { degree: 'M.Sc. Organic Chemistry', institution: 'Example University', start_date: '2025', is_current: true },
    { degree: 'B.Sc. Chemistry', institution: 'Example University', start_date: '2020', end_date: '2023' },
  ],
});
assertEquals(multiDegreeView.education.length, 2);
assertEquals(multiDegreeView.education.map((item) => item.dates), ['2025 – Present', '2020 – 2023']);
