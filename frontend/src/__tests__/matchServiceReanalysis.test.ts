import { reanalyzeScan } from '../services/matchService';
import type { CVUploadResponse } from '../types/api';

function assertEquals(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

const updatedCandidate = {
  id: 'test',
  scan_id: 'test',
  filename: 'candidate.pdf',
  parsed_at: '2026-08-13T00:00:00Z',
  markdown: 'Candidate resume',
  analysis_run_id: 'analysis_test',
  match_analysis: {
    best_match: { vacancy_id: '123', llm_reason: 'Fresh Ollama reasoning' },
  },
} as CVUploadResponse;
const requests: string[] = [];
const client = {
  post: async <T>(endpoint: string): Promise<T> => {
    requests.push(endpoint);
    return updatedCandidate as T;
  },
};

async function run(): Promise<void> {
  const response = await reanalyzeScan('test', client);
  assertEquals(requests, ['/api/match/reanalyze/test']);
  assertEquals(response, updatedCandidate);
  assertEquals(response.match_analysis?.best_match?.llm_reason, 'Fresh Ollama reasoning');
}

void run();
