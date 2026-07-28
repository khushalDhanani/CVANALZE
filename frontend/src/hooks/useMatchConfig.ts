import { useCallback, useEffect, useState } from 'react';
import { configService } from '@/services/configService';
import {
  MatchEngineConfigResponse,
  MatchEngineConfigUpdate,
} from '@/types/api';

export function useMatchConfig() {
  const [config, setConfig] = useState<MatchEngineConfigResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [updating, setUpdating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await configService.getMatchConfig();
      setConfig(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch match engine configuration');
    } finally {
      setLoading(false);
    }
  }, []);

  const updateConfig = useCallback(
    async (payload: MatchEngineConfigUpdate) => {
      setUpdating(true);
      setError(null);
      try {
        const updated = await configService.updateMatchConfig(payload);
        setConfig(updated);
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
    updating,
    error,
    refreshConfig: fetchConfig,
    updateConfig,
  };
}
