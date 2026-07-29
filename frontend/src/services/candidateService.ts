import { apiClient } from './apiClient';
import { CandidateSummary, CVUploadResponse } from '@/types/api';

export const candidateService = {
  /**
   * Fetch list of candidates with optional search filter.
   */
  getCandidates: (search?: string, limit: number = 50): Promise<CandidateSummary[]> => {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (limit) params.append('limit', String(limit));
    
    const queryStr = params.toString();
    const url = `/api/v1/candidates${queryStr ? `?${queryStr}` : ''}`;
    return apiClient.get<CandidateSummary[]>(url);
  },

  /**
   * Fetch detailed candidate evaluation by ID / scan key.
   */
  getCandidateById: (candidateId: string): Promise<CVUploadResponse> => {
    return apiClient.get<CVUploadResponse>(`/api/v1/candidates/${encodeURIComponent(candidateId)}`);
  },
};
