import { apiClient } from './apiClient';
import {
  CandidateRecommendationsResponse,
  CandidateSearchOptions,
  CandidateSearchResponse,
  CandidateSummary,
  CVUploadResponse,
  TalentPoolsResponse,
} from '@/types/api';

export const candidateService = {
  /**
   * Enterprise semantic candidate search with vector similarity & structured filters.
   */
  searchCandidates: (
    options: CandidateSearchOptions = {}
  ): Promise<CandidateSearchResponse> => {
    return apiClient.post<CandidateSearchResponse>(
      '/api/v1/candidates/search',
      options
    );
  },

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

  /**
   * Fetch AI Recommendations (skill gaps, certifications, career transitions, talent pools) for candidate.
   */
  getCandidateRecommendations: (
    candidateId: string
  ): Promise<CandidateRecommendationsResponse> => {
    return apiClient.get<CandidateRecommendationsResponse>(
      `/api/recommendations/candidate/${encodeURIComponent(candidateId)}`
    );
  },

  /**
   * Trigger cache invalidation and reprocess CV from scratch.
   */
  reprocessCandidate: (candidateId: string): Promise<{ cv_key: string; status: string; message: string; progress: number }> => {
    return apiClient.post<{ cv_key: string; status: string; message: string; progress: number }>(
      `/api/v1/candidates/${encodeURIComponent(candidateId)}/reprocess`,
      {}
    );
  },

  /**
   * Fetch internal talent pools grouped by department and skills.
   */
  getTalentPools: (): Promise<TalentPoolsResponse> => {
    return apiClient.get<TalentPoolsResponse>('/api/recommendations/talent-pools');
  },
};


