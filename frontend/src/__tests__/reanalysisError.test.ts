import { getReanalysisErrorPresentation } from '../utils/reanalysisError';

function assertEquals(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

function apiError(message: string, status: number, detail?: string): Error {
  return Object.assign(new Error(message), { status, data: detail ? { detail } : undefined });
}

assertEquals(getReanalysisErrorPresentation(apiError('Not found', 404, 'Candidate not found.')).kind, 'candidate_not_found');
assertEquals(getReanalysisErrorPresentation(apiError('Timed out', 504)).kind, 'llm_timeout');
assertEquals(getReanalysisErrorPresentation(apiError('Unavailable', 503)).kind, 'llm_unavailable');
assertEquals(getReanalysisErrorPresentation(apiError('Invalid', 422)).kind, 'invalid_response');
assertEquals(getReanalysisErrorPresentation(apiError('Network request failed', 0)).kind, 'network');
assertEquals(getReanalysisErrorPresentation(apiError('Internal server error', 500)).kind, 'server');
