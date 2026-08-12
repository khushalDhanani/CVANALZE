import { apiClient } from './apiClient';
import {
  CandidateGraphResponse,
  VacancyGraphResponse,
  SkillGraphResponse,
  RecruitmentAnalyticsGraphResponse,
} from '@/types/api';

export const talentGraphService = {
  getCandidateGraph: async (candidateId: string): Promise<CandidateGraphResponse> => {
    return apiClient.get<CandidateGraphResponse>(`/api/talent-graph/candidate/${candidateId}`);
  },

  getVacancyGraph: async (vacancyId: string): Promise<VacancyGraphResponse> => {
    return apiClient.get<VacancyGraphResponse>(`/api/talent-graph/vacancy/${vacancyId}`);
  },

  getSkillGraph: async (skillName: string): Promise<SkillGraphResponse> => {
    return apiClient.get<SkillGraphResponse>(`/api/talent-graph/skill/${skillName}`);
  },

  getAnalyticsGraph: async (): Promise<RecruitmentAnalyticsGraphResponse> => {
    return apiClient.get<RecruitmentAnalyticsGraphResponse>('/api/talent-graph/analytics');
  },
};
