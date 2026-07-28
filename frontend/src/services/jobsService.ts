import { apiClient } from './apiClient';
import { JobOpening } from '@/types/api';

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
   * Invalidate job cache on backend.
   */
  invalidateJobsCache: (): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>('/api/jobs/cache/invalidate');
  },
};
