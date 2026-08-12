import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '@/services/apiClient';
import { configService } from '@/services/configService';
import {
  MatchEngineConfigResponse,
  MatchEngineConfigUpdate,
  RuleInventoryResponse,
} from '@/types/api';

export function useMatchConfig() {
  const [config, setConfig] = useState<MatchEngineConfigResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [updating, setUpdating] = useState<boolean>(false);
  const [configurationMissing, setConfigurationMissing] = useState<boolean>(false);
  const [ruleInventory, setRuleInventory] = useState<RuleInventoryResponse | null>(null);
  const [ruleInventoryError, setRuleInventoryError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    setRuleInventoryError(null);
    try {
      const data = await configService.getMatchConfig();
      setConfig(data);
      setConfigurationMissing(false);
      try {
        setRuleInventory(await configService.getRuleInventory());
      } catch (inventoryError: any) {
        setRuleInventory(null);
        setRuleInventoryError(inventoryError.message || 'Failed to load active rules');
      }
    } catch (err: any) {
      setConfig(null);
      setRuleInventory(null);
      if (err instanceof ApiError && err.status === 404) {
        setConfigurationMissing(true);
      } else {
        setConfigurationMissing(false);
        setError(err.message || 'Failed to fetch match engine configuration');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const updateConfig = useCallback(
    async (payload: MatchEngineConfigUpdate) => {
      setUpdating(true);
      setError(null);
      try {
        const updated = await configService.updateMatchConfig(payload);
        setConfig(updated);
        try {
          setRuleInventory(await configService.getRuleInventory());
          setRuleInventoryError(null);
        } catch (inventoryError: any) {
          setRuleInventoryError(inventoryError.message || 'Configuration saved, but active rules could not be refreshed');
        }
        return updated;
      } catch (err: any) {
        setError(err.message || 'Failed to update configuration');
        throw err;
      } finally {
        setUpdating(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  return {
    config,
    loading,
    refreshing,
    updating,
    configurationMissing,
    ruleInventory,
    ruleInventoryError,
    error,
    refreshConfig: () => fetchConfig(true),
    updateConfig,
  };
}
