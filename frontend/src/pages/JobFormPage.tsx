import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useState, useCallback } from 'react'
import { ArrowLeft, Sparkles, Loader2, Image, X, Search, Check } from 'lucide-react'
import { jobsApi, libraryApi } from '../api/services'
import type { JobCreate, JobType, Platform, LibraryImageResponse, ImageAspectRatio } from '../api/types'
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

const ASPECT_RATIOS: { value: ImageAspectRatio; label: string }[] = [
  { value: '1:1', label: 'Square (1:1)' },
  { value: '4:5', label: 'Portrait (4:5)' },
  { value: '1.91:1', label: 'Landscape (1.91:1)' },
  { value: '9:16', label: 'Story (9:16)' },
]

// Reference Picker Modal Component
function ReferencePickerModal({
  isOpen,
  onClose,
  selectedIds,
  onToggle,
  searchQuery,
  setSearchQuery,
  selectedTags,
  setSelectedTags,
  aspectRatio,
  setAspectRatio,
  page,
  setPage,
  images,
  isLoading,
  totalPages,
}: {
  isOpen: boolean
  onClose: () => void
  selectedIds: string[]
  onToggle: (id: string) => void
  searchQuery: string
  setSearchQuery: (q: string) => void
  selectedTags: string[]
  setSelectedTags: (tags: string[]) => void
  aspectRatio: string
  setAspectRatio: (ar: string) => void
  page: number
  setPage: (value: number | ((prev: number) => number)) => void
  images: { id: string; url: string; thumbnail_url?: string; prompt: string; tags: string[]; aspect_ratio: string; is_global: boolean }[]
  isLoading: boolean
  totalPages: number
}) {
  if (!isOpen) return null

  const isSelected = (id: string) => selectedIds.includes(id)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-3xl w-full max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Select Reference Images</h2>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">{selectedIds.length} selected</span>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="p-4 border-b border-gray-200 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input type="text" value={searchQuery} onChange={e => { setSearchQuery(e.target.value); setPage(1); }}
              placeholder="Search by prompt, tags..." className="input pl-10" />
          </div>
          <div className="flex flex-wrap gap-2">
            <select value={aspectRatio} onChange={e => { setAspectRatio(e.target.value); setPage(1); }} className="input w-auto">
              <option value="">All Aspect Ratios</option>
              <option value="1:1">Square (1:1)</option>
              <option value="4:5">Portrait (4:5)</option>
              <option value="1.91:1">Landscape (1.91:1)</option>
              <option value="9:16">Story (9:16)</option>
            </select>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : images.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Image className="h-12 w-12 mx-auto mb-2" />
              <p>No images found</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {images.map((image) => (
                <button key={image.id} onClick={() => onToggle(image.id)}
                  className={`relative group cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
                    isSelected(image.id) ? 'ring-2 ring-primary-500 border-primary-500' : 'border-transparent hover:border-gray-300'
                  }`}>
                  <div className="aspect-square relative">
                    <img src={image.thumbnail_url || image.url} alt={image.prompt} className="w-full h-full object-cover" loading="lazy" />
                    {image.is_global && (
                      <span className="absolute top-1 right-1 bg-black/50 text-white text-xs px-1.5 py-0.5 rounded">Global</span>
                    )}
                    {isSelected(image.id) && (
                      <div className="absolute inset-0 bg-primary-600/30 flex items-center justify-center">
                        <Check className="h-8 w-8 text-primary-600" />
                      </div>
                    )}
                  </div>
                  <div className="p-1.5 text-xs text-gray-600 truncate">{image.prompt}</div>
                </button>
              ))}
            </div>
          )}

          {totalPages > 1 && (
            <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
              <span className="text-sm text-gray-500">Page {page} of {totalPages}</span>
              <div className="flex gap-2">
                <button onClick={() => setPage(prev => Math.max(1, prev - 1))} disabled={page === 1} className="btn-secondary text-sm">Previous</button>
                <button onClick={() => setPage(prev => Math.min(totalPages, prev + 1))} disabled={page === totalPages} className="btn-secondary text-sm">Next</button>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-gray-200 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={onClose} className="btn-primary">Done</button>
        </div>
      </div>
    </div>
  )
}

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
  const useReferences = watch('use_references')
  const [selectedReferenceIds, setSelectedReferenceIds] = useState<string[]>([])
  const [showReferencePicker, setShowReferencePicker] = useState(false)
  const [refSearchQuery, setRefSearchQuery] = useState('')
  const [refSelectedTags, setRefSelectedTags] = useState<string[]>([])
  const [refAspectRatio, setRefAspectRatio] = useState<ImageAspectRatio | ''>('')
  const [refPage, setRefPage] = useState(1)

  const createMutation = useMutation({
    mutationFn: (data: JobCreate) => jobsApi.create(data),
    onSuccess: (response) => {
      navigate(`/review/${response.data.id}`)
    },
  })

  const { data: refSearchResponse, isLoading: refLoading } = useQuery({
    queryKey: ['library', 'reference-picker', refSearchQuery, refSelectedTags, refAspectRatio, refPage],
    queryFn: () => libraryApi.search({
      query: refSearchQuery || undefined,
      tags: refSelectedTags,
      aspect_ratio: refAspectRatio || undefined,
      is_global: undefined,
      page: refPage,
      page_size: 12,
    }),
    enabled: showReferencePicker,
  })

  const refImages = refSearchResponse?.data?.images || []
  const refTotalPages = Math.ceil((refSearchResponse?.data?.total || 0) / 12)

  const handlePlatformToggle = (platform: Platform) => {
    const current = selectedPlatforms || []
    if (current.includes(platform)) {
      setValue('platforms', current.filter((p) => p !== platform))
    } else {
      setValue('platforms', [...current, platform])
    }
  }

  const handleKeywordsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValue('keywords', e.target.value)
  }

  const toggleReference = (imageId: string) => {
    setSelectedReferenceIds(prev =>
      prev.includes(imageId) ? prev.filter(id => id !== imageId) : [...prev, imageId]
    )
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
      reference_image_ids: selectedReferenceIds,
    })
  }

  return (
    <>
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/dashboard')} className="btn-ghost p-2" aria-label="Go back">
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

        <form onSubmit={handleSubmit(onSubmit)} className="card p-6 space-y-6" noValidate>
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Content Details</h2>

            <div>
              <label htmlFor="title" className="label">Title *</label>
              <input {...register('title')} id="title" type="text" className="input"
                placeholder={jobType === 'blog' ? 'e.g., "The Future of AI in Content Marketing"' : 'e.g., "Announcing Our New Feature"'}
                disabled={isSubmitting} aria-invalid={!!errors.title} />
              {errors.title && <p className="mt-1 text-sm text-red-600">{errors.title.message}</p>}
            </div>

            <div>
              <label htmlFor="topic" className="label">What's this about? *</label>
              <textarea {...register('topic')} id="topic" rows={3} className="input"
                placeholder={jobType === 'blog' ? 'Describe the main topic, key points, and angle...' : 'Describe the announcement, event, or message...'}
                disabled={isSubmitting} aria-invalid={!!errors.topic} />
              {errors.topic && <p className="mt-1 text-sm text-red-600">{errors.topic.message}</p>}
              <p className="mt-1 text-sm text-gray-500">Be specific — the AI uses this to create a detailed brief.</p>
            </div>

            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="tone" className="label">Tone</label>
                <select {...register('tone')} id="tone" className="input" disabled={isSubmitting}>
                  {TONE_OPTIONS.map((tone) => <option key={tone} value={tone}>{tone}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="audience" className="label">Target Audience</label>
                <select {...register('audience')} id="audience" className="input" disabled={isSubmitting}>
                  <option value="">Select audience...</option>
                  {AUDIENCE_OPTIONS.map((audience) => <option key={audience} value={audience}>{audience}</option>)}
                </select>
              </div>
            </div>

            <div>
              <label htmlFor="keywords" className="label">Keywords (comma-separated)</label>
              <input {...register('keywords')} id="keywords" type="text" className="input"
                placeholder="AI, content marketing, automation, productivity" onChange={handleKeywordsChange} disabled={isSubmitting} />
              <p className="mt-1 text-sm text-gray-500">Optional: Keywords to include for SEO and relevance.</p>
            </div>
          </div>

          <div className="space-y-4 border-t border-gray-200 pt-6">
            <h2 className="text-lg font-semibold text-gray-900">Image Settings</h2>

            <div>
              <label htmlFor="image_description" className="label">Image Description</label>
              <textarea {...register('image_description')} id="image_description" rows={2} className="input"
                placeholder="Describe the image you want (style, colors, composition, elements...)" disabled={isSubmitting} />
              <p className="mt-1 text-sm text-gray-500">Optional: The AI will create a detailed image prompt from your content.</p>
            </div>

            <div>
              <label className="label">Platforms</label>
              <div className="flex flex-wrap gap-2">
                {PLATFORM_OPTIONS.map((platform) => (
                  <button key={platform.value} type="button" onClick={() => handlePlatformToggle(platform.value)}
                    className={clsx('flex items-center gap-2 px-4 py-2 rounded-lg border-2 text-sm font-medium transition-all',
                      selectedPlatforms.includes(platform.value) ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-200 text-gray-600 hover:border-gray-300')} disabled={isSubmitting}>
                  <span className="text-lg">{platform.icon}</span> {platform.label}
                </button>
                ))}
              </div>
              {selectedPlatforms.length === 0 && <p className="mt-1 text-sm text-yellow-600">Select at least one platform for publishing.</p>}
            </div>

            <div className="border-t border-gray-200 pt-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <input {...register('use_references')} id="use_references" type="checkbox"
                    className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" disabled={isSubmitting} />
                  <label htmlFor="use_references" className="text-sm text-gray-700">Use reference images from library</label>
                </div>
                {useReferences && selectedReferenceIds.length > 0 && (
                  <span className="badge badge-primary">{selectedReferenceIds.length} reference{selectedReferenceIds.length !== 1 ? 's' : ''} selected</span>
                )}
              </div>

              {useReferences && (
                <div className="mt-4 space-y-3">
                  {selectedReferenceIds.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {selectedReferenceIds.map((id) => (
                        <span key={id} className="flex items-center gap-1 px-3 py-1 bg-primary-50 text-primary-700 rounded-full text-sm">
                          Reference #{id.slice(0, 8)}
                          <button onClick={() => setSelectedReferenceIds(prev => prev.filter(x => x !== id))} className="ml-1 hover:text-primary-900">✕</button>
                        </span>
                      ))}
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => { setRefPage(1); setShowReferencePicker(true); }}
                    className={clsx('w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 text-sm font-medium transition-colors',
                      'border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50')}
                    disabled={isSubmitting}
                  >
                    <Image className="h-4 w-4" />
                    {selectedReferenceIds.length > 0 ? 'Change References' : 'Select Reference Images'}
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-3 border-t border-gray-200 pt-6">
            <button type="button" onClick={() => navigate('/dashboard')} className="btn-secondary" disabled={isSubmitting}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={isSubmitting || selectedPlatforms.length === 0}>
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

      <ReferencePickerModal
        isOpen={showReferencePicker}
        onClose={() => setShowReferencePicker(false)}
        selectedIds={selectedReferenceIds}
        onToggle={toggleReference}
        searchQuery={refSearchQuery}
        setSearchQuery={setRefSearchQuery}
        selectedTags={refSelectedTags}
        setSelectedTags={setRefSelectedTags}
        aspectRatio={refAspectRatio}
        setAspectRatio={(ar: string) => setRefAspectRatio(ar as ImageAspectRatio | '')}
        page={refPage}
        setPage={setRefPage}
        images={refImages}
        isLoading={refLoading}
        totalPages={refTotalPages}
      />
    </>
  )
}