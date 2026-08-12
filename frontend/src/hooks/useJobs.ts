import { useCallback, useEffect, useState } from 'react';
import { jobsService, VacancyLoadStatus } from '@/services/jobsService';
import { JobOpening } from '@/types/api';

export function useJobs() {
  const [jobs, setJobs] = useState<JobOpening[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<VacancyLoadStatus | null>(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await jobsService.getJobs();
      setJobs(result.jobs);
      setStatus(result.status);
    } catch (err: any) {
      setJobs([]);
      setStatus(null);
      setError(err.message || 'Failed to fetch job openings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  return { jobs, status, loading, error, refreshJobs: fetchJobs };
}
