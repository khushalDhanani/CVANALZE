import { apiClient } from './apiClient';
import {
  DomainEquivalentRequest,
  DomainEquivalentResponse,
} from '@/types/api';

export const domainKnowledgeService = {
  getCategories: async (): Promise<string[]> => {
    return apiClient.get<string[]>('/api/domain-knowledge/categories');
  },

  getEquivalents: async (request: DomainEquivalentRequest): Promise<DomainEquivalentResponse> => {
    return apiClient.post<DomainEquivalentResponse>('/api/domain-knowledge/equivalents', request);
  },
};
