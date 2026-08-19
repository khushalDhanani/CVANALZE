import { apiClient } from './apiClient';
import {
  ConfigVersionActivatedResponse,
  ConfigVersionCreatedResponse,
  MatchEngineConfigResponse,
  MatchEngineConfigUpdate,
  RuleInventoryResponse,
  RuleConfigJsonSchema,
  UnifiedRuleConfig,
} from '@/types/api';

const getActiveConfig = (): Promise<UnifiedRuleConfig> => {
  return apiClient.get<UnifiedRuleConfig>('/api/config/active');
};

export const toMatchEngineConfig = (config: UnifiedRuleConfig): MatchEngineConfigResponse => {
  const parameters = config.scoring.match.scoring_parameters;
  return {
    MATCH_HIGH_THRESHOLD: parameters.match_high_threshold,
    MATCH_MEDIUM_THRESHOLD: parameters.match_medium_threshold,
    MANDATORY_FAILURE_PENALTY_PER_ITEM: parameters.mandatory_failure_penalty,
    MAX_SCORE_ON_MANDATORY_FAILURE: parameters.max_score_on_failure,
    LLM_SEMANTIC_WEIGHT: parameters.llm_semantic_weight,
    MAX_LLM_BOOST: parameters.max_llm_boost,
    MATCH_COMPONENT_WEIGHTS: parameters.component_weights,
    HIRING_RISK_POLICIES: config.hiring_risks?.policies || {},
  };
};

export const applyMatchUpdate = (
  activeConfig: UnifiedRuleConfig,
  payload: MatchEngineConfigUpdate,
  versionTag: string,
): UnifiedRuleConfig => {
  const current = activeConfig.scoring.match.scoring_parameters;
  return {
    ...activeConfig,
    version: versionTag,
    last_updated: new Date().toISOString(),
    scoring: {
      ...activeConfig.scoring,
      match: {
        ...activeConfig.scoring.match,
        scoring_parameters: {
          ...current,
          match_high_threshold: payload.MATCH_HIGH_THRESHOLD ?? current.match_high_threshold,
          match_medium_threshold: payload.MATCH_MEDIUM_THRESHOLD ?? current.match_medium_threshold,
          mandatory_failure_penalty: payload.MANDATORY_FAILURE_PENALTY_PER_ITEM ?? current.mandatory_failure_penalty,
          max_score_on_failure: payload.MAX_SCORE_ON_MANDATORY_FAILURE ?? current.max_score_on_failure,
          llm_semantic_weight: payload.LLM_SEMANTIC_WEIGHT ?? current.llm_semantic_weight,
          max_llm_boost: payload.MAX_LLM_BOOST ?? current.max_llm_boost,
          component_weights: {
            ...current.component_weights,
            ...payload.MATCH_COMPONENT_WEIGHTS,
          },
        },
      },
    },
    hiring_risks: {
      ...activeConfig.hiring_risks,
      policies: payload.HIRING_RISK_POLICIES ?? activeConfig.hiring_risks?.policies ?? {},
    },
  };
};

export const configService = {
  getRuleConfigSchema: (): Promise<RuleConfigJsonSchema> => {
    return apiClient.get<RuleConfigJsonSchema>('/api/config/schema');
  },

  getSystemDefaultConfig: (): Promise<Record<string, unknown>> => {
    return apiClient.get<Record<string, unknown>>('/api/config/system-default');
  },

  getRuleInventory: (): Promise<RuleInventoryResponse> => {
    return apiClient.get<RuleInventoryResponse>('/api/config/rules');
  },

  initializeConfig: async (payload: Record<string, unknown>): Promise<MatchEngineConfigResponse> => {
    await apiClient.post<ConfigVersionActivatedResponse>('/api/config/initialize', payload);
    return getActiveConfig().then(toMatchEngineConfig);
  },

  /**
   * Retrieve the active versioned rule configuration and map its editable match fields.
   */
  getMatchConfig: (): Promise<MatchEngineConfigResponse> => {
    return getActiveConfig().then(toMatchEngineConfig);
  },

  /**
   * Create and activate a complete new rule configuration version with the edited match fields.
   */
  updateMatchConfig: async (
    payload: MatchEngineConfigUpdate
  ): Promise<MatchEngineConfigResponse> => {
    const activeConfig = await getActiveConfig();
    const versionTag = `ui-${Date.now()}`;
    const nextConfig = applyMatchUpdate(activeConfig, payload, versionTag);
    const createQuery = [
      `version_tag=${encodeURIComponent(versionTag)}`,
      `description=${encodeURIComponent(activeConfig.description)}`,
      'created_by=frontend',
      `audit_reason=${encodeURIComponent('Matching configuration updated from frontend')}`,
    ].join('&');

    await apiClient.post<ConfigVersionCreatedResponse>(
      `/api/config/versions?${createQuery}`,
      nextConfig,
    );
    await apiClient.post<ConfigVersionActivatedResponse>(
      `/api/config/versions/${encodeURIComponent(versionTag)}/activate`,
      { tenant_id: null },
    );
    return getActiveConfig().then(toMatchEngineConfig);
  },
};
