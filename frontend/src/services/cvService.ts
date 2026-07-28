import { apiClient } from './apiClient';
import {
  CandidateMatchAnalysis,
  CVMatchRequest,
  CVProcessingResponse,
  CVUploadResponse,
} from '@/types/api';

export const cvService = {
  /**
   * Upload CV file for basic processing.
   */
  uploadCv: (
    file: { uri: string; name: string; type: string; rawFile?: any },
    candidateId?: string,
    cvId?: string
  ): Promise<CVProcessingResponse> => {
    const additionalFields: Record<string, string> = {};
    if (candidateId) additionalFields.candidate_id = candidateId;
    if (cvId) additionalFields.cv_id = cvId;

    return apiClient.uploadFile<CVProcessingResponse>(
      '/api/cv/upload',
      file,
      additionalFields
    );
  },

  /**
   * Get processing status or final result of a CV job.
   */
  getCvStatus: (
    cvKey: string
  ): Promise<CVUploadResponse | CVProcessingResponse> => {
    return apiClient.get<CVUploadResponse | CVProcessingResponse>(
      `/api/cv/status/${encodeURIComponent(cvKey)}`
    );
  },

  /**
   * Match raw CV text directly against vacancies using rule-based scoring engine.
   */
  matchCvText: (cvText: string): Promise<CandidateMatchAnalysis> => {
    return apiClient.post<CandidateMatchAnalysis>('/api/cv/match', {
      cv_text: cvText,
    } as CVMatchRequest);
  },
};
