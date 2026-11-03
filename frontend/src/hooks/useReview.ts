import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewApi } from '../api/services'
import type { ReviewResponse, RegenerateRequest, ApproveRequest, ContentResponse, Platform } from '../api/types'

export function useReview(jobId: string | null) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['review', jobId],
    queryFn: () => reviewApi.get(jobId!),
    enabled: !!jobId,
    staleTime: 5000,
  })

  return { 
    review: data?.data, 
    isLoading, 
    error, 
    refetch 
  }
}

export function useRegenerate(jobId: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: RegenerateRequest) => reviewApi.regenerate(jobId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review', jobId] })
      queryClient.invalidateQueries({ queryKey: ['job', jobId] })
    },
  })
}

export function useApprove(jobId: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ApproveRequest) => reviewApi.approve(jobId!, data),
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