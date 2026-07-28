import { apiClient } from './apiClient';
import {
  CVMatchRequest,
  CVProcessingResponse,
  EnrichedCandidateAnalysis,
  HRReviewRequest,
  LlmHealthResponse,
  TrainingExample,
} from '@/types/api';

export const matchService = {
  /**
   * Check Ollama LLM availability & configured model.
   */
  getLlmHealth: (): Promise<LlmHealthResponse> => {
    return apiClient.get<LlmHealthResponse>('/api/match/health');
  },

  /**
   * Direct text enriched analysis using semantic LLM.
   */
  analyzeCvText: (cvText: string): Promise<EnrichedCandidateAnalysis> => {
    return apiClient.post<EnrichedCandidateAnalysis>('/api/match/analyze', {
      cv_text: cvText,
    } as CVMatchRequest);
  },

  /**
   * Upload CV for Docling parsing + LLM-enriched semantic matching in background.
   */
  uploadAndAnalyze: (file: {
    uri: string;
    name: string;
    type: string;
    rawFile?: any;
  }): Promise<CVProcessingResponse> => {
    return apiClient.uploadFile<CVProcessingResponse>(
      '/api/match/upload',
      file
    );
  },

  /**
   * Get processing status or result of enriched background match job.
   */
  getMatchStatus: (
    cvKey: string
  ): Promise<EnrichedCandidateAnalysis | CVProcessingResponse> => {
    return apiClient.get<EnrichedCandidateAnalysis | CVProcessingResponse>(
      `/api/match/status/${encodeURIComponent(cvKey)}`
    );
  },

  /**
   * Re-run LLM semantic matching on a previously parsed scan by scan_id.
   */
  reanalyzeScan: (scanId: string): Promise<EnrichedCandidateAnalysis> => {
    return apiClient.post<EnrichedCandidateAnalysis>(
      `/api/match/reanalyze/${encodeURIComponent(scanId)}`
    );
  },

  /**
   * Submit HR feedback / review corrections.
   */
  submitHrReview: (
    payload: HRReviewRequest
  ): Promise<{ status: string; message: string }> => {
    return apiClient.post<{ status: string; message: string }>(
      '/api/match/hr-review',
      payload
    );
  },

  /**
   * Retrieve collected training examples.
   */
  getTrainingData: (
    limit: number = 100
  ): Promise<{ count: number; examples: TrainingExample[] }> => {
    return apiClient.get<{ count: number; examples: TrainingExample[] }>(
      `/api/match/training-data?limit=${limit}`
    );
  },
};
