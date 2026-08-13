import { reanalyzeCandidateAndCommit } from '../utils/candidateReanalysis';
import { normalizeCandidateMatchAnalysis } from '../utils/candidateDetail';
import { getVacancyEnrichmentPresentation } from '../utils/vacancyEnrichment';
import type { CVUploadResponse, EnrichedJobEvaluation } from '../types/api';

function assertEquals(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

let renderedCandidate = {
  id: 'test',
  scan_id: 'test',
  filename: 'candidate.pdf',
  parsed_at: '2026-08-13T00:00:00Z',
  markdown: 'Candidate resume',
  match_analysis: { best_match: { vacancy_id: '123', llm_reason: 'Old reasoning' } },
} as CVUploadResponse;
const freshOpening = {
  vacancy_id: '123',
  llm_reason: 'Fresh Ollama reasoning',
  inferred_skills: ['HPLC'],
};
const response = {
  ...renderedCandidate,
  analysis_run_id: 'analysis_fresh',
  match_analysis: { best_match: freshOpening, suitable_openings: [freshOpening], unsuitable_openings: [] },
} as CVUploadResponse;

async function run(): Promise<void> {
  await reanalyzeCandidateAndCommit({
    scanId: 'test',
    reanalyze: async () => response,
    commit: (candidate) => { renderedCandidate = candidate; },
  });

  const normalized = normalizeCandidateMatchAnalysis(renderedCandidate.match_analysis);
  const displayed = getVacancyEnrichmentPresentation(normalized?.best_match as Partial<EnrichedJobEvaluation>);
  assertEquals(renderedCandidate.analysis_run_id, 'analysis_fresh');
  assertEquals(displayed.reasoning, 'Fresh Ollama reasoning');
}

void run();
