import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API_CONFIG } from '@/constants/config';
import { cvService } from '@/services/cvService';
import { matchService } from '@/services/matchService';
import type { CVProcessingResponse } from '@/types/api';
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
}

const TERMINAL_STATES = new Set<CvQueueUiState>(['COMPLETED', 'FAILED']);

function getResponseKey(response: Record<string, any>): string | undefined {
  return response.cv_key || response.scan_id || response.id;
}

export function useCvQueueUploads() {
  const [items, setItems] = useState<CvQueueUploadItem[]>([]);
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
          message: processingResponse.message || meta.label,
          error: state === 'FAILED' ? processingResponse.message || 'CV processing failed.' : undefined,
        });
        if (!meta.terminal && attempt + 1 < API_CONFIG.MAX_POLL_RETRIES) {
          schedulePoll(clientId, cvKey, enrichWithLlm, attempt + 1, 0);
        } else if (!meta.terminal) {
          timersRef.current.delete(clientId);
          updateItem(clientId, {
            state: 'FAILED',
            message: 'Status polling timed out. The backend may still be processing this CV.',
            error: 'Status polling timed out.',
          });
        } else {
          timersRef.current.delete(clientId);
        }
      } catch (error: any) {
        const nextErrorCount = consecutiveErrors + 1;
        if (nextErrorCount < 5 && attempt + 1 < API_CONFIG.MAX_POLL_RETRIES) {
          schedulePoll(clientId, cvKey, enrichWithLlm, attempt + 1, nextErrorCount);
          return;
        }
        updateItem(clientId, {
          state: 'FAILED',
          message: error?.message || 'Status check failed.',
          error: error?.message || 'Status check failed.',
        });
        timersRef.current.delete(clientId);
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
        const cvKey = getResponseKey(responseRecord);
        if (!cvKey) throw new Error('The upload response did not include a CV tracking key.');
        const state = resolveCvQueueUiState(responseRecord);
        const meta = getCvQueueStateMeta(state);
        updateItem(item.clientId, {
          cvKey,
          jobId: responseRecord.job_id,
          state,
          progress: state === 'COMPLETED' ? 100 : responseRecord.progress || 0,
          message: responseRecord.message || meta.label,
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

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      timersRef.current.forEach((timer) => clearTimeout(timer));
      timersRef.current.clear();
    };
  }, []);

  return {
    items,
    summary,
    isActive: items.some((item) => !TERMINAL_STATES.has(item.state)),
    uploadFiles,
    clearFinished,
  };
}
