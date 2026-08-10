import fs from 'node:fs';
import Module, { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const sourcePath = path.resolve(testDirectory, '../utils/candidateDetail.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const output = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const candidateModule = new Module(sourcePath);
candidateModule.filename = sourcePath;
candidateModule.paths = Module._nodeModulePaths(path.dirname(sourcePath));
candidateModule._compile(output, sourcePath);

const { buildCandidateDetailViewModel, normalizeCandidateMatchAnalysis, normalizeCandidateRouteId, responseMatchesCandidateId } = candidateModule.exports;

const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

const canonicalPayload = {
  id: 'cv_alpha',
  scan_id: 'cv_alpha',
  full_name: '  ',
  resume_json: {
    contact_info: { name: 'Jordan Lee', email: 'jordan@example.org', phone: null },
    work_experience: [
      { company: 'Example Group', job_title: 'Engineer', responsibilities: ['Built services'] },
      { company: 'Example Group', job_title: 'Lead Engineer', dates: '2022 - Present', responsibilities: ['Led delivery'] },
    ],
    education: [{ degree: 'BSc', institution: 'Example University' }],
    skills: { categorized: { Languages: ['Python'], Platforms: ['Linux'] } },
    projects: [{ name: 'Service Platform', bullet_points: ['Implemented APIs'] }],
    certifications: [{ name: 'Cloud Certificate' }],
  },
  normalized_resume: {
    employment: [{ company: { normalized_value: 'Example Group' }, job_title: { normalized_value: 'Engineer' }, responsibilities: ['Reviewed code'] }],
    education: [{ degree: { normalized_value: 'BSc' }, institution: { normalized_value: 'Example University' }, grade: 'A' }],
  },
};

const canonicalView = buildCandidateDetailViewModel(canonicalPayload);
assert(canonicalView.name === 'Jordan Lee', 'Whitespace top-level values must fall through to valid nested fields.');
assert(canonicalView.experience.length === 2, 'Distinct roles at one company must not be collapsed.');
assert(canonicalView.experience[0].responsibilities.length === 2, 'Equivalent records from multiple schemas must merge completely.');
assert(canonicalView.education.length === 1 && canonicalView.education[0].grade === 'A', 'Education schema variants must merge.');
assert(canonicalView.skills.length === 2 && canonicalView.projects.length === 1 && canonicalView.certifications.length === 1, 'All populated arrays must render.');

const partialPayload = {
  id: 'cv_beta',
  scan_id: 'cv_beta',
  contact_info: { full_name: 'Priya Nair', location: 'Remote' },
  work_experience: ['Independent consulting'],
  education: ['Diploma in Design'],
  skills: ['Research', null, 'Research'],
  projects: ['Portfolio redesign'],
  certifications: { professional: ['Design Certificate'] },
  resume_json: null,
};
const partialView = buildCandidateDetailViewModel(partialPayload);
assert(partialView.name === 'Priya Nair' && partialView.email === undefined, 'Partial contact data must not create fallback values.');
assert(partialView.experience.length === 1 && partialView.education.length === 1, 'Flat array schemas must remain visible.');
assert(partialView.skills.length === 1 && partialView.projects.length === 1 && partialView.certifications.length === 1, 'Flat and nested collections must normalize generically.');
assert(!JSON.stringify(partialView).match(/"(?:null|undefined|not specified)"/i), 'Null sentinels must never reach rendering.');

assert(normalizeCandidateRouteId(['cv_alpha']) === 'cv_alpha', 'Array route parameters must normalize.');
assert(normalizeCandidateRouteId('../cv_alpha') === undefined, 'Path-like route IDs must be rejected.');
assert(responseMatchesCandidateId(canonicalPayload, 'cv_alpha'), 'Matching response identities must pass.');
assert(!responseMatchesCandidateId(canonicalPayload, 'cv_beta'), 'Mismatched response identities must be rejected.');

const normalizedMatches = normalizeCandidateMatchAnalysis({
  has_genuine_match: true,
  match_status: 'DB_MATCH',
  best_match: { vacancy_id: 1, classification: 'HIGH', match_status: 'MATCHED', score: 88, mandatory_failures: [] },
  suitable_openings: [
    { vacancy_id: 1, classification: 'HIGH', match_status: 'MATCHED', score: 88, mandatory_failures: [] },
    { vacancy_id: 2, classification: 'MEDIUM', match_status: 'MATCHED', score: 72.3, mandatory_failures: [] },
    { vacancy_id: 3, classification: 'HIGH', match_status: 'MATCHED', score: 91, mandatory_failures: [{ requirement_id: 'minimum_experience' }] },
  ],
  unsuitable_openings: [{ vacancy_id: 4, classification: 'LOW', match_status: 'NO_STRONG_VACANCY_MATCH', score: 35 }],
});
assert(normalizedMatches.suitable_openings.length === 2 && normalizedMatches.best_match.vacancy_id === 1, 'Backend MATCHED decisions without hard disqualifiers must remain selected.');
assert(normalizedMatches.unsuitable_openings.length === 2, 'Hard-disqualified and rejected matches must remain available for manual review.');

const normalizedLegacySplitScore = normalizeCandidateMatchAnalysis({
  match_status: 'NO_SUITABLE_MATCH',
  best_match: null,
  suitable_openings: [],
  unsuitable_openings: [{
    vacancy_id: 1215,
    vacancy_fit_score: 89.2,
    score: 73.5,
    overall_score: 73.5,
    classification: 'MEDIUM',
    vacancy_match_status: 'MATCHED',
    mandatory_failures: [],
  }],
  active_vacancy_summary: 'NO_STRONG_MATCH: stale summary',
});
assert(normalizedLegacySplitScore.match_status === 'MATCHED', 'A persisted canonical MATCHED opening must repair a stale candidate-level status.');
assert(normalizedLegacySplitScore.best_match.vacancy_fit_score === 89.2, 'The canonical fit score must remain the displayed score.');

console.log('Candidate detail generic tests: passed');
