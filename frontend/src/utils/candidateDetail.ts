import type { CandidateRecommendationsResponse, CVUploadResponse } from '@/types/api';

type UnknownRecord = Record<string, unknown>;

export interface CandidateExperienceView {
  title?: string;
  company?: string;
  dates?: string;
  responsibilities: string[];
}

export interface CandidateEducationView {
  degree?: string;
  institution?: string;
  dates?: string;
  grade?: string;
  details?: string;
}

export interface CandidateProjectView {
  name?: string;
  description?: string;
  technologies: string[];
  bulletPoints: string[];
}

export interface CandidateDetailViewModel {
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  linkedin?: string;
  github?: string;
  jobTitle?: string;
  company?: string;
  summary?: string;
  extractedText?: string;
  experience: CandidateExperienceView[];
  education: CandidateEducationView[];
  certifications: string[];
  skills: string[];
  projects: CandidateProjectView[];
}

export type CandidateSummaryRecommendation = 'STRONG MATCH' | 'POTENTIAL MATCH' | 'MANUAL REVIEW' | 'NO STRONG MATCH';

export interface CandidateFiveSecondSummary {
  name: string;
  role?: string;
  company?: string;
  totalExperience?: string;
  relevantExperience?: string;
  overallFit?: number;
  skillsFit?: number;
  matchedSkillsCount?: number;
  requiredSkillsCount?: number;
  domain?: string;
  department?: string;
  matchConfidence?: number;
  recommendation: CandidateSummaryRecommendation;
  mainConcern: string;
}

export interface CandidateDecisionNarratives {
  topStrength: string;
  mainConcern: string;
  aiMatchExplanation: string;
}

const isRecord = (value: unknown): value is UnknownRecord => Boolean(value) && typeof value === 'object' && !Array.isArray(value);

interface MatchScoreSource {
  vacancy_fit_score?: unknown;
  overall_score?: unknown;
  score?: unknown;
  score_breakdown?: unknown;
}

export const resolveVacancyFitScore = (match?: MatchScoreSource): number | undefined => {
  if (!match) return undefined;

  const fitScore = Number(match.vacancy_fit_score);
  const hasFitScore = match.vacancy_fit_score != null && Number.isFinite(fitScore);
  if (hasFitScore && (fitScore !== 0 || isRecord(match.score_breakdown))) return fitScore;

  for (const fallback of [match.overall_score, match.score]) {
    if (fallback == null) continue;
    const score = Number(fallback);
    if (Number.isFinite(score)) return score;
  }
  return hasFitScore ? fitScore : undefined;
};

export const normalizeCandidateMatchAnalysis = (value: unknown): UnknownRecord | undefined => {
  if (!isRecord(value)) return undefined;

  const suitableOpenings = Array.isArray(value.suitable_openings) ? value.suitable_openings.filter(isRecord) : [];
  const unsuitableOpenings = Array.isArray(value.unsuitable_openings) ? value.unsuitable_openings.filter(isRecord) : [];
  const rawBestMatch = isRecord(value.best_match) ? value.best_match : undefined;

  return {
    ...value,
    best_match: rawBestMatch ?? suitableOpenings[0] ?? null,
    suitable_openings: suitableOpenings,
    unsuitable_openings: unsuitableOpenings,
    has_genuine_match: typeof value.has_genuine_match === 'boolean' ? value.has_genuine_match : suitableOpenings.length > 0,
  };
};

const asFiniteNumber = (value: unknown): number | undefined => {
  if (value == null || value === '') return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const asPercent = (value: unknown): number | undefined => {
  const parsed = asFiniteNumber(value);
  if (parsed == null) return undefined;
  return Math.max(0, Math.min(100, parsed <= 1 ? parsed * 100 : parsed));
};

const formatYears = (value: unknown): string | undefined => {
  const years = asFiniteNumber(value);
  if (years == null) return undefined;
  return `${Math.round(years * 10) / 10} ${Math.abs(years - 1) < 0.001 ? 'Year' : 'Years'}`;
};

const normalizeRecommendation = (rawStatus: unknown, requiresReview: boolean): CandidateSummaryRecommendation => {
  const status = cleanCandidateText(rawStatus)?.toUpperCase().replaceAll('_', ' ');
  if (status && ['MATCHED', 'HIGH', 'STRONG', 'STRONG MATCH', 'HIGHLY RECOMMENDED', 'HIRE', 'DB MATCH'].includes(status)) return 'STRONG MATCH';
  if (status && ['POTENTIAL MATCH', 'PARTIAL MATCH', 'MEDIUM', 'POTENTIAL FIT', 'RECOMMENDED', 'CONSIDER'].includes(status)) return 'POTENTIAL MATCH';
  if (status && ['MANUAL REVIEW', 'NEEDS FURTHER REVIEW', 'HR REVIEW REQUIRED'].includes(status)) return 'MANUAL REVIEW';
  if (!status || requiresReview) return 'MANUAL REVIEW';
  return 'NO STRONG MATCH';
};

const resolveTotalExperience = (data: CVUploadResponse): string | undefined => {
  const experienceSummary = isRecord(data.experience_summary) ? data.experience_summary : {};
  const experienceState = cleanCandidateText(data.experience_state ?? experienceSummary.experience_state)?.toUpperCase();
  const grossDisplay = cleanCandidateText(data.gross_display);
  const numericYears = asFiniteNumber(data.total_experience_years ?? data.experience_years);
  const hasConfirmedZero = experienceState === 'ZERO_CONFIRMED';
  const grossIsZero = Boolean(grossDisplay && /^0(?:\.0+)?\s+years?(?:\s+0\s+months?)?$/i.test(grossDisplay));
  if ((grossIsZero || numericYears === 0) && !hasConfirmedZero) return undefined;
  return grossDisplay || formatYears(numericYears);
};

const collectRequirementSkills = (match: UnknownRecord, status: 'matched' | 'missing'): string[] => {
  const expectedStatuses = status === 'matched' ? new Set(['SATISFIED']) : new Set(['FAILED', 'PARTIALLY_SATISFIED', 'UNVERIFIED']);
  return ['mandatory_requirements', 'preferred_requirements', 'optional_requirements'].flatMap((key) => {
    const requirements = Array.isArray(match[key]) ? match[key] : [];
    return requirements.filter(isRecord).flatMap((requirement) => {
      const requirementId = cleanCandidateText(requirement.requirement_id)?.toLowerCase() || '';
      const requirementStatus = cleanCandidateText(requirement.status)?.toUpperCase() || '';
      if (!requirementId.includes('skill') || !expectedStatuses.has(requirementStatus)) return [];
      const description = cleanCandidateText(requirement.description)?.replace(/^skill\s*:\s*/i, '');
      return description ? [description] : [];
    });
  });
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

const findFailedRequirementConcern = (match: UnknownRecord): string | undefined => {
  for (const key of ['mandatory_requirements', 'preferred_requirements', 'optional_requirements']) {
    const requirements = Array.isArray(match[key]) ? match[key] : [];
    const failed = requirements.filter(isRecord).find((requirement) => ['FAILED', 'PARTIALLY_SATISFIED'].includes(cleanCandidateText(requirement.status)?.toUpperCase() || ''));
    if (!failed) continue;
    return humanizeRecruiterText(failed.failure_reason) || humanizeRecruiterText(failed.description);
  }
  return undefined;
};

const findMainConcern = (data: CVUploadResponse, analysis: UnknownRecord, match: UnknownRecord, recommendations?: CandidateRecommendationsResponse | null): string => {
  const mandatoryFailures = Array.isArray(match.mandatory_failures) ? match.mandatory_failures.filter(isRecord) : [];
  const mandatoryConcern = mandatoryFailures
    .map((failure) => humanizeRecruiterText(failure.reason) || humanizeRecruiterText(failure.description))
    .find(Boolean);
  if (mandatoryConcern) return mandatoryConcern;

  const failedRequirementConcern = findFailedRequirementConcern(match);
  if (failedRequirementConcern) return failedRequirementConcern;

  const severityRank: Record<string, number> = { CRITICAL: 5, HIGH: 4, MEDIUM: 3, LOW: 2, UNKNOWN: 1 };
  const hiringRisks = (Array.isArray(match.hiring_risks) ? match.hiring_risks.filter(isRecord) : [])
    .sort((left, right) => (severityRank[cleanCandidateText(right.severity)?.toUpperCase() || 'UNKNOWN'] || 0) - (severityRank[cleanCandidateText(left.severity)?.toUpperCase() || 'UNKNOWN'] || 0));
  const topRisk = hiringRisks[0];
  if (topRisk) {
    const riskConcern = humanizeRecruiterText(topRisk.explanation) || humanizeRecruiterText(topRisk.title);
    if (riskConcern) return riskConcern;
  }

  const missingQualification = recommendations?.missing_qualifications?.[0];
  if (missingQualification) return humanizeRecruiterText(missingQualification.requirement) || humanizeRecruiterText(missingQualification.impact) || 'A qualification requires recruiter review.';

  const recommendationRisk = recommendations?.risk_flags?.map(humanizeRecruiterText).find(Boolean);
  if (recommendationRisk) return recommendationRisk;

  const domainConcern = humanizeRecruiterText(match.domain_mismatch_reason);
  if (domainConcern) return domainConcern;

  const gapAnalysis = isRecord(data.experience_gap_analysis) ? data.experience_gap_analysis : isRecord(analysis.experience_gap_analysis) ? analysis.experience_gap_analysis : {};
  const gapIndicators = Array.isArray(gapAnalysis.hr_review_indicators) ? gapAnalysis.hr_review_indicators : [];
  const gapConcern = gapIndicators.map(humanizeRecruiterText).find(Boolean);
  if (gapConcern) return gapConcern;

  const missingSkills = uniqueText(Array.isArray(match.missing_skills) ? match.missing_skills : []);
  if (missingSkills.length) return `Missing required skills: ${missingSkills.slice(0, 3).join(', ')}${missingSkills.length > 3 ? ` and ${missingSkills.length - 3} more` : ''}.`;

  const qualityFlags = Array.isArray(match.quality_flags) ? match.quality_flags.map(cleanCandidateText) : [];
  if (qualityFlags.includes('LOW_CALIBRATED_CONFIDENCE')) return 'Match evidence has low confidence and needs recruiter review.';

  if (Object.keys(match).length === 0) return 'Match analysis is not available for this candidate.';

  return 'No major concern identified in the current analysis.';
};

const ensureDetailedNarrative = (primary: unknown, supportingSentence: string): string => {
  const text = humanizeRecruiterText(primary);
  if (!text) return supportingSentence;
  const normalized = /[.!?]$/.test(text) ? text : `${text}.`;
  const sentenceCount = normalized.match(/[.!?](?=\s|$)/g)?.length || 0;
  return sentenceCount >= 2 ? normalized : `${normalized} ${supportingSentence}`;
};

export const buildCandidateDecisionNarratives = (
  data: CVUploadResponse,
  candidate: CandidateDetailViewModel,
  rawAnalysis: unknown,
  recommendations?: CandidateRecommendationsResponse | null,
): CandidateDecisionNarratives => {
  const analysis = isRecord(rawAnalysis) ? rawAnalysis : {};
  const match = isRecord(analysis.best_match) ? analysis.best_match : {};
  const matchedSkills = uniqueText([
    ...(Array.isArray(match.matched_skills) ? match.matched_skills : []),
    ...collectRequirementSkills(match, 'matched'),
  ]);
  const missingSkills = uniqueText([
    ...(Array.isArray(match.missing_skills) ? match.missing_skills : []),
    ...collectRequirementSkills(match, 'missing'),
  ]);
  const vacancyTitle = firstCandidateText(match.job_title, match.title) || 'the selected vacancy';
  const score = resolveVacancyFitScore(match);
  const scoreLabel = score == null ? 'not available' : `${Math.round(score)}%`;
  const cvSkills = uniqueText(candidate.skills);
  const topEvidence = matchedSkills.length ? matchedSkills.slice(0, 3) : cvSkills.slice(0, 3);
  const matchedSkillsLabel = matchedSkills.slice(0, 3).join(', ');
  const missingSkillsLabel = missingSkills.slice(0, 3).join(', ');
  const matchedSkillNoun = `required skill match${matchedSkills.length === 1 ? '' : 'es'}`;
  const comparisonSentence = matchedSkills.length
    ? `Their background covers ${matchedSkills.length} ${matchedSkillNoun} for ${vacancyTitle}: ${matchedSkillsLabel}.`
    : 'No role requirement is linked to the candidate’s experience, so a recruiter needs the missing position details before identifying a strongest match.';
  const topStrengthFallback = topEvidence.length && matchedSkills.length
    ? `The candidate’s strongest match for ${vacancyTitle} is ${topEvidence.join(', ')}, supported by both their experience and the position requirements. ` + comparisonSentence
    : `The resume mentions ${topEvidence.length ? topEvidence.join(', ') : 'no specific skills, projects, achievements, or experience'}, `
      + `but the current assessment does not connect that background to a requirement for ${vacancyTitle}. `
      + 'A clear top strength cannot be determined until the missing candidate or role details are available.';

  const baseConcern = findMainConcern(data, analysis, match, recommendations);
  const missingSkillsRemainder = missingSkills.length > 3 ? ` and ${missingSkills.length - 3} more` : '';
  const concernSupport = missingSkills.length
    ? `Their profile does not show ${missingSkillsLabel}${missingSkillsRemainder}, so these role requirements should be tested during screening.`
    : `No specific required-skill gap is identified for ${vacancyTitle}; `
      + 'employment continuity and qualification fit still need review if the position details do not cover them.';
  const mainConcernFallback = `${/[.!?]$/.test(baseConcern) ? baseConcern : `${baseConcern}.`} ${concernSupport}`;

  const matchedRequirementNoun = `matched requirement${matchedSkills.length === 1 ? '' : 's'}`;
  const missingRequirementNoun = `missing requirement${missingSkills.length === 1 ? '' : 's'}`;
  const scoreEvidence = matchedSkills.length || missingSkills.length
    ? `The ${scoreLabel} rating reflects ${matchedSkills.length} ${matchedRequirementNoun}${matchedSkills.length ? ` (${matchedSkillsLabel})` : ''} `
      + `with ${missingSkills.length} ${missingRequirementNoun}${missingSkills.length ? ` (${missingSkillsLabel})` : ''} for ${vacancyTitle}.`
    : `A ${scoreLabel} rating is recorded for ${vacancyTitle}, but the assessment does not identify which position requirements are met or missing.`;
  const explanationSupport = 'Where candidate or role evidence is missing, the rating should be treated as incomplete '
    + 'rather than assuming the requirement is met.';

  return {
    topStrength: ensureDetailedNarrative(match.top_strength, topStrengthFallback),
    mainConcern: ensureDetailedNarrative(match.main_concern, mainConcernFallback),
    aiMatchExplanation: ensureDetailedNarrative(
      match.ai_match_explanation || match.llm_reason || match.semantic_reason,
      `${scoreEvidence} ${explanationSupport}`,
    ),
  };
};

export const buildCandidateFiveSecondSummary = (
  data: CVUploadResponse,
  candidate: CandidateDetailViewModel,
  rawAnalysis: unknown,
  recommendations?: CandidateRecommendationsResponse | null,
): CandidateFiveSecondSummary => {
  const analysis = isRecord(rawAnalysis) ? rawAnalysis : {};
  const match = isRecord(analysis.best_match) ? analysis.best_match : {};
  const dynamicProfile = isRecord(data.dynamic_profile) ? data.dynamic_profile : {};
  const classification = isRecord(analysis.classification) ? analysis.classification : {};
  const scoreBreakdown = isRecord(match.score_breakdown) ? match.score_breakdown : {};
  const matchedSkills = uniqueText([...(Array.isArray(match.matched_skills) ? match.matched_skills : []), ...collectRequirementSkills(match, 'matched')]);
  const missingSkills = uniqueText([...(Array.isArray(match.missing_skills) ? match.missing_skills : []), ...collectRequirementSkills(match, 'missing')]);
  const requiredSkills = uniqueText([...matchedSkills, ...missingSkills]);
  const totalExperience = resolveTotalExperience(data);
  const relevantExperience = formatYears(dynamicProfile.relevant_experience_years);
  const requiresReview = Boolean(match.hr_review_required) || (Array.isArray(match.mandatory_failures) && match.mandatory_failures.length > 0);
  const rawRecommendation = recommendations?.hiring_recommendation || match.vacancy_match_status || match.match_status || analysis.match_status;

  return {
    name: candidate.name || 'Candidate Profile',
    role: candidate.jobTitle || cleanCandidateText(dynamicProfile.current_role),
    company: candidate.company,
    totalExperience,
    relevantExperience,
    overallFit: asPercent(resolveVacancyFitScore(match)),
    skillsFit: asPercent(match.skills_score ?? scoreBreakdown.skills_score),
    matchedSkillsCount: requiredSkills.length ? matchedSkills.length : undefined,
    requiredSkillsCount: requiredSkills.length || undefined,
    domain: firstCandidateText(analysis.professional_domain, classification.industry_domain, match.candidate_job_family),
    department: firstCandidateText(analysis.recommended_department, analysis.primary_department, recommendations?.primary_department),
    matchConfidence: asPercent(match.calibrated_confidence ?? match.confidence),
    recommendation: normalizeRecommendation(rawRecommendation, requiresReview),
    mainConcern: findMainConcern(data, analysis, match, recommendations),
  };
};

const decodeEntities = (value: string): string => value
  .replace(/&amp;/gi, '&')
  .replace(/&lt;/gi, '<')
  .replace(/&gt;/gi, '>')
  .replace(/&quot;/gi, '"')
  .replace(/&#39;|&apos;/gi, "'");

export const cleanCandidateText = (value: unknown): string | undefined => {
  if (isRecord(value)) {
    return cleanCandidateText(value.normalized_value ?? value.raw_value ?? value.value);
  }
  if (typeof value !== 'string' && typeof value !== 'number') return undefined;
  const cleaned = decodeEntities(String(value)).trim();
  if (!cleaned || /^(?:null|undefined|n\/a|none|unknown(?: candidate)?|not specified|position|-+)$/i.test(cleaned)) return undefined;
  return cleaned;
};

export const cleanRecommendationText = (value: unknown): string | undefined => {
  const cleaned = cleanCandidateText(value);
  if (!cleaned) return undefined;
  const displayText = cleaned
    .replace(/[\u2022\u2023\u2043\u2219\u25aa-\u25ab\u25a0-\u25a4\uf0b7]/g, ' ')
    .replace(/\bamp;?\b/gi, '&')
    .replace(/\s+/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/\s+for\s+\.$/i, '.')
    .replace(/[\s,;]+$/g, '')
    .trim();
  return displayText || undefined;
};

const RECRUITER_TERM_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bcalibrated[_\s-]?confidence\b/gi, 'Match Confidence'],
  [/\bmandatory[_\s-]?failure\b/gi, 'Mandatory Requirement Gap'],
  [/\bdomain[_\s-]?alignment\b/gi, 'Domain Match'],
  [/\bcross[_\s-]?domain[_\s-]?guard\b/gi, 'Role/Domain Conflict'],
  [/\bsemantic[_\s-]?reason\b/gi, 'AI Match Explanation'],
  [/\bexperience[_\s-]?gap\b/gi, 'Experience Gap'],
  [/\beducation[_\s-]?conflict\b/gi, 'Education Concern'],
  [/\binferred[_\s-]?skills\b/gi, 'Related Skills Identified'],
];

export const humanizeRecruiterText = (value: unknown): string | undefined => {
  const cleaned = cleanRecommendationText(value);
  if (!cleaned) return undefined;
  return RECRUITER_TERM_REPLACEMENTS.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), cleaned);
};

const firstCandidateText = (...values: unknown[]): string | undefined => {
  for (const value of values) {
    const cleaned = cleanCandidateText(value);
    if (cleaned) return cleaned;
  }
  return undefined;
};

const cleanList = (value: unknown): string[] => {
  const items = Array.isArray(value) ? value : cleanCandidateText(value) ? [value] : [];
  return items.map(cleanCandidateText).filter((item): item is string => Boolean(item));
};

const unique = (values: string[]): string[] => {
  const seen = new Set<string>();
  return values.filter((value) => {
    const key = value.toLocaleLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export const normalizeCandidateRouteId = (value: string | string[] | undefined): string | undefined => {
  const candidateId = cleanCandidateText(Array.isArray(value) ? value[0] : value)?.replace(/\.json$/i, '');
  if (!candidateId || candidateId.includes('/') || candidateId.includes('\\')) return undefined;
  return candidateId;
};

export const responseMatchesCandidateId = (data: CVUploadResponse, requestedId: string): boolean => {
  const requested = requestedId.replace(/\.json$/i, '').toLocaleLowerCase();
  const identifiers = [data.id, data.scan_id, data.candidate_id, data.cv_id, ...(Array.isArray(data.legacy_cv_keys) ? data.legacy_cv_keys : [])]
    .map(cleanCandidateText)
    .filter((value): value is string => Boolean(value))
    .map((value) => value.replace(/\.json$/i, '').toLocaleLowerCase());
  return identifiers.includes(requested);
};

const formatCandidateDateRange = (value: UnknownRecord): string | undefined => {
  const start = firstCandidateText(value.start_date, value.start, value.from);
  const end = Boolean(value.is_current) ? 'Present' : firstCandidateText(value.end_date, value.end, value.to);
  return start || end ? [start, end].filter(Boolean).join(' – ') : undefined;
};

const mapExperience = (value: unknown): CandidateExperienceView | undefined => {
  if (!isRecord(value)) {
    const description = cleanCandidateText(value);
    return description ? { responsibilities: [description] } : undefined;
  }
  const responsibilities = unique([
    ...cleanList(value.responsibilities),
    ...cleanList(value.bullet_points),
    ...cleanList(value.description),
    ...cleanList(value.details),
  ]);
  const item: CandidateExperienceView = {
    title: firstCandidateText(value.job_title, value.role, value.position, value.title),
    company: firstCandidateText(value.company, value.company_name, value.employer),
    dates: firstCandidateText(isRecord(value.interval) ? value.interval.raw_value : undefined, value.dates, formatCandidateDateRange(value), value.duration),
    responsibilities,
  };
  return item.title || item.company || item.dates || item.responsibilities.length ? item : undefined;
};

const mergeExperienceSources = (...sources: unknown[]): CandidateExperienceView[] => {
  const merged: CandidateExperienceView[] = [];
  for (const source of sources) {
    if (!Array.isArray(source)) continue;
    for (const rawItem of source) {
      const item = mapExperience(rawItem);
      if (!item) continue;
      const companyKey = item.company?.toLocaleLowerCase();
      const titleKey = item.title?.toLocaleLowerCase();
      const dateKey = item.dates?.toLocaleLowerCase();
      const existing = merged.find((candidate) =>
        (companyKey && candidate.company?.toLocaleLowerCase() === companyKey &&
          (!titleKey || !candidate.title || candidate.title.toLocaleLowerCase() === titleKey) &&
          (!dateKey || !candidate.dates || candidate.dates.toLocaleLowerCase() === dateKey)) ||
        (titleKey && dateKey && candidate.title?.toLocaleLowerCase() === titleKey && candidate.dates?.toLocaleLowerCase() === dateKey));
      if (!existing) {
        merged.push(item);
        continue;
      }
      existing.title = existing.title ?? item.title;
      existing.company = existing.company ?? item.company;
      existing.dates = existing.dates ?? item.dates;
      existing.responsibilities = unique([...existing.responsibilities, ...item.responsibilities]);
    }
  }
  return merged;
};

const mapEducation = (value: unknown): CandidateEducationView | undefined => {
  if (!isRecord(value)) {
    const details = cleanCandidateText(value);
    return details ? { details } : undefined;
  }
  const item: CandidateEducationView = {
    degree: firstCandidateText(value.degree, value.qualification),
    institution: firstCandidateText(value.institution, value.university, value.school),
    dates: firstCandidateText(isRecord(value.interval) ? value.interval.raw_value : undefined, value.dates, formatCandidateDateRange(value), value.passing_year, value.year),
    grade: firstCandidateText(value.grade, value.score, value.gpa),
    details: firstCandidateText(value.details, value.description) || cleanList(value.details).join(' • ') || undefined,
  };
  return Object.values(item).some(Boolean) ? item : undefined;
};

const normalizeFingerprintPart = (value: string | undefined): string => (value || '').toLocaleLowerCase().replace(/[^a-z0-9]+/g, '');

const LEGACY_SECTION_LABELS = new Set([
  'contact', 'profile', 'profile summary', 'professional profile summary', 'objective', 'summary',
  'education', 'educational background', 'work experience', 'experience', 'technical skills', 'skills',
  'safety & compliance', 'safety and compliance', 'core competencies', 'languages', 'interests', 'declaration',
]);
const EDUCATION_QUALIFICATION = /\b(?:b\.?\s*e\.?|b\.?\s*tech|b\.?\s*sc|bca|bba|b\.?\s*com|b\.?\s*a\.?|b\.?\s*pharm|b\.?\s*arch|m\.?\s*e\.?|m\.?\s*tech|m\.?\s*sc|mca|mba|m\.?\s*com|m\.?\s*a\.?|m\.?\s*pharm|m(?:\.\s*|\s+)arch|master of architecture|ph\.?\s*d|diploma|iti|h\.?\s*s\.?\s*c|s\.?\s*s\.?\s*c|10th|12th|bachelor|master|doctorate)\b/i;
const EMPLOYMENT_DATE_RANGE = /\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\s*(?:-|–|—|to|till|until)\s*(?:present|current|till date|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})\b/i;

const isLegacyEducationView = (item: CandidateEducationView): boolean => {
  const institution = (item.institution || '').trim();
  if (!item.degree || !(EDUCATION_QUALIFICATION.test(item.degree) || /(^|[^A-Za-z])MArch([^A-Za-z]|$)/.test(item.degree))) return false;
  if (LEGACY_SECTION_LABELS.has(institution.toLocaleLowerCase())) return false;
  if (institution && institution === institution.toLocaleUpperCase() && institution.split(/\s+/).length >= 3) return false;
  if (EMPLOYMENT_DATE_RANGE.test(item.degree)) return false;
  return Boolean(institution || item.dates || item.grade);
};

const canonicalEducationFingerprint = (item: CandidateEducationView): string => {
  const institution = normalizeFingerprintPart(item.institution);
  const dates = normalizeFingerprintPart(item.dates);
  if (institution && dates) return `${institution}|${dates}`;
  const degree = normalizeFingerprintPart(item.degree)
    .replace(/bachelorofengineering|bechemical|be$/, 'be')
    .replace(/highersecondary|hsc$/, 'hsc')
    .replace(/secondaryschool|ssc$/, 'ssc');
  return `${degree}|${institution}|${dates}|${normalizeFingerprintPart(item.grade)}`;
};

const isLegacyProjectView = (item: CandidateProjectView): boolean => {
  const name = (item.name || '').trim();
  if (!name || LEGACY_SECTION_LABELS.has(name.toLocaleLowerCase())) return false;
  if (EMPLOYMENT_DATE_RANGE.test(item.description || '')) return false;
  if (/[@☎📞✉🏠]|\b(?:phone|email|address)\b/i.test(item.description || '')) return false;
  return Boolean(item.technologies.length || item.bulletPoints.length || /\bproject\b/i.test(name));
};

const selectIntegrityCollection = (
  normalizedValue: unknown,
  rawValue: unknown,
  expectedCount: unknown,
  sourceSection: 'education' | 'projects',
): unknown[] => {
  const validatedItems = (value: unknown): unknown[] | undefined => (
    Array.isArray(value)
      ? value.filter((item) => isRecord(item) && cleanCandidateText(item.source_section) === sourceSection)
      : undefined
  );
  const normalizedItems = validatedItems(normalizedValue);
  const rawItems = validatedItems(rawValue);
  if (typeof expectedCount === 'number' && Number.isInteger(expectedCount) && expectedCount >= 0) {
    if (normalizedItems?.length === expectedCount) return normalizedItems;
    if (rawItems?.length === expectedCount) return rawItems;
    return [];
  }
  return normalizedItems || rawItems || [];
};

const versionAtLeast = (value: unknown, minimum: [number, number]): boolean => {
  const match = cleanCandidateText(value)?.match(/^(\d+)\.(\d+)\./);
  if (!match) return false;
  const current: [number, number] = [Number(match[1]), Number(match[2])];
  return current[0] > minimum[0] || (current[0] === minimum[0] && current[1] >= minimum[1]);
};

const mergeEducationSources = (...sources: unknown[]): CandidateEducationView[] => {
  const merged: CandidateEducationView[] = [];
  for (const source of sources) {
    if (!Array.isArray(source)) continue;
    for (const rawItem of source) {
      const item = mapEducation(rawItem);
      if (!item) continue;
      const fingerprint = canonicalEducationFingerprint(item);
      const existing = merged.find((candidate) => canonicalEducationFingerprint(candidate) === fingerprint);
      if (!existing) {
        merged.push(item);
        continue;
      }
      existing.degree = existing.degree ?? item.degree;
      existing.institution = existing.institution ?? item.institution;
      existing.dates = existing.dates ?? item.dates;
      existing.grade = existing.grade ?? item.grade;
      existing.details = existing.details ?? item.details;
    }
  }
  return merged;
};

const mapProject = (value: unknown): CandidateProjectView | undefined => {
  if (!isRecord(value)) {
    const name = cleanCandidateText(value);
    return name ? { name, technologies: [], bulletPoints: [] } : undefined;
  }
  const project: CandidateProjectView = {
    name: firstCandidateText(value.name, value.title),
    description: firstCandidateText(value.description, value.details),
    technologies: unique(cleanList(value.technologies ?? value.tech_stack)),
    bulletPoints: unique([...cleanList(value.bullet_points), ...cleanList(value.responsibilities)]),
  };
  return project.name || project.description || project.technologies.length || project.bulletPoints.length ? project : undefined;
};

const mergeProjectSources = (...sources: unknown[]): CandidateProjectView[] => {
  const merged: CandidateProjectView[] = [];
  for (const source of sources) {
    if (!Array.isArray(source)) continue;
    for (const rawItem of source) {
      const item = mapProject(rawItem);
      if (!item) continue;
      const existing = item.name ? merged.find((candidate) => candidate.name?.toLocaleLowerCase() === item.name?.toLocaleLowerCase()) : undefined;
      if (!existing) {
        merged.push(item);
        continue;
      }
      existing.description = existing.description ?? item.description;
      existing.technologies = unique([...existing.technologies, ...item.technologies]);
      existing.bulletPoints = unique([...existing.bulletPoints, ...item.bulletPoints]);
    }
  }
  return merged;
};

const isRecoveredSkillCategory = (category: string): boolean => (
  /^recover(?:ed|y)\b.*\b(?:skills?|stats?)\b/i.test(category.trim())
);

const collectSkills = (value: unknown): string[] => {
  if (Array.isArray(value)) return cleanList(value);
  if (!isRecord(value)) return [];
  const categorizedEntries = isRecord(value.categorized) ? Object.entries(value.categorized) : [];
  const rejected = new Set(
    categorizedEntries
      .filter(([category]) => isRecoveredSkillCategory(category))
      .flatMap(([, items]) => cleanList(items))
      .map((item) => normalizeFingerprintPart(item)),
  );
  const categorized = categorizedEntries
    .filter(([category]) => !isRecoveredSkillCategory(category))
    .flatMap(([, items]) => cleanList(items));
  return unique([...cleanList(value.all_skills), ...cleanList(value.skills), ...categorized])
    .filter((skill) => !rejected.has(normalizeFingerprintPart(skill)));
};

const recoveredContextSkillFingerprints = (...values: unknown[]): Set<string> => {
  const rejected = new Set<string>();
  for (const value of values) {
    if (!isRecord(value) || !isRecord(value.categorized)) continue;
    for (const [category, items] of Object.entries(value.categorized)) {
      if (!isRecoveredSkillCategory(category)) continue;
      cleanList(items).forEach((item) => rejected.add(normalizeFingerprintPart(item)));
    }
  }
  return rejected;
};

const collectCertifications = (value: unknown): string[] => {
  if (Array.isArray(value)) return unique(value.flatMap(collectCertifications));
  if (isRecord(value)) {
    const namedCertification = firstCandidateText(value.name, value.title, value.certification);
    return namedCertification ? [namedCertification] : unique(Object.values(value).flatMap(collectCertifications));
  }
  const certification = cleanCandidateText(value);
  return certification ? [certification] : [];
};

export const buildCandidateDetailViewModel = (data: CVUploadResponse): CandidateDetailViewModel => {
  const resume = isRecord(data.resume_json) ? data.resume_json : {};
  const normalized = isRecord(data.normalized_resume) ? data.normalized_resume : {};
  const topLevelContact = isRecord(data.contact_info) ? data.contact_info : {};
  const contact = isRecord(resume.contact_info) ? resume.contact_info : {};
  const normalizedContact = isRecord(normalized.contact) ? normalized.contact : {};
  const experience = mergeExperienceSources(data.work_experience, resume.work_experience, resume.experience, normalized.employment);
  const currentExperience = experience.find((item) => item.title || item.company);
  const integrityCounts = isRecord(data.extraction_integrity?.accepted_counts)
    ? data.extraction_integrity.accepted_counts
    : {};
  const hasIntegrityContract = versionAtLeast(data.parser_version, [1, 1])
    && versionAtLeast(data.schema_version, [2, 1])
    && isRecord(data.extraction_integrity)
    && cleanCandidateText(data.extraction_integrity.policy_version)?.startsWith('section-integrity-')
    && Number.isInteger(integrityCounts.education)
    && Number(integrityCounts.education) >= 0
    && Number.isInteger(integrityCounts.projects)
    && Number(integrityCounts.projects) >= 0;
  const educationSource = hasIntegrityContract
    ? selectIntegrityCollection(
      normalized.education,
      resume.education,
      data.extraction_integrity?.accepted_counts?.education,
      'education',
    )
    : [resume.education, normalized.education, data.education].flatMap((value) => (Array.isArray(value) ? value : []));
  const education = mergeEducationSources(educationSource).filter((item) => hasIntegrityContract || isLegacyEducationView(item));
  const certifications = unique([...collectCertifications(resume.certifications), ...collectCertifications(normalized.certifications), ...collectCertifications(data.certifications)]);
  const rejectedRecoveredSkills = recoveredContextSkillFingerprints(resume.skills, data.skills);
  const skills = unique([...collectSkills(resume.skills), ...collectSkills(normalized.skills), ...collectSkills(data.skills)])
    .filter((skill) => !rejectedRecoveredSkills.has(normalizeFingerprintPart(skill)));
  const projectSource = hasIntegrityContract
    ? selectIntegrityCollection(
      normalized.projects,
      resume.projects,
      data.extraction_integrity?.accepted_counts?.projects,
      'projects',
    )
    : [resume.projects, normalized.projects, data.projects].flatMap((value) => (Array.isArray(value) ? value : []));
  const projects = mergeProjectSources(projectSource).filter((item) => hasIntegrityContract || isLegacyProjectView(item));

  return {
    name: firstCandidateText(data.full_name, data.candidate_name, topLevelContact.full_name, topLevelContact.name, contact.full_name, contact.name, normalizedContact.full_name, normalizedContact.name),
    email: firstCandidateText(data.email, topLevelContact.email, contact.email, normalizedContact.email),
    phone: firstCandidateText(data.phone, topLevelContact.phone, contact.phone, normalizedContact.phone),
    location: firstCandidateText(data.location, topLevelContact.location, contact.location, normalizedContact.location),
    linkedin: firstCandidateText(data.linkedin, topLevelContact.linkedin, contact.linkedin, normalizedContact.linkedin),
    github: firstCandidateText(data.github, topLevelContact.github, contact.github, normalizedContact.github),
    jobTitle: firstCandidateText(data.job_title, currentExperience?.title),
    company: firstCandidateText(data.company_name, currentExperience?.company),
    summary: firstCandidateText(data.summary, resume.summary, normalized.summary),
    extractedText: firstCandidateText(data.markdown, data.text),
    experience,
    education,
    certifications,
    skills,
    projects,
  };
};
