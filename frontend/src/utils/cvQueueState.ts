import type { BadgeTone } from '@/components/ui/Badge';
import type { CVProcessingResponse } from '@/types/api';

export type CvQueueUiState = 'PENDING' | 'PROCESSING' | 'RETRYING' | 'COMPLETED' | 'FAILED';

export interface CvQueueStateMeta {
  label: 'Pending' | 'Processing' | 'Retrying' | 'Completed' | 'Failed';
  tone: BadgeTone;
  terminal: boolean;
}

export function resolveCvQueueUiState(response: Partial<CVProcessingResponse> & Record<string, any>): CvQueueUiState {
  const jobState = String(response.job_state || '').toUpperCase();
  const status = String(response.status || '').toUpperCase();
  if (jobState === 'FAILED' || jobState === 'CANCELLED' || status === 'FAILED' || status === 'CANCELLED') {
    return 'FAILED';
  }
  if (
    jobState === 'COMPLETED' ||
    jobState === 'COMPLETED_DEGRADED' ||
    status === 'COMPLETED' ||
    status === 'COMPLETED_DEGRADED' ||
    status === 'NEW_CV' ||
    status === 'REPROCESSED' ||
    status === 'CACHE_HIT' ||
    response.is_complete === true
  ) {
    return 'COMPLETED';
  }
  if (jobState === 'RETRYING') {
    return 'RETRYING';
  }
  if (jobState === 'PROCESSING') {
    return 'PROCESSING';
  }
  return 'PENDING';
}

export function getCvQueueStateMeta(state: CvQueueUiState): CvQueueStateMeta {
  switch (state) {
    case 'PROCESSING':
      return { label: 'Processing', tone: 'info', terminal: false };
    case 'RETRYING':
      return { label: 'Retrying', tone: 'warning', terminal: false };
    case 'COMPLETED':
      return { label: 'Completed', tone: 'success', terminal: true };
    case 'FAILED':
      return { label: 'Failed', tone: 'danger', terminal: true };
    default:
      return { label: 'Pending', tone: 'neutral', terminal: false };
  }
}
