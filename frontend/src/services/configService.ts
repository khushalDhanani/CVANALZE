import { apiClient } from './apiClient';
import {
  MatchEngineConfigResponse,
  MatchEngineConfigUpdate,
} from '@/types/api';

export const configService = {
  /**
   * Retrieve current engine weights & thresholds.
   */
  getMatchConfig: (): Promise<MatchEngineConfigResponse> => {
    return apiClient.get<MatchEngineConfigResponse>('/api/config/match');
  },

  /**
   * Update engine weights & thresholds.
   */
  updateMatchConfig: (
    payload: MatchEngineConfigUpdate
  ): Promise<MatchEngineConfigResponse> => {
    return apiClient.put<MatchEngineConfigResponse>(
      '/api/config/match',
      payload
    );
  },
};
