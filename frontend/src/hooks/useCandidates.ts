import { useCallback, useEffect, useState } from 'react';
import { candidateService } from '@/services/candidateService';
import { CandidateSearchOptions, CandidateSummary } from '@/types/api';

export function useCandidates() {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchMode, setSearchMode] = useState<string>('keyword');
  const [totalFound, setTotalFound] = useState<number>(0);

  const fetchCandidates = useCallback(
    async (options?: CandidateSearchOptions | string) => {
      setLoading(true);
      setError(null);
      try {
        const payload: CandidateSearchOptions =
          typeof options === 'string'
            ? { query: options }
            : options || {};

        const res = await candidateService.searchCandidates(payload);
        setCandidates(res.candidates || []);
        setSearchMode(res.search_mode || 'keyword');
        setTotalFound(res.total_found ?? (res.candidates?.length || 0));
      } catch (err: any) {
        setError(err.message || 'Failed to fetch candidate directory.');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchCandidates();
  }, [fetchCandidates]);

  return {
    candidates,
    loading,
    error,
    searchMode,
    totalFound,
    refreshCandidates: fetchCandidates,
  };
}

