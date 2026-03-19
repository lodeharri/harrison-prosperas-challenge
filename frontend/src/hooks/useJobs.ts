import { useState, useCallback, useEffect } from 'react';
import { apiService } from '../services/api';
import type { Job, JobCreateRequest, JobListResponse } from '../types';

export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response: JobListResponse = await apiService.getJobs(page, pageSize);
      setJobs(response.items);
      setTotal(response.total);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { error?: { message?: string } } } };
      setError(axiosError.response?.data?.error?.message || 'Failed to fetch jobs');
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize]);

  const createJob = useCallback(async (data: JobCreateRequest): Promise<boolean> => {
    setError(null);
    try {
      await apiService.createJob(data);
      await fetchJobs();
      return true;
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { error?: { message?: string } } } };
      setError(axiosError.response?.data?.error?.message || 'Failed to create job');
      return false;
    }
  }, [fetchJobs]);

  const updateJobLocally = useCallback((jobId: string, updates: Partial<Job>) => {
    setJobs(prev => prev.map(job => 
      job.job_id === jobId ? { ...job, ...updates } : job
    ));
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  return {
    jobs,
    total,
    page,
    pageSize,
    isLoading,
    error,
    setPage,
    fetchJobs,
    createJob,
    updateJobLocally,
  };
}
