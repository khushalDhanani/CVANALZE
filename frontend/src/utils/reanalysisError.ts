export type ReanalysisErrorKind = 'candidate_not_found' | 'llm_timeout' | 'llm_unavailable' | 'invalid_response' | 'network' | 'server';

export interface ReanalysisErrorPresentation {
  kind: ReanalysisErrorKind;
  title: string;
  message: string;
}

type ApiErrorLike = Error & { status: number; data?: { detail?: unknown } };

function isApiErrorLike(error: unknown): error is ApiErrorLike {
  return error instanceof Error && typeof (error as Partial<ApiErrorLike>).status === 'number';
}

function getErrorDetail(error: unknown): string {
  if (isApiErrorLike(error)) {
    const detail = error.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail.trim();
    return error.message;
  }
  return error instanceof Error ? error.message : '';
}

export function getReanalysisErrorPresentation(error: unknown): ReanalysisErrorPresentation {
  const status = isApiErrorLike(error) ? error.status : null;
  const detail = getErrorDetail(error);
  const normalizedDetail = detail.toLowerCase();

  if (status === 404) {
    return {
      kind: 'candidate_not_found',
      title: 'Candidate Not Found',
      message: detail || 'The candidate record no longer exists. Return to the candidate list and reload it.',
    };
  }
  if (status === 408 || status === 504 || normalizedDetail.includes('timed out') || normalizedDetail.includes('timeout')) {
    return {
      kind: 'llm_timeout',
      title: 'LLM Timeout',
      message: detail || 'The LLM did not finish re-analysis before the request deadline. Please try again.',
    };
  }
  if (status === 422 || normalizedDetail.includes('invalid structured') || normalizedDetail.includes('invalid json') || normalizedDetail.includes('schema')) {
    return {
      kind: 'invalid_response',
      title: 'Invalid LLM Response',
      message: detail || 'The LLM response could not be validated. Please retry the re-analysis.',
    };
  }
  if (status === 503 || normalizedDetail.includes('llm service is unavailable') || normalizedDetail.includes('ollama is unavailable')) {
    return {
      kind: 'llm_unavailable',
      title: 'LLM Unavailable',
      message: detail || 'The configured LLM service or model is unavailable. Check the Ollama configuration and try again.',
    };
  }
  if (status === 0) {
    return {
      kind: 'network',
      title: 'Connection Error',
      message: detail || 'The API could not be reached. Check the connection and try again.',
    };
  }
  return {
    kind: 'server',
    title: 'Re-analysis Error',
    message: detail || 'The server could not complete candidate re-analysis. Please try again.',
  };
}
