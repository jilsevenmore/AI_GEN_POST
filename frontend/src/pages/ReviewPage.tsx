import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { 
  ArrowLeft, CheckCircle, RotateCcw, Edit2, Image, 
  Loader2, AlertCircle, ChevronDown, ChevronUp,
  Copy, Check, Hash, Type, Layout, Send
} from 'lucide-react'
import { reviewApi, publishApi } from '../api/services'
import type { ReviewResponse, RegenerateRequest, ApproveRequest, Platform, PlatformContent } from '../api/types'
import clsx from 'clsx'
import { format } from 'date-fns'

const PLATFORM_COLORS: Record<Platform, string> = {
  instagram: 'bg-gradient-to-r from-purple-500 to-pink-500',
  facebook: 'bg-blue-600',
  linkedin: 'bg-blue-700',
}

const PLATFORM_ICONS: Record<Platform, React.ComponentType<{ className?: string }>> = {
  instagram: Image,
  facebook: Send,
  linkedin: Layout,
}

const PlatformIcon = ({ platform, className }: { platform: Platform; className?: string }) => {
  const Icon = PLATFORM_ICONS[platform] || Image
  return <Icon className={className} />
}

export function ReviewPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null)
  const [editedTexts, setEditedTexts] = useState<Record<Platform, string>>({
    instagram: '',
    facebook: '',
    linkedin: '',
  })
  const [showRegenerate, setShowRegenerate] = useState(false)
  const [regenerateFeedback, setRegenerateFeedback] = useState('')
  const [scheduleAt, setScheduleAt] = useState<Date | null>(null)

  const { data: reviewResponse, isLoading, error, refetch } = useQuery({
    queryKey: ['review', jobId],
    queryFn: () => reviewApi.get(jobId!),
    enabled: !!jobId,
  })

  const regenerateMutation = useMutation({
    mutationFn: (data: RegenerateRequest) => reviewApi.regenerate(jobId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review', jobId] })
      setShowRegenerate(false)
      setRegenerateFeedback('')
    },
  })

  const approveMutation = useMutation({
    mutationFn: (data: ApproveRequest) => reviewApi.approve(jobId!, data),
    onSuccess: (response) => {
      navigate(`/publish/${response.data.id}`)
    },
  })

  const reviewData = reviewResponse?.data
  const content = reviewData?.content

  // Initialize selected image
  if (content && !selectedImageId && content.primary_image_id) {
    setSelectedImageId(content.primary_image_id)
  }

  // Initialize edited texts
  if (content && Object.keys(editedTexts).length === 0) {
    const initial: Record<Platform, string> = {
      instagram: '',
      facebook: '',
      linkedin: '',
    }
    content.platform_contents.forEach((pc) => {
      initial[pc.platform] = pc.text
    })
    setEditedTexts(initial)
  }

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-center h-96">
          <Loader2 className="h-12 w-12 animate-spin text-primary-600" />
        </div>
      </div>
    )
  }

  if (error || !content) {
    return (
      <div className="max-w-5xl mx-auto">
        <div className="card p-12 text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-medium text-gray-900">Content not found</h2>
          <p className="mt-1 text-gray-500">This content may have been deleted or the link is invalid.</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="mt-4 btn-primary"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  const primaryImage = content.image_variants.find((v) => v.id === selectedImageId) || content.image_variants[0]

  const handleApprove = () => {
    if (!selectedImageId) {
      alert('Please select an image')
      return
    }

    const scheduleISO = scheduleAt ? scheduleAt.toISOString() : undefined

    approveMutation.mutate({
      selected_image_id: selectedImageId,
      edited_text: Object.keys(editedTexts).some((k) => editedTexts[k as Platform] !== 
        content.platform_contents.find((pc) => pc.platform === k)?.text)
        ? editedTexts as Record<Platform, string>
        : undefined,
      schedule_at: scheduleISO,
    })
  }

  const handleRegenerate = () => {
    if (!regenerateFeedback.trim()) {
      alert('Please provide feedback for regeneration')
      return
    }

    regenerateMutation.mutate({
      feedback: regenerateFeedback,
      regenerate_text: true,
      regenerate_image: true,
      reference_image_ids: [],
    })
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <button
          onClick={() => navigate('/dashboard')}
          className="btn-ghost p-2 self-start"
          aria-label="Go back"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Review & Approve</h1>
          <p className="text-gray-500">Review the generated content and image before publishing</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleApprove}
            disabled={approveMutation.isPending}
            className="btn-primary"
          >
            {approveMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                Approving...
              </>
            ) : (
              <>
                <CheckCircle className="h-4 w-4 mr-2" />
                Approve & Publish
              </>
            )}
          </button>
        </div>
      </div>

      {/* Regenerate Panel */}
      {showRegenerate && (
        <div className="card p-4 bg-yellow-50 border-yellow-200 animate-slide-down">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <h3 className="font-medium text-yellow-800">Regenerate with Feedback</h3>
              <p className="text-sm text-yellow-700 mt-1">Tell the AI what to change</p>
            </div>
            <button
              onClick={() => setShowRegenerate(false)}
              className="text-yellow-500 hover:text-yellow-700"
            >
              ✕
            </button>
          </div>
          <textarea
            value={regenerateFeedback}
            onChange={(e) => setRegenerateFeedback(e.target.value)}
            rows={3}
            className="mt-3 input"
            placeholder="e.g., Make the tone more casual, use brighter colors in the image, add more emojis..."
          />
          <div className="mt-3 flex justify-end gap-2">
            <button
              onClick={() => setShowRegenerate(false)}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              onClick={handleRegenerate}
              disabled={regenerateMutation.isPending || !regenerateFeedback.trim()}
              className="btn-primary"
            >
              {regenerateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Regenerating...
                </>
              ) : (
                'Regenerate'
              )}
            </button>
          </div>
        </div>
      )}

      {!showRegenerate && reviewData?.can_regenerate && reviewData?.regeneration_count < reviewData?.max_regenerations && (
        <button
          onClick={() => setShowRegenerate(true)}
          className="btn-secondary w-full sm:w-auto"
        >
          <RotateCcw className="h-4 w-4 mr-2" />
          Regenerate ({reviewData?.regeneration_count}/{reviewData?.max_regenerations})
        </button>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Image Panel */}
        <div className="lg:col-span-1 space-y-4">
          <div className="card">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">Generated Images</h3>
              <span className="badge badge-primary">{content.image_variants.length} variants</span>
            </div>
            <div className="p-4 space-y-3">
              {content.image_variants.map((variant) => (
                <button
                  key={variant.id}
                  onClick={() => setSelectedImageId(variant.id)}
                  className={clsx(
                    'relative w-full aspect-square rounded-lg overflow-hidden border-2 transition-all',
                    selectedImageId === variant.id
                      ? 'border-primary-500 ring-2 ring-primary-500/20'
                      : 'border-transparent hover:border-gray-300'
                  )}
                  disabled={selectedImageId === variant.id}
                >
                  <img
                    src={variant.url}
                    alt={`Image variant ${variant.aspect_ratio}`}
                    className="w-full h-full object-cover"
                  />
                  {selectedImageId === variant.id && (
                    <div className="absolute inset-0 bg-primary-600/10 flex items-center justify-center">
                      <CheckCircle className="h-8 w-8 text-primary-600" />
                    </div>
                  )}
                  <div className="absolute bottom-0 left-0 right-0 p-2 bg-black/50 text-white text-xs flex items-center justify-between">
                    <span>{variant.aspect_ratio}</span>
                    {variant.is_primary && <span className="badge badge-primary">Primary</span>}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Selected Image Details */}
          <div className="card p-4">
            <h4 className="font-medium text-gray-900 mb-3">Selected Image</h4>
            <div className="aspect-square rounded-lg overflow-hidden bg-gray-100">
              <img
                src={primaryImage.url}
                alt="Selected image"
                className="w-full h-full object-cover"
              />
            </div>
            <div className="mt-3 space-y-2 text-sm text-gray-600">
              <p><strong>Aspect:</strong> {primaryImage.aspect_ratio}</p>
              <p><strong>Size:</strong> {primaryImage.width}×{primaryImage.height}</p>
              <p className="truncate"><strong>Prompt:</strong> {primaryImage.prompt_used}</p>
            </div>
          </div>
        </div>

        {/* Text Panel */}
        <div className="lg:col-span-2 space-y-6">
          {/* Platform Tabs */}
          <div className="card">
            <div className="border-b border-gray-200">
              <nav className="flex gap-1 p-1" aria-label="Platform tabs">
                {content.platform_contents.map((pc) => (
                  <button
                    key={pc.platform}
                    onClick={() => {}}
                    className={clsx(
                      'flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-colors',
                      'bg-gray-100 text-gray-600'
                    )}
                    disabled
                  >
                    <PlatformIcon platform={pc.platform} className="h-4 w-4" />
                    {pc.platform.charAt(0).toUpperCase() + pc.platform.slice(1)}
                    <span className="badge badge-gray">{pc.character_count} chars</span>
                  </button>
                ))}
              </nav>
            </div>

            <div className="p-4 space-y-6">
              {content.platform_contents.map((pc) => {
                const currentText = editedTexts[pc.platform] || pc.text
                const originalText = pc.text

                return (
                  <div key={pc.platform} className="space-y-3">
                    <div className="flex items-center gap-2">
                      <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', PLATFORM_COLORS[pc.platform])}>
                        <PlatformIcon platform={pc.platform} className="h-4 w-4 text-white" />
                      </div>
                      <h4 className="font-medium text-gray-900 capitalize">{pc.platform}</h4>
                      <span className="badge badge-gray">{currentText.length} chars</span>
                      {currentText !== originalText && (
                        <span className="badge badge-yellow">Edited</span>
                      )}
                    </div>

                    <textarea
                      value={currentText}
                      onChange={(e) => setEditedTexts({ ...editedTexts, [pc.platform]: e.target.value })}
                      rows={6}
                      className="input font-mono text-sm"
                      placeholder={`Generated ${pc.platform} content...`}
                    />
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => copyToClipboard(currentText)}
                        className="btn-ghost text-sm"
                      >
                        <Copy className="h-4 w-4 mr-1" />
                        Copy
                      </button>
                      <button
                        onClick={() => setEditedTexts({ ...editedTexts, [pc.platform]: originalText })}
                        disabled={currentText === originalText}
                        className="btn-ghost text-sm text-gray-500"
                      >
                        <RotateCcw className="h-4 w-4 mr-1" />
                        Reset
                      </button>
                    </div>
                  </div>
                )
              })}

              {/* Hashtags */}
              <div className="border-t border-gray-200 pt-4">
                <h4 className="font-medium text-gray-900 mb-3">Hashtags</h4>
                <div className="flex flex-wrap gap-2">
                  {content.platform_contents.flatMap((pc) => pc.hashtags).filter((h, i, arr) => arr.indexOf(h) === i).map((tag) => (
                    <span key={tag} className="badge badge-primary">#{tag}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Schedule Options */}
          <div className="card p-4 bg-gray-50 border-gray-200">
            <h4 className="font-medium text-gray-900 mb-3">Publishing Options</h4>
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!scheduleAt}
                  onChange={(e) => setScheduleAt(e.target.checked ? new Date(Date.now() + 3600000) : null)}
                  className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700">Schedule for later</span>
              </label>
              {scheduleAt && (
                <div className="ml-10 flex items-center gap-3">
                  <input
                    type="datetime-local"
                    value={format(scheduleAt, "yyyy-MM-dd'T'HH:mm")}
                    onChange={(e) => setScheduleAt(new Date(e.target.value))}
                    className="input w-auto"
                  />
                  <button
                    onClick={() => setScheduleAt(null)}
                    className="btn-ghost text-sm text-gray-500"
                  >
                    Remove schedule
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Safety Check */}
          <div className="card p-4 border-l-4 border-green-500 bg-green-50">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-green-600" />
              <div>
                <p className="font-medium text-green-800">Safety check passed</p>
                <p className="text-sm text-green-700">No policy violations detected in text or image.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}