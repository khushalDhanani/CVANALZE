import { getCvQueueStateMeta, resolveCvQueueUiState } from '../utils/cvQueueState';

function assertEquals(actual: unknown, expected: unknown): void {
  if (actual !== expected) throw new Error(`Expected ${String(expected)}, received ${String(actual)}`);
}

assertEquals(resolveCvQueueUiState({ job_state: 'QUEUED' }), 'PENDING');
assertEquals(resolveCvQueueUiState({ job_state: 'PROCESSING' }), 'PROCESSING');
assertEquals(resolveCvQueueUiState({ job_state: 'RETRYING' }), 'RETRYING');
assertEquals(resolveCvQueueUiState({ job_state: 'COMPLETED' }), 'COMPLETED');
assertEquals(resolveCvQueueUiState({ status: 'CACHE_HIT' }), 'COMPLETED');
assertEquals(resolveCvQueueUiState({ job_state: 'FAILED' }), 'FAILED');
assertEquals(resolveCvQueueUiState({ job_state: 'CANCELLED' }), 'FAILED');
assertEquals(getCvQueueStateMeta('PENDING').label, 'Pending');
assertEquals(getCvQueueStateMeta('PROCESSING').label, 'Processing');
assertEquals(getCvQueueStateMeta('RETRYING').label, 'Retrying');
assertEquals(getCvQueueStateMeta('COMPLETED').label, 'Completed');
assertEquals(getCvQueueStateMeta('FAILED').label, 'Failed');
