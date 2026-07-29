import { useCallback, useEffect, useState } from 'react';
import { candidateService } from '@/services/candidateService';
import { CandidateSummary } from '@/types/api';

export function useCandidates() {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCandidates = useCallback(async (searchQuery?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await candidateService.getCandidates(searchQuery);
      setCandidates(data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch candidate directory.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCandidates();
  }, [fetchCandidates]);

  return {
    candidates,
    loading,
    error,
    refreshCandidates: fetchCandidates,
  };
}
