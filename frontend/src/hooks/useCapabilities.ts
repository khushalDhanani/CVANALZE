import { useEffect, useState } from 'react';
import { capabilitiesService } from '@/services/capabilitiesService';
import type { ApplicationCapabilities } from '@/types/capabilities';
import { applyServerPollingCapabilities } from '@/constants/config';

let cachedCapabilities: ApplicationCapabilities | null = null;

export function useCapabilities() {
  const [capabilities, setCapabilities] = useState<ApplicationCapabilities | null>(cachedCapabilities);
  const [loading, setLoading] = useState(cachedCapabilities === null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cachedCapabilities) return;
    let active = true;
    capabilitiesService.get()
      .then((result) => {
        applyServerPollingCapabilities(result.polling.interval_ms, result.polling.max_attempts);
        cachedCapabilities = result;
        if (active) setCapabilities(result);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : 'Capabilities are unavailable.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return { capabilities, loading, error };
}
