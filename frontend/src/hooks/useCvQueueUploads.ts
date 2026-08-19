import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API_CONFIG } from '@/constants/config';
import { cvService } from '@/services/cvService';
import { matchService } from '@/services/matchService';
import type { CVProcessingJobSummary, CVProcessingResponse } from '@/types/api';
import { getCvQueueStateMeta, resolveCvQueueUiState } from '@/utils/cvQueueState';
import type { CvQueueUiState } from '@/utils/cvQueueState';
import type { FilePickerAsset } from './useCvUpload';

export interface CvQueueUploadFile extends FilePickerAsset {
  size?: number;
}

export interface CvQueueUploadItem {
  clientId: string;
  filename: string;
  cvKey?: string;
  jobId?: string;
  state: CvQueueUiState;
  progress: number;
  message: string;
  error?: string;
  errorCode?: string;
  syncError?: string;
}

const TERMINAL_STATES = new Set<CvQueueUiState>(['COMPLETED', 'FAILED']);

function getResponseKey(response: Record<string, any>): string | undefined {
  return response.cv_key || response.scan_id || response.id;
}

export function useCvQueueUploads() {
  const [items, setItems] = useState<CvQueueUploadItem[]>([]);
  const [hydrationError, setHydrationError] = useState<string | null>(null);
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const mountedRef = useRef(true);
  const idSequenceRef = useRef(0);

  const updateItem = useCallback((clientId: string, update: Partial<CvQueueUploadItem>) => {
    if (!mountedRef.current) return;
    setItems((current) => current.map((item) => item.clientId === clientId ? { ...item, ...update } : item));
  }, []);

  const stopPolling = useCallback((clientId: string) => {
    const timer = timersRef.current.get(clientId);
    if (timer) clearTimeout(timer);
    timersRef.current.delete(clientId);
  }, []);

  const pollItem = useCallback(function schedulePoll(
    clientId: string,
    cvKey: string,
    enrichWithLlm: boolean,
    attempt: number = 0,
    consecutiveErrors: number = 0,
  ) {
    stopPolling(clientId);
    const timer = setTimeout(async () => {
      try {
        const response = enrichWithLlm ? await matchService.getMatchStatus(cvKey) : await cvService.getCvStatus(cvKey);
        const processingResponse = response as CVProcessingResponse & Record<string, any>;
        const state = resolveCvQueueUiState(processingResponse);
        const meta = getCvQueueStateMeta(state);
        updateItem(clientId, {
          state,
          progress: state === 'COMPLETED' ? 100 : processingResponse.progress || 0,
          message: processingResponse.error_message || processingResponse.message || meta.label,
          error: state === 'FAILED' ? processingResponse.error_message || processingResponse.message || 'CV processing failed.' : undefined,
          errorCode: processingResponse.error_code || undefined,
          syncError: undefined,
        });
        if (!meta.terminal) {
          schedulePoll(clientId, cvKey, enrichWithLlm, (attempt + 1) % API_CONFIG.MAX_POLL_RETRIES, 0);
        } else {
          timersRef.current.delete(clientId);
        }
      } catch (error: any) {
        const nextErrorCount = consecutiveErrors + 1;
        updateItem(clientId, {
          syncError: nextErrorCount >= 5 ? error?.message || 'Unable to refresh backend status.' : undefined,
        });
        schedulePoll(clientId, cvKey, enrichWithLlm, (attempt + 1) % API_CONFIG.MAX_POLL_RETRIES, nextErrorCount);
      }
    }, API_CONFIG.POLL_INTERVAL_MS);
    timersRef.current.set(clientId, timer);
  }, [stopPolling, updateItem]);

  const uploadFiles = useCallback(async (files: CvQueueUploadFile[], enrichWithLlm: boolean) => {
    const queuedItems = files.map((file) => {
      idSequenceRef.current += 1;
      return {
        file,
        item: {
          clientId: `cv-upload-${Date.now()}-${idSequenceRef.current}`,
          filename: file.name,
          state: 'PENDING' as CvQueueUiState,
          progress: 0,
          message: 'Waiting to be submitted in selection order.',
        },
      };
    });
    setItems((current) => [...queuedItems.map(({ item }) => item), ...current]);

    for (const { file, item } of queuedItems) {
      try {
        const response = enrichWithLlm ? await matchService.uploadAndAnalyze(file) : await cvService.uploadCv(file);
        const responseRecord = response as CVProcessingResponse & Record<string, any>;
        const cvKey = String(getResponseKey(responseRecord) || '');
        if (!cvKey) throw new Error('The upload response did not include a CV tracking key.');
        const state = resolveCvQueueUiState(responseRecord);
        const meta = getCvQueueStateMeta(state);
        updateItem(item.clientId, {
          cvKey,
          jobId: responseRecord.job_id || undefined,
          state,
          progress: state === 'COMPLETED' ? 100 : responseRecord.progress || 0,
          message: responseRecord.message || meta.label,
          error: state === 'FAILED' ? responseRecord.error_message || responseRecord.message : undefined,
          errorCode: responseRecord.error_code || undefined,
        });
        if (!meta.terminal) pollItem(item.clientId, cvKey, enrichWithLlm);
      } catch (error: any) {
        const queueFull = error?.status === 503 && String(error?.message || '').includes('CV_QUEUE_FULL');
        updateItem(item.clientId, {
          state: 'FAILED',
          message: queueFull ? 'The CV queue is full. Try again after queued work completes.' : error?.message || 'Upload failed.',
          error: queueFull ? 'CV_QUEUE_FULL' : error?.message || 'Upload failed.',
        });
      }
    }
  }, [pollItem, updateItem]);

  const hydrateQueue = useCallback(async function restoreQueue() {
    stopPolling('queue-hydration');
    try {
      const persistedJobs = await cvService.listProcessingJobs();
      if (!mountedRef.current) return;
      const restored = persistedJobs.map((job: CVProcessingJobSummary): CvQueueUploadItem => {
        const state = resolveCvQueueUiState(job as unknown as CVProcessingResponse & Record<string, any>);
        return {
          clientId: `persisted-${job.job_id}`,
          filename: job.filename,
          cvKey: job.cv_key,
          jobId: job.job_id,
          state,
          progress: job.progress,
          message: job.error_message || job.message,
          error: state === 'FAILED' ? job.error_message || job.message : undefined,
          errorCode: job.error_code || undefined,
        };
      });
      setItems((current) => [...current.filter((item) => !item.jobId), ...restored]);
      setHydrationError(null);
      restored.forEach((item) => {
        if (!TERMINAL_STATES.has(item.state) && item.cvKey) pollItem(item.clientId, item.cvKey, false);
      });
    } catch (error: any) {
      if (mountedRef.current) {
        setHydrationError(error?.message || 'Unable to restore the CV processing queue.');
        const timer = setTimeout(() => void restoreQueue(), API_CONFIG.POLL_INTERVAL_MS);
        timersRef.current.set('queue-hydration', timer);
      }
    }
  }, [pollItem, stopPolling]);

  const summary = useMemo(() => items.reduce(
    (counts, item) => {
      counts[item.state] += 1;
      return counts;
    },
    { PENDING: 0, PROCESSING: 0, RETRYING: 0, COMPLETED: 0, FAILED: 0 } as Record<CvQueueUiState, number>,
  ), [items]);

  const clearFinished = useCallback(() => {
    setItems((current) => current.filter((item) => !TERMINAL_STATES.has(item.state)));
  }, []);

  const stopItem = useCallback((clientId: string) => {
    stopPolling(clientId);
    updateItem(clientId, {
      state: 'FAILED',
      message: 'Processing stopped by user.',
      error: 'Processing stopped by user.',
    });
  }, [stopPolling, updateItem]);

  const stopAll = useCallback(() => {
    items.forEach((item) => {
      if (!TERMINAL_STATES.has(item.state)) {
        stopItem(item.clientId);
      }
    });
  }, [items, stopItem]);

  const clearAll = useCallback(() => {
    timersRef.current.forEach((timer) => clearTimeout(timer));
    timersRef.current.clear();
    setItems([]);
  }, []);

  const removeItem = useCallback((clientId: string) => {
    stopPolling(clientId);
    setItems((current) => current.filter((item) => item.clientId !== clientId));
  }, [stopPolling]);

  const reprocessItem = useCallback((clientId: string) => {
    const item = items.find((i) => i.clientId === clientId);
    if (!item || !item.cvKey) return;
    updateItem(clientId, {
      state: 'PROCESSING',
      progress: 10,
      message: 'Re-submitting CV for match analysis...',
      error: undefined,
      errorCode: undefined,
      syncError: undefined,
    });
    pollItem(clientId, item.cvKey, true);
  }, [items, pollItem, updateItem]);

  const reprocessFailed = useCallback(() => {
    items.filter((i) => i.state === 'FAILED' && i.cvKey).forEach((item) => {
      reprocessItem(item.clientId);
    });
  }, [items, reprocessItem]);

  useEffect(() => {
    mountedRef.current = true;
    void hydrateQueue();
    return () => {
      mountedRef.current = false;
      timersRef.current.forEach((timer) => clearTimeout(timer));
      timersRef.current.clear();
    };
  }, [hydrateQueue]);

  return {
    items,
    summary,
    isActive: items.some((item) => !TERMINAL_STATES.has(item.state)),
    uploadFiles,
    clearFinished,
    clearAll,
    stopItem,
    stopAll,
    removeItem,
    reprocessItem,
    reprocessFailed,
    hydrationError,
    refreshQueue: hydrateQueue,
  };
}
