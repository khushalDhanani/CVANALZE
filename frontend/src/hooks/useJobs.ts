import { useCallback, useEffect, useState } from 'react';
import { jobsService } from '@/services/jobsService';
import { JobOpening } from '@/types/api';

export function useJobs() {
  const [jobs, setJobs] = useState<JobOpening[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await jobsService.getJobs();
      setJobs(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch job openings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  return { jobs, loading, error, refreshJobs: fetchJobs };
}
