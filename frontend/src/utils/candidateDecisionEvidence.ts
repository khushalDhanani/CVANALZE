import type { CandidateRecommendationsResponse, CVUploadResponse, JobMatchScore } from '@/types/api';
import type { CandidateDetailViewModel } from '@/utils/candidateDetail';
import { cleanCandidateText, humanizeRecruiterText, resolveVacancyFitScore } from '@/utils/candidateDetail';

type UnknownRecord = Record<string, unknown>;

export interface CandidateSkillsEvidence {
  score?: number;
  matched: string[];
  missingRequired: string[];
  additional: string[];
}

export interface EducationDecisionEvidence {
  status: 'MATCHED' | 'CONFLICT' | 'REVIEW';
  requirement?: string;
  candidateEvidence?: string;
  explanation?: string;
}

export interface CandidateDecisionEvidence {
  skills: CandidateSkillsEvidence;
  education?: EducationDecisionEvidence;
  strengths: string[];
  concerns: string[];
}

export interface CandidateSkillsSummaryPresentation {
  scoreLabel?: string;
  matchedLabel?: string;
  missingLabel?: string;
}

export interface VacancyDecisionEvidence {
  overallFit?: number;
  skillsFit?: number;
  experienceFit?: number;
  educationFit?: number;
  whyItFits?: string;
  mainGap?: string;
}

const isRecord = (value: unknown): value is UnknownRecord => Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const asPercent = (value: unknown): number | undefined => {
  if (value == null || value === '') return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return undefined;
  return Math.max(0, Math.min(100, parsed <= 1 ? parsed * 100 : parsed));
};

const uniqueText = (values: unknown[]): string[] => {
  const seen = new Set<string>();
  return values.map(cleanCandidateText).filter((value): value is string => {
    if (!value) return false;
    const key = value.toLocaleLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const uniqueRecruiterText = (values: unknown[]): string[] => {
  const seen = new Set<string>();
  return values.map(humanizeRecruiterText).filter((value): value is string => {
    if (!value) return false;
    const key = value.toLocaleLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const getRequirements = (match: UnknownRecord): UnknownRecord[] => ['mandatory_requirements', 'preferred_requirements', 'optional_requirements'].flatMap((key) => {
  const requirements = match[key];
  return Array.isArray(requirements) ? requirements.filter(isRecord) : [];
});

const getRequirementEvidence = (requirement: UnknownRecord, key: 'cv_evidence' | 'vacancy_evidence'): string | undefined => {
  const evidence = requirement.evidence;
  return isRecord(evidence) ? humanizeRecruiterText(evidence[key]) : undefined;
};

const findEducationEvidence = (match: UnknownRecord): EducationDecisionEvidence | undefined => {
  const educationRequirement = getRequirements(match).find((requirement) => {
    const requirementId = cleanCandidateText(requirement.requirement_id)?.toLowerCase() || '';
    const description = cleanCandidateText(requirement.description)?.toLowerCase() || '';
    return requirementId.includes('education') || description.includes('education') || description.includes('degree');
  });
  if (!educationRequirement) return undefined;

  const status = cleanCandidateText(educationRequirement.status)?.toUpperCase();
  const decisionStatus = status === 'SATISFIED' ? 'MATCHED' : status === 'FAILED' || status === 'PARTIALLY_SATISFIED' ? 'CONFLICT' : 'REVIEW';
  return {
    status: decisionStatus,
    requirement: getRequirementEvidence(educationRequirement, 'vacancy_evidence') || humanizeRecruiterText(educationRequirement.description),
    candidateEvidence: getRequirementEvidence(educationRequirement, 'cv_evidence'),
    explanation: humanizeRecruiterText(educationRequirement.failure_reason),
  };
};

const getMatchSkills = (match: UnknownRecord, status: 'matched' | 'missing'): string[] => {
  const directValues = status === 'matched' ? match.matched_skills : match.missing_skills;
  const expectedStatuses = status === 'matched' ? new Set(['SATISFIED']) : new Set(['FAILED', 'PARTIALLY_SATISFIED', 'UNVERIFIED']);
  const requirementValues = getRequirements(match).flatMap((requirement) => {
    const requirementId = cleanCandidateText(requirement.requirement_id)?.toLowerCase() || '';
    const requirementStatus = cleanCandidateText(requirement.status)?.toUpperCase() || '';
    if (!requirementId.includes('skill') || !expectedStatuses.has(requirementStatus)) return [];
    const description = cleanCandidateText(requirement.description)?.replace(/^skill\s*:\s*/i, '');
    return description ? [description] : [];
  });
  return uniqueText([...(Array.isArray(directValues) ? directValues : []), ...requirementValues]);
};

const buildConcerns = (data: CVUploadResponse, match: UnknownRecord, recommendations?: CandidateRecommendationsResponse | null): string[] => {
  const mandatoryFailures = Array.isArray(match.mandatory_failures) ? match.mandatory_failures.filter(isRecord) : [];
  const severityRank: Record<string, number> = { CRITICAL: 5, HIGH: 4, MEDIUM: 3, LOW: 2, UNKNOWN: 1 };
  const hiringRisks = (Array.isArray(match.hiring_risks) ? match.hiring_risks.filter(isRecord) : [])
    .sort((left, right) => (severityRank[cleanCandidateText(right.severity)?.toUpperCase() || 'UNKNOWN'] || 0) - (severityRank[cleanCandidateText(left.severity)?.toUpperCase() || 'UNKNOWN'] || 0));
  const gapAnalysis = isRecord(data.experience_gap_analysis) ? data.experience_gap_analysis : {};
  const values = [
    ...mandatoryFailures.map((failure) => humanizeRecruiterText(failure.reason) || humanizeRecruiterText(failure.description)),
    ...getRequirements(match)
      .filter((requirement) => ['FAILED', 'PARTIALLY_SATISFIED'].includes(cleanCandidateText(requirement.status)?.toUpperCase() || ''))
      .map((requirement) => humanizeRecruiterText(requirement.failure_reason) || humanizeRecruiterText(requirement.description)),
    ...hiringRisks.map((risk) => humanizeRecruiterText(risk.title) || humanizeRecruiterText(risk.explanation)),
    ...(recommendations?.missing_qualifications || []).map((qualification) => humanizeRecruiterText(qualification.requirement) || humanizeRecruiterText(qualification.impact)),
    ...(recommendations?.risk_flags || []).map(humanizeRecruiterText),
    ...(Array.isArray(gapAnalysis.hr_review_indicators) ? gapAnalysis.hr_review_indicators.map(humanizeRecruiterText) : []),
  ];
  return uniqueRecruiterText(values).slice(0, 4);
};

export const buildCandidateSkillsSummaryPresentation = (skills: CandidateSkillsEvidence): CandidateSkillsSummaryPresentation => {
  const requiredCount = skills.matched.length + skills.missingRequired.length;
  return {
    scoreLabel: skills.score != null ? `${Math.round(skills.score)}% Skills Match` : undefined,
    matchedLabel: requiredCount > 0 ? `${skills.matched.length} Matched` : undefined,
    missingLabel: requiredCount > 0 ? `${skills.missingRequired.length} Missing` : undefined,
  };
};

export const buildCandidateDecisionEvidence = (
  data: CVUploadResponse,
  candidate: CandidateDetailViewModel,
  rawAnalysis: unknown,
  recommendations?: CandidateRecommendationsResponse | null,
): CandidateDecisionEvidence => {
  const analysis = isRecord(rawAnalysis) ? rawAnalysis : {};
  const match = isRecord(analysis.best_match) ? analysis.best_match : {};
  const scoreBreakdown = isRecord(match.score_breakdown) ? match.score_breakdown : {};
  const matched = getMatchSkills(match, 'matched');
  const missingRequired = getMatchSkills(match, 'missing');
  const matchedCriteria = uniqueRecruiterText(Array.isArray(match.matched_criteria) ? match.matched_criteria : []);
  const comparedSkills = new Set([...matched, ...missingRequired].map((skill) => skill.toLocaleLowerCase()));
  const additional = uniqueText(candidate.skills).filter((skill) => !comparedSkills.has(skill.toLocaleLowerCase()));
  const factualStrengths = [
    candidate.certifications.length ? `Recorded certifications: ${candidate.certifications.slice(0, 3).join(', ')}.` : undefined,
    matchedCriteria.length ? `Other matched evidence: ${matchedCriteria.slice(0, 3).join(', ')}.` : undefined,
  ];
  const strengths = uniqueText(factualStrengths).slice(0, 4);

  return {
    skills: {
      score: asPercent(match.skills_score ?? scoreBreakdown.skills_score),
      matched,
      missingRequired,
      additional,
    },
    education: findEducationEvidence(match),
    strengths,
    concerns: buildConcerns(data, match, recommendations),
  };
};

export const buildVacancyDecisionEvidence = (rawMatch: JobMatchScore | UnknownRecord): VacancyDecisionEvidence => {
  const match = isRecord(rawMatch) ? rawMatch : {};
  const breakdown = isRecord(match.score_breakdown) ? match.score_breakdown : {};
  const mandatoryFailures = Array.isArray(match.mandatory_failures) ? match.mandatory_failures.filter(isRecord) : [];
  const missingSkills = uniqueText(Array.isArray(match.missing_skills) ? match.missing_skills : []);
  const matchedSkills = uniqueText(Array.isArray(match.matched_skills) ? match.matched_skills : []);
  const missingCriteria = uniqueRecruiterText(Array.isArray(match.missing_criteria) ? match.missing_criteria : []);
  const matchedCriteria = uniqueRecruiterText(Array.isArray(match.matched_criteria) ? match.matched_criteria : []);
  const failedRequirement = getRequirements(match).find((requirement) => ['FAILED', 'PARTIALLY_SATISFIED'].includes(cleanCandidateText(requirement.status)?.toUpperCase() || ''));
  const mainGap = mandatoryFailures
    .map((failure) => humanizeRecruiterText(failure.reason) || humanizeRecruiterText(failure.description))
    .find(Boolean)
    || (failedRequirement ? humanizeRecruiterText(failedRequirement.failure_reason) || humanizeRecruiterText(failedRequirement.description) : undefined)
    || humanizeRecruiterText(match.domain_mismatch_reason)
    || (missingSkills.length ? `Missing required skills: ${missingSkills.slice(0, 3).join(', ')}.` : undefined)
    || missingCriteria[0];
  const whyItFits = matchedCriteria.length
    ? `Matched evidence: ${matchedCriteria.slice(0, 3).join(', ')}.`
    : matchedSkills.length
      ? `Matched required skills: ${matchedSkills.slice(0, 4).join(', ')}.`
      : undefined;

  return {
    overallFit: asPercent(resolveVacancyFitScore(match)),
    skillsFit: asPercent(match.skills_score ?? breakdown.skills_score),
    experienceFit: asPercent(match.experience_score ?? breakdown.experience_score),
    educationFit: asPercent(match.education_score ?? breakdown.education_score),
    whyItFits,
    mainGap,
  };
};
