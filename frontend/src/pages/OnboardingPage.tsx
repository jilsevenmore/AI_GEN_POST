import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { 
  ArrowLeft, CheckCircle, Clock, Loader2, AlertCircle, 
  ExternalLink, MessageSquare, Star, Zap, Users, TrendingUp,
  Check, X, ChevronRight, Menu, Heart
} from 'lucide-react'
import { betaApi } from '../api/services'
import type { OnboardingProgressResponse, OnboardingStepResponse } from '../api/types'
import clsx from 'clsx'

const ONBOARDING_STEPS = [
  { key: 'connect_channels', name: 'Connect Social Channels', description: 'Link your Instagram, Facebook, and LinkedIn accounts' },
  { key: 'fill_brand_kit', name: 'Fill Brand Kit', description: 'Add company name, logo, colors, and tone' },
  { key: 'first_post', name: 'Create First Post', description: 'Generate and publish your first AI-powered post' },
]

export function OnboardingPage() {
  const { userId } = useParams<{ userId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [stepTimes, setStepTimes] = useState<Record<string, number>>({})
  const [stepStartTime, setStepStartTime] = useState<Record<string, number>>({})

  const { data: progress, isLoading, error, refetch } = useQuery({
    queryKey: ['beta', 'onboarding', userId],
    queryFn: () => betaApi.getOnboardingProgress(userId!),
    enabled: !!userId,
  })

  const completeMutation = useMutation({
    mutationFn: (stepKey: string) => betaApi.completeOnboardingStep(userId!, stepKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['beta', 'onboarding', userId] })
    },
  })

  // Track time spent on each step
  useEffect(() => {
    if (progress?.data?.steps) {
      progress.data.steps.forEach((step: any) => {
        if (step.completed && !stepTimes[step.step_key]) {
          setStepTimes(prev => ({ ...prev, [step.step_key]: step.time_spent_seconds || 0 }))
        }
      })
    }
  }, [progress])

  useEffect(() => {
    if (!isLoading && progress?.data) {
      const incompleteIndex = progress.data.steps.findIndex((s: any) => !s.completed)
      if (incompleteIndex !== -1) {
        setCurrentStepIndex(incompleteIndex)
        const stepKey = progress.data.steps[incompleteIndex].step_key
        if (!stepStartTime[stepKey]) {
          setStepStartTime(prev => ({ ...prev, [stepKey]: Date.now() }))
        }
      } else {
        setCurrentStepIndex(progress.data.steps.length - 1)
      }
    }
  }, [progress, isLoading])

  const handleCompleteStep = async (stepKey: string) => {
    const timeSpent = stepStartTime[stepKey] ? Math.round((Date.now() - stepStartTime[stepKey]) / 1000) : 0
    try {
      await completeMutation.mutateAsync(stepKey)
      // Move to next step
      const nextIndex = currentStepIndex + 1
      if (nextIndex < ONBOARDING_STEPS.length) {
        setCurrentStepIndex(nextIndex)
        setStepStartTime(prev => ({ ...prev, [ONBOARDING_STEPS[nextIndex].key]: Date.now() }))
      }
    } catch (error) {
      console.error('Failed to complete step:', error)
    }
  }

  const handleSkipStep = async (stepKey: string) => {
    // In a real implementation, you'd call an API to mark as skipped
    const nextIndex = currentStepIndex + 1
    if (nextIndex < ONBOARDING_STEPS.length) {
      setCurrentStepIndex(nextIndex)
      setStepStartTime(prev => ({ ...prev, [ONBOARDING_STEPS[nextIndex].key]: Date.now() }))
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="h-12 w-12 animate-spin text-primary-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto py-12 text-center">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-lg font-medium text-gray-900">Failed to load onboarding</h2>
        <button onClick={() => refetch()} className="mt-4 btn-primary">Try again</button>
      </div>
    )
  }

  const currentStep = progress?.data?.steps[currentStepIndex]
  const allCompleted = progress?.data?.steps.every((s: any) => s.completed)

  if (allCompleted) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center">
        <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-6">
          <CheckCircle className="h-10 w-10 text-green-600" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900">Onboarding Complete! 🎉</h1>
        <p className="mt-2 text-gray-600">You're ready to create your first AI-powered post.</p>
        <button
          onClick={() => navigate('/create/post')}
          className="mt-6 btn-primary"
        >
          <Zap className="h-4 w-4 mr-2" />
          Create First Post
        </button>
      </div>
    )
  }

  if (!currentStep) {
    return (
      <div className="max-w-2xl mx-auto py-12 text-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary-600 mx-auto" />
      </div>
    )
  }

  const stepInfo = ONBOARDING_STEPS.find(s => s.key === currentStep.step_key)
  const progressPercent = progress?.data?.progress_percent || 0

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Progress Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl font-bold text-gray-900">Welcome to AI Gen Post</h1>
            <span className="text-sm text-gray-500">{Math.round(progressPercent)}% complete</span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary-600 transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <p className="mt-2 text-sm text-gray-500 text-center">
            Step {currentStepIndex + 1} of {ONBOARDING_STEPS.length}
          </p>
        </div>

        {/* Step Content */}
        <div className="card p-8">
          <div className="mb-6">
            <div className="flex items-center gap-3 mb-4">
              <div className={clsx(
                'w-12 h-12 rounded-full flex items-center justify-center',
                currentStep.completed ? 'bg-green-100' : 'bg-primary-100'
              )}>
                {currentStep.completed ? (
                  <CheckCircle className="h-6 w-6 text-green-600" />
                ) : (
                  <span className="text-xl font-bold text-primary-600">
                    {currentStepIndex + 1}
                  </span>
                )}
              </div>
              <div>
                <h2 className="text-xl font-semibold text-gray-900">
                  {stepInfo?.name || currentStep.step_name}
                </h2>
                <p className="text-gray-500">{stepInfo?.description || ''}</p>
              </div>
            </div>

            <div className="space-y-4">
              {/* Step-specific content */}
              {currentStep.step_key === 'connect_channels' && (
                <div className="space-y-4">
                  <p className="text-gray-600">Connect your social media accounts to publish directly from AI Gen Post.</p>
                  <a href="/settings" target="_blank" className="btn-primary inline-flex items-center gap-2">
                    <ExternalLink className="h-4 w-4" />
                    Open Settings to Connect Channels
                  </a>
                  <p className="text-sm text-gray-500">After connecting, return here to continue.</p>
                </div>
              )}

              {currentStep.step_key === 'fill_brand_kit' && (
                <div className="space-y-4">
                  <p className="text-gray-600">Set up your brand identity so every post matches your style.</p>
                  <a href="/brand" target="_blank" className="btn-primary inline-flex items-center gap-2">
                    <ExternalLink className="h-4 w-4" />
                    Open Brand Kit
                  </a>
                  <p className="text-sm text-gray-500">Add your logo, colors, and tone, then return here.</p>
                </div>
              )}

              {currentStep.step_key === 'first_post' && (
                <div className="space-y-4">
                  <p className="text-gray-600">Create your first AI-generated post and see the magic happen.</p>
                  <button
                    onClick={() => navigate('/create/post')}
                    className="btn-primary w-full py-3"
                  >
                    <Zap className="h-4 w-4 mr-2" />
                    Create Your First Post
                  </button>
                  <p className="text-sm text-gray-500 text-center">Or try the demo first</p>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3 pt-4 border-t border-gray-200">
                {!currentStep.completed && (
                  <button
                    onClick={() => handleCompleteStep(currentStep.step_key)}
                    className="btn-primary flex-1"
                    disabled={completeMutation.isPending}
                  >
                    {completeMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <>
                        <Check className="h-4 w-4 mr-2" />
                        Mark as Complete
                      </>
                    )}
                  </button>
                )}
                <button
                  onClick={() => handleSkipStep(currentStep.step_key)}
                  className="btn-secondary"
                  disabled={currentStep.completed || completeMutation.isPending}
                >
                  Skip for Now
                </button>
              </div>
            </div>
          </div>

          {/* Step Indicators */}
          <div className="mt-8">
            <div className="flex items-center justify-center gap-2">
              {ONBOARDING_STEPS.map((step, index) => {
                const stepData = progress?.data?.steps.find((s: any) => s.step_key === step.key)
                const isCompleted = stepData?.completed
                const isCurrent = index === currentStepIndex

                return (
                  <div key={step.key} className="flex items-center gap-2">
                    <div className={clsx(
                      'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all',
                      isCompleted ? 'bg-green-500 text-white' :
                      isCurrent ? 'bg-primary-500 text-white' :
                      'bg-gray-200 text-gray-500'
                    )}>
                      {isCompleted ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        index + 1
                      )}
                    </div>
                    {index < ONBOARDING_STEPS.length - 1 && (
                      <div className={clsx(
                        'flex-1 h-1 max-w-xs',
                        isCompleted ? 'bg-green-500' : 'bg-gray-200'
                      )} />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}