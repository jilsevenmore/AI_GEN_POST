import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useCallback } from 'react'
import { jobsApi } from '../api/services'
import type { JobResponse, JobStatus, JobListResponse } from '../api/types'

const POLLING_INTERVAL = 2000 // 2 seconds
const ACTIVE_STATUSES: JobStatus[] = [
  'pending',
  'expanding_prompt',
  'writing_text',
  'generating_image',
  'safety_check',
  'adapting',
  'regenerating',
]

export function useJobPolling(jobId: string | null, enabled: boolean = true) {
  const queryClient = useQueryClient()

  // Query returns AxiosResponse<JobResponse> - we'll extract data in component
  const { data: axiosResponse, isLoading, error, refetch } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.get(jobId!),
    enabled: enabled && !!jobId,
    refetchInterval: (query) => {
      // Poll while job is in active status
      const jobData = query.state.data?.data
      if (!jobData) return false
      return ACTIVE_STATUSES.includes(jobData.status) ? POLLING_INTERVAL : false
    },
    staleTime: 1000,
  })

  const job = axiosResponse?.data

  // Invalidate related queries when job completes
  useEffect(() => {
    if (job && !ACTIVE_STATUSES.includes(job.status)) {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      queryClient.invalidateQueries({ queryKey: ['review', jobId] })
    }
  }, [job?.status, jobId, queryClient])

  return { job, isLoading, error, refetch }
}

export function useJobActions() {
  const queryClient = useQueryClient()

  const cancelJob = useCallback(async (jobId: string) => {
    await jobsApi.cancel(jobId)
    queryClient.invalidateQueries({ queryKey: ['jobs'] })
  }, [queryClient])

  const simulateProgress = useCallback(async (jobId: string) => {
    const response = await jobsApi.simulateProgress(jobId)
    queryClient.invalidateQueries({ queryKey: ['jobs'] })
    return response.data
  }, [queryClient])

  return { cancelJob, simulateProgress }
}

export function useJobsList(params?: { page?: number; page_size?: number; status?: JobStatus }) {
  const { data: axiosResponse, isLoading, error, refetch } = useQuery({
    queryKey: ['jobs', params],
    queryFn: () => jobsApi.list(params),
  })

  const jobList = axiosResponse?.data

  return { 
    jobs: jobList?.jobs || [], 
    total: jobList?.total || 0,
    page: jobList?.page || 1,
    page_size: jobList?.page_size || 20,
    isLoading, 
    error, 
    refetch 
  }
}