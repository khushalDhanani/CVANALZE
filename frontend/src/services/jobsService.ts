import { apiClient } from './apiClient';
import { JobOpening, VacancyRecommendationsResponse } from '@/types/api';

export const jobsService = {
  /**
   * Retrieve all active job openings.
   */
  getJobs: (): Promise<JobOpening[]> => {
    return apiClient.get<JobOpening[]>('/api/jobs');
  },

  /**
   * Retrieve specific job opening details by ID.
   */
  getJobById: (jobId: string | number): Promise<JobOpening> => {
    return apiClient.get<JobOpening>(`/api/jobs/${jobId}`);
  },

  /**
   * Fetch AI Recommendations (skill gap insights, candidate supply, talent pools) for vacancy.
   */
  getVacancyRecommendations: (
    vacancyId: string | number
  ): Promise<VacancyRecommendationsResponse> => {
    return apiClient.get<VacancyRecommendationsResponse>(
      `/api/recommendations/vacancy/${encodeURIComponent(String(vacancyId))}`
    );
  },

  /**
   * Invalidate job cache on backend.
   */
  invalidateJobsCache: (): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>('/api/jobs/cache/invalidate');
  },
};

