import { apiClient } from './apiClient';

export interface WarmCacheResponse {
  message: string;
  counts: Record<string, number>;
}

export const masterDataService = {
  /**
   * Fetch cached master data job profiles.
   */
  getJobProfiles: (): Promise<any[]> => {
    return apiClient.get<any[]>('/api/master-data/job-profiles');
  },

  /**
   * Fetch cached master data departments.
   */
  getDepartments: (): Promise<any[]> => {
    return apiClient.get<any[]>('/api/master-data/departments');
  },

  /**
   * Fetch cached master data companies.
   */
  getCompanies: (): Promise<any[]> => {
    return apiClient.get<any[]>('/api/master-data/companies');
  },

  /**
   * Fetch cached master data skills.
   */
  getSkills: (): Promise<any[]> => {
    return apiClient.get<any[]>('/api/master-data/skills');
  },

  /**
   * Trigger synchronous background cache warming for all master data.
   */
  warmCache: (): Promise<WarmCacheResponse> => {
    return apiClient.post<WarmCacheResponse>('/api/master-data/warm');
  },
};
