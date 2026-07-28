import { API_CONFIG } from '@/constants/config';
import { apiClient } from './apiClient';
import { BatchMatchResponse, BatchProgressMessage } from '@/types/api';

export const batchService = {
  /**
   * Run batch candidate evaluation against active job openings.
   */
  matchCandidates: (limit: number = 10): Promise<BatchMatchResponse> => {
    return apiClient.post<BatchMatchResponse>(
      `/api/batch/match-candidates?limit=${limit}`
    );
  },

  /**
   * Establish WebSocket connection to stream real-time batch progress.
   */
  connectProgressWebSocket: (
    onMessage: (data: BatchProgressMessage) => void,
    onError?: (error: Event) => void,
    onClose?: (event: CloseEvent) => void
  ): WebSocket => {
    const wsBaseUrl = API_CONFIG.BASE_URL.replace(/^http/, 'ws');
    const wsUrl = `${wsBaseUrl}/api/batch/ws/progress`;

    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data: BatchProgressMessage = JSON.parse(event.data);
        onMessage(data);
      } catch (err) {
        onMessage({ status: 'info', message: event.data });
      }
    };

    if (onError) ws.onerror = onError;
    if (onClose) ws.onclose = onClose;

    return ws;
  },
};
