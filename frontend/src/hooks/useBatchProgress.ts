import { useCallback, useEffect, useRef, useState } from 'react';
import { batchService } from '@/services/batchService';
import { BatchMatchResponse, BatchProgressMessage } from '@/types/api';

export function useBatchProgress() {
  const [running, setRunning] = useState<boolean>(false);
  const [progress, setProgress] = useState<BatchProgressMessage | null>(null);
  const [result, setResult] = useState<BatchMatchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [wsDisconnected, setWsDisconnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);

  const startBatch = useCallback(async (limit: number = 10) => {
    setRunning(true);
    setError(null);
    setProgress(null);
    setResult(null);
    setWsDisconnected(false);

    // Connect progress websocket
    wsRef.current = batchService.connectProgressWebSocket(
      (data) => {
        setProgress(data);
      },
      (err) => {
        console.warn('WebSocket progress warning:', err);
        setWsDisconnected(true);
      }
    );

    try {
      const res = await batchService.matchCandidates(limit);
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Batch matching failed');
    } finally {
      setRunning(false);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    }
  }, []);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    running,
    progress,
    result,
    error,
    wsDisconnected,
    startBatch,
  };
}
