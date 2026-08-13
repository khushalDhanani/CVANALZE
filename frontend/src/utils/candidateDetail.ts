import type { CVUploadResponse } from '@/types/api';

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
    dates: firstCandidateText(isRecord(value.interval) ? value.interval.raw_value : undefined, value.dates, value.duration),
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
    dates: firstCandidateText(value.passing_year, value.dates, value.year, isRecord(value.interval) ? value.interval.raw_value : undefined),
    grade: firstCandidateText(value.grade, value.score, value.gpa),
    details: firstCandidateText(value.details, value.description),
  };
  return Object.values(item).some(Boolean) ? item : undefined;
};

const mergeEducationSources = (...sources: unknown[]): CandidateEducationView[] => {
  const merged: CandidateEducationView[] = [];
  for (const source of sources) {
    if (!Array.isArray(source)) continue;
    for (const rawItem of source) {
      const item = mapEducation(rawItem);
      if (!item) continue;
      const existing = merged.find((candidate) => {
        const sameDegree = item.degree && candidate.degree?.toLocaleLowerCase() === item.degree.toLocaleLowerCase();
        const sameInstitution = item.institution && candidate.institution?.toLocaleLowerCase() === item.institution.toLocaleLowerCase();
        const sameDetails = item.details && candidate.details?.toLocaleLowerCase() === item.details.toLocaleLowerCase();
        return Boolean(sameDegree || sameInstitution || sameDetails);
      });
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

const collectSkills = (value: unknown): string[] => {
  if (Array.isArray(value)) return cleanList(value);
  if (!isRecord(value)) return [];
  const categorized = isRecord(value.categorized) ? Object.values(value.categorized).flatMap(cleanList) : [];
  return unique([...cleanList(value.all_skills), ...cleanList(value.skills), ...categorized]);
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
  const education = mergeEducationSources(resume.education, normalized.education, data.education);
  const certifications = unique([...collectCertifications(resume.certifications), ...collectCertifications(normalized.certifications), ...collectCertifications(data.certifications)]);
  const skills = unique([...collectSkills(resume.skills), ...collectSkills(normalized.skills), ...collectSkills(data.skills)]);
  const projects = mergeProjectSources(resume.projects, normalized.projects, data.projects);

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
