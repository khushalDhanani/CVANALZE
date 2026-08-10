import { useCallback, useEffect, useRef, useState } from 'react';
import { batchService } from '@/services/batchService';
import { BatchMatchResponse, BatchProgressMessage } from '@/types/api';

export function useBatchProgress() {
  const [running, setRunning] = useState<boolean>(false);
  const [progress, setProgress] = useState<BatchProgressMessage | null>(null);
  const [result, setResult] = useState<BatchMatchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef<boolean>(false);

  const startBatch = useCallback(async (limit: number = 10) => {
    setRunning(true);
    setError(null);
    setProgress(null);
    setResult(null);
    cancelledRef.current = false;

    try {
      let current = await batchService.matchCandidates(limit);
      setProgress(current);
      while (!['COMPLETED', 'COMPLETED_DEGRADED', 'FAILED'].includes(current.status.toUpperCase())) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        if (cancelledRef.current) return;
        current = await batchService.getBatchJob(current.batch_job_id);
        setProgress(current);
      }
      if (current.status === 'FAILED') {
        throw new Error(current.error || current.message || 'Batch matching failed');
      }
      setResult(current);
    } catch (err: any) {
      setError(err.message || 'Batch matching failed');
    } finally {
      if (!cancelledRef.current) setRunning(false);
    }
  }, []);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
    };
  }, []);

  return {
    running,
    progress,
    result,
    error,
    startBatch,
  };
}
