import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewApi, jobsApi } from '../api/services'
import type { ReviewResponse, RegenerateRequest, ApproveRequest, ContentResponse, Platform, JobResponse, JobStatus } from '../api/types'

const ACTIVE_STATUSES: JobStatus[] = [
  'pending', 'expanding_prompt', 'writing_text',
  'generating_image', 'safety_check', 'adapting', 'regenerating',
]

export function useReview(jobId: string | null) {
  // First, poll the job status to know when generation is complete
  const { data: job, isLoading: jobLoading, error: jobError, refetch: refetchJob } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => {
      if (!jobId) throw new Error('Job ID is required')
      return jobsApi.get(jobId)
    },
    enabled: !!jobId,
    refetchInterval: (query) => {
      const jobData = query.state.data?.data
      if (!jobData) return 2000
      return ACTIVE_STATUSES.includes(jobData.status) ? 2000 : false
    },
    staleTime: 0,
  })

  // Only fetch review content when job is awaiting_review (generation complete)
  const jobData = job?.data
  const isGenerationComplete = jobData && jobData.status === 'awaiting_review'
  const isGenerationFailed = jobData && jobData.status === 'failed'

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['review', jobId],
    queryFn: () => {
      if (!jobId) throw new Error('Job ID is required')
      return reviewApi.get(jobId)
    },
    enabled: !!jobId && isGenerationComplete,
    staleTime: 5000,
  })

  return { 
    review: data?.data,
    job: jobData,
    isLoading: jobLoading || (isGenerationComplete && isLoading),
    error: jobError || error,
    isGenerating: jobData ? ACTIVE_STATUSES.includes(jobData.status) : true,
    isGenerationComplete,
    isGenerationFailed,
    generationProgress: jobData?.progress ?? 0,
    generationStep: jobData?.current_step ?? 'Queued',
    generationError: jobData?.error ?? null,
    refetchJob,
    refetchReview: refetch,
  }
}

export function useRegenerate(jobId: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: RegenerateRequest) => {
      if (!jobId) throw new Error('Job ID is required')
      return reviewApi.regenerate(jobId, data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review', jobId] })
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
    },
  })
}

export function useApprove(jobId: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ApproveRequest) => {
      if (!jobId) throw new Error('Job ID is required')
      return reviewApi.approve(jobId, data)
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['review', jobId] })
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
      // Return the content ID for redirect
      return response.data
    },
  })
}

// Helper to create initial edited texts from platform contents
export function createInitialEditedTexts(platformContents: { platform: Platform; text: string }[]): Record<Platform, string> {
  const initial: Record<Platform, string> = {
    instagram: '',
    facebook: '',
    linkedin: '',
  }
  platformContents.forEach((pc) => {
    initial[pc.platform] = pc.text
  })
  return initial
}