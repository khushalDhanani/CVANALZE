import { apiClient } from './apiClient';
import {
  VectorDbStatusResponse,
  VectorDbSyncResponse,
} from '@/types/api';

export const vectorDbService = {
  getStatus: async (): Promise<VectorDbStatusResponse> => {
    return apiClient.get<VectorDbStatusResponse>('/api/vector-db/status');
  },

  syncEmbeddings: async (): Promise<VectorDbSyncResponse> => {
    return apiClient.post<VectorDbSyncResponse>('/api/vector-db/sync');
  },
};
