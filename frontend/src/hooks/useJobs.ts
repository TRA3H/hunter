import { useCallback, useEffect, useState } from "react";
import { jobsApi } from "@/lib/api";
import type { Job, JobFilters, JobListResponse } from "@/types";

export function useJobs(initialFilters?: JobFilters) {
  const [data, setData] = useState<JobListResponse>({ jobs: [], total: 0, page: 1, page_size: 25 });
  const [filters, setFilters] = useState<JobFilters>(initialFilters || {});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async (f?: JobFilters) => {
    setLoading(true);
    setError(null);
    try {
      const result = await jobsApi.list(f || filters);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch jobs");
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const updateFilters = useCallback((newFilters: Partial<JobFilters>) => {
    setFilters((prev) => ({ ...prev, ...newFilters, page: newFilters.page ?? 1 }));
  }, []);

  const refresh = useCallback(() => fetchJobs(), [fetchJobs]);

  return { ...data, filters, updateFilters, loading, error, refresh };
}
