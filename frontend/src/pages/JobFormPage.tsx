import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { ArrowLeft, Sparkles, Loader2 } from 'lucide-react'
import { jobsApi } from '../api/services'
import type { JobCreate, JobType, Platform } from '../api/types'
import clsx from 'clsx'

const jobSchema = z.object({
  title: z.string().min(1, 'Title is required').max(200),
  topic: z.string().min(1, 'Topic is required').max(500),
  tone: z.string().optional(),
  audience: z.string().optional(),
  keywords: z.string().optional(),
  image_description: z.string().optional(),
  platforms: z.array(z.enum(['instagram', 'facebook', 'linkedin'])).default([]),
  use_references: z.boolean().default(true),
})

type JobForm = z.infer<typeof jobSchema>

const PLATFORM_OPTIONS: { value: Platform; label: string; icon: string }[] = [
  { value: 'instagram', label: 'Instagram', icon: '📷' },
  { value: 'facebook', label: 'Facebook', icon: '📘' },
  { value: 'linkedin', label: 'LinkedIn', icon: '💼' },
]

const TONE_OPTIONS = [
  'Professional', 'Friendly', 'Casual', 'Authoritative', 'Conversational',
  'Inspirational', 'Educational', 'Humorous', 'Minimalist', 'Bold',
]

const AUDIENCE_OPTIONS = [
  'General audience', 'Professionals', 'Students', 'Entrepreneurs',
  'Marketers', 'Developers', 'Small business owners', 'C-suite executives',
]

export function JobFormPage() {
  const { type } = useParams<{ type: JobType }>()
  const navigate = useNavigate()
  const jobType = type || 'post'

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<JobForm>({
    resolver: zodResolver(jobSchema),
    defaultValues: {
      platforms: [],
      use_references: true,
      tone: 'Professional',
    },
  })

  const selectedPlatforms = watch('platforms')
  const keywordsInput = watch('keywords')

  const createMutation = useMutation({
    mutationFn: (data: JobCreate) => jobsApi.create(data),
    onSuccess: (response) => {
      navigate(`/review/${response.data.id}`)
    },
  })

  const handlePlatformToggle = (platform: Platform) => {
    const current = selectedPlatforms || []
    if (current.includes(platform)) {
      setValue('platforms', current.filter((p) => p !== platform))
    } else {
      setValue('platforms', [...current, platform])
    }
  }

  const handleKeywordsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setValue('keywords', value)
  }

  const onSubmit = (data: JobForm) => {
    const keywords = data.keywords
      ? data.keywords.split(',').map((k) => k.trim()).filter(Boolean)
      : []

    createMutation.mutate({
      type: jobType,
      title: data.title,
      topic: data.topic,
      tone: data.tone,
      audience: data.audience,
      keywords,
      image_description: data.image_description,
      platforms: data.platforms,
      use_references: data.use_references,
      reference_image_ids: [],
    })
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/dashboard')}
          className="btn-ghost p-2"
          aria-label="Go back"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {jobType === 'blog' ? 'Write Blog Post' : 'Create Social Post'}
          </h1>
          <p className="text-gray-500">
            {jobType === 'blog'
              ? 'Generate a full blog article with matching image'
              : 'Generate posts for Instagram, Facebook & LinkedIn'}
          </p>
        </div>
      </div>

      {/* Progress indicator */}
      <div className="card p-4 bg-primary-50 border-primary-100">
        <div className="flex items-center gap-2 text-primary-700">
          <Sparkles className="h-5 w-5" />
          <span className="font-medium">AI-Powered Generation</span>
          <span className="text-sm text-primary-500">→</span>
          <span className="text-sm">Expand prompt</span>
          <span className="text-sm text-primary-500">→</span>
          <span className="text-sm">Write content</span>
          <span className="text-sm text-primary-500">→</span>
          <span className="text-sm">Generate image</span>
          <span className="text-sm text-primary-500">→</span>
          <span className="text-sm">Review & approve</span>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="card p-6 space-y-6" noValidate>
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Content Details</h2>

          <div>
            <label htmlFor="title" className="label">Title *</label>
            <input
              {...register('title')}
              id="title"
              type="text"
              className="input"
              placeholder={jobType === 'blog' ? 'e.g., "The Future of AI in Content Marketing"' : 'e.g., "Announcing Our New Feature"'}
              disabled={isSubmitting}
              aria-invalid={!!errors.title}
            />
            {errors.title && <p className="mt-1 text-sm text-red-600">{errors.title.message}</p>}
          </div>

          <div>
            <label htmlFor="topic" className="label">What's this about? *</label>
            <textarea
              {...register('topic')}
              id="topic"
              rows={3}
              className="input"
              placeholder={jobType === 'blog'
                ? 'Describe the main topic, key points, and angle...'
                : 'Describe the announcement, event, or message...'}
              disabled={isSubmitting}
              aria-invalid={!!errors.topic}
            />
            {errors.topic && <p className="mt-1 text-sm text-red-600">{errors.topic.message}</p>}
            <p className="mt-1 text-sm text-gray-500">Be specific — the AI uses this to create a detailed brief.</p>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="tone" className="label">Tone</label>
              <select
                {...register('tone')}
                id="tone"
                className="input"
                disabled={isSubmitting}
              >
                {TONE_OPTIONS.map((tone) => (
                  <option key={tone} value={tone}>{tone}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="audience" className="label">Target Audience</label>
              <select
                {...register('audience')}
                id="audience"
                className="input"
                disabled={isSubmitting}
              >
                <option value="">Select audience...</option>
                {AUDIENCE_OPTIONS.map((audience) => (
                  <option key={audience} value={audience}>{audience}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="keywords" className="label">Keywords (comma-separated)</label>
            <input
              {...register('keywords')}
              id="keywords"
              type="text"
              className="input"
              placeholder="AI, content marketing, automation, productivity"
              onChange={handleKeywordsChange}
              disabled={isSubmitting}
            />
            <p className="mt-1 text-sm text-gray-500">Optional: Keywords to include for SEO and relevance.</p>
          </div>
        </div>

        <div className="space-y-4 border-t border-gray-200 pt-6">
          <h2 className="text-lg font-semibold text-gray-900">Image Settings</h2>

          <div>
            <label htmlFor="image_description" className="label">Image Description</label>
            <textarea
              {...register('image_description')}
              id="image_description"
              rows={2}
              className="input"
              placeholder="Describe the image you want (style, colors, composition, elements...)"
              disabled={isSubmitting}
            />
            <p className="mt-1 text-sm text-gray-500">Optional: The AI will create a detailed image prompt from your content.</p>
          </div>

          <div>
            <label className="label">Platforms</label>
            <div className="flex flex-wrap gap-2">
              {PLATFORM_OPTIONS.map((platform) => (
                <button
                  key={platform.value}
                  type="button"
                  onClick={() => handlePlatformToggle(platform.value)}
                  className={clsx(
                    'flex items-center gap-2 px-4 py-2 rounded-lg border-2 text-sm font-medium transition-all',
                    selectedPlatforms.includes(platform.value)
                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                      : 'border-gray-200 text-gray-600 hover:border-gray-300'
                  )}
                  disabled={isSubmitting}
                >
                  <span className="text-lg">{platform.icon}</span>
                  {platform.label}
                </button>
              ))}
            </div>
            {selectedPlatforms.length === 0 && (
              <p className="mt-1 text-sm text-yellow-600">Select at least one platform for publishing.</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              {...register('use_references')}
              id="use_references"
              type="checkbox"
              className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              disabled={isSubmitting}
            />
            <label htmlFor="use_references" className="text-sm text-gray-700">
              Use reference images from library (recommended)
            </label>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3 border-t border-gray-200 pt-6">
          <button
            type="button"
            onClick={() => navigate('/dashboard')}
            className="btn-secondary"
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn-primary"
            disabled={isSubmitting || selectedPlatforms.length === 0}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Starting generation...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                Generate with AI
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}