import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Save, Image, Loader2, AlertCircle, CheckCircle, Trash2 } from 'lucide-react'
import { brandApi } from '../api/services'
import type { BrandKitResponse, BrandKitCreate, BrandKitUpdate } from '../api/types'
import clsx from 'clsx'

const brandKitSchema = z.object({
  company_name: z.string().min(1, 'Company name is required'),
  tagline: z.string().optional(),
  address: z.string().optional(),
  primary_color: z.string().regex(/^#[0-9A-Fa-f]{6}$/, 'Invalid color format').optional().or(z.literal('')),
  secondary_color: z.string().regex(/^#[0-9A-Fa-f]{6}$/, 'Invalid color format').optional().or(z.literal('')),
  tone: z.string().optional(),
  use_openai_only: z.boolean().default(false),
})

type BrandKitForm = z.infer<typeof brandKitSchema>

const TONE_OPTIONS = [
  'Professional', 'Friendly', 'Casual', 'Authoritative', 'Conversational',
  'Inspirational', 'Educational', 'Humorous', 'Minimalist', 'Bold',
]

export function BrandKitPage() {
  const queryClient = useQueryClient()
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'details' | 'logo' | 'advanced'>('details')

  const { data: brandResponse, isLoading, error } = useQuery({
    queryKey: ['brand'],
    queryFn: () => brandApi.get(),
  })

  const brand = brandResponse?.data

  const updateMutation = useMutation({
    mutationFn: (data: BrandKitCreate) => brandApi.upsert(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brand'] })
    },
  })

  const uploadLogoMutation = useMutation({
    mutationFn: (file: File) => brandApi.uploadLogo(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brand'] })
      setLogoFile(null)
      setLogoPreview(null)
    },
  })

  const deleteLogoMutation = useMutation({
    mutationFn: () => brandApi.deleteLogo(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brand'] })
    },
  })

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isDirty },
  } = useForm<BrandKitForm>({
    resolver: zodResolver(brandKitSchema),
    defaultValues: {
      company_name: '',
      tagline: '',
      address: '',
      primary_color: '#2563EB',
      secondary_color: '#7C3AED',
      tone: 'Professional',
      use_openai_only: false,
    },
  })

  // Initialize form with brand data
  if (brand) {
    register('company_name', { value: brand.company_name })
    register('tagline', { value: brand.tagline || '' })
    register('address', { value: brand.address || '' })
    register('primary_color', { value: brand.primary_color || '#2563EB' })
    register('secondary_color', { value: brand.secondary_color || '#7C3AED' })
    register('tone', { value: brand.tone || 'Professional' })
    register('use_openai_only', { value: brand.use_openai_only })
  }

  const primaryColor = watch('primary_color') || '#2563EB'
  const secondaryColor = watch('secondary_color') || '#7C3AED'

  const onSubmit = (data: BrandKitForm) => {
    const submitData: BrandKitCreate = {
      company_name: data.company_name,
      tagline: data.tagline || undefined,
      address: data.address || undefined,
      primary_color: data.primary_color || undefined,
      secondary_color: data.secondary_color || undefined,
      tone: data.tone || undefined,
      use_openai_only: data.use_openai_only,
    }
    updateMutation.mutate(submitData)
  }

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (!file.type.startsWith('image/')) {
        alert('Please select an image file')
        return
      }
      if (file.size > 5 * 1024 * 1024) {
        alert('File size must be less than 5MB')
        return
      }
      setLogoFile(file)
      setLogoPreview(URL.createObjectURL(file))
    }
  }

  const handleLogoUpload = () => {
    if (logoFile) {
      uploadLogoMutation.mutate(logoFile)
    }
  }

  const handleDeleteLogo = () => {
    if (confirm('Are you sure you want to remove the logo?')) {
      deleteLogoMutation.mutate()
    }
  }

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-12 w-12 animate-spin text-primary-600" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="card p-8 text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-medium text-gray-900">Failed to load brand kit</h2>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Brand Kit</h1>
        <p className="text-gray-500">Manage your company identity and AI preferences</p>
      </div>

      {/* Tabs */}
      <div className="card">
        <div className="border-b border-gray-200">
          <nav className="flex gap-1 p-1" aria-label="Brand kit tabs">
            {[
              { id: 'details', label: 'Details', icon: null },
              { id: 'logo', label: 'Logo', icon: Image },
              { id: 'advanced', label: 'Advanced', icon: null },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-100'
                )}
              >
                {tab.icon && <tab.icon className="h-4 w-4" />}
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'details' && (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" noValidate>
              <div>
                <label htmlFor="company_name" className="label">Company Name *</label>
                <input
                  {...register('company_name')}
                  id="company_name"
                  type="text"
                  className="input"
                  placeholder="Acme Inc."
                />
                {errors.company_name && <p className="mt-1 text-sm text-red-600">{errors.company_name.message}</p>}
              </div>

              <div>
                <label htmlFor="tagline" className="label">Tagline</label>
                <input
                  {...register('tagline')}
                  id="tagline"
                  type="text"
                  className="input"
                  placeholder="Empowering businesses with AI"
                />
              </div>

              <div>
                <label htmlFor="address" className="label">Address</label>
                <textarea
                  {...register('address')}
                  id="address"
                  rows={2}
                  className="input"
                  placeholder="123 Main St, San Francisco, CA 94102"
                />
                <p className="mt-1 text-sm text-gray-500">Used in generated images (added via code, not AI).</p>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="primary_color" className="label">Primary Color</label>
                  <div className="flex items-center gap-3">
                    <input
                      {...register('primary_color')}
                      id="primary_color"
                      type="color"
                      className="h-10 w-10 rounded-lg border border-gray-300 cursor-pointer"
                    />
                    <input
                      {...register('primary_color')}
                      type="text"
                      className="input flex-1 font-mono"
                      placeholder="#2563EB"
                    />
                  </div>
                </div>

                <div>
                  <label htmlFor="secondary_color" className="label">Secondary Color</label>
                  <div className="flex items-center gap-3">
                    <input
                      {...register('secondary_color')}
                      id="secondary_color"
                      type="color"
                      className="h-10 w-10 rounded-lg border border-gray-300 cursor-pointer"
                    />
                    <input
                      {...register('secondary_color')}
                      type="text"
                      className="input flex-1 font-mono"
                      placeholder="#7C3AED"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label htmlFor="tone" className="label">Default Tone</label>
                <select
                  {...register('tone')}
                  id="tone"
                  className="input"
                >
                  {TONE_OPTIONS.map((tone) => (
                    <option key={tone} value={tone}>{tone}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
                <button
                  type="submit"
                  disabled={updateMutation.isPending || !isDirty}
                  className="btn-primary"
                >
                  {updateMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Changes
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {activeTab === 'logo' && (
            <div className="space-y-6">
              <div className="text-center">
                {logoPreview || brand?.logo_url ? (
                  <div className="relative inline-block">
                    <img
                      src={logoPreview || brand?.logo_url!}
                      alt="Company logo"
                      className="max-w-xs max-h-40 rounded-lg border border-gray-200"
                    />
                    {!logoPreview && brand?.logo_url && (
                      <button
                        onClick={handleDeleteLogo}
                        disabled={deleteLogoMutation.isPending}
                        className="absolute top-2 right-2 p-1 rounded-full bg-red-500 text-white hover:bg-red-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="w-64 h-32 mx-auto rounded-lg border-2 border-dashed border-gray-300 flex flex-col items-center justify-center text-gray-500">
                    <Image className="h-12 w-12 mb-2" />
                    <p>No logo uploaded</p>
                  </div>
                )}
              </div>

              {logoFile && (
                <div className="card p-4 bg-yellow-50 border-yellow-200">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center overflow-hidden">
                        <img src={logoPreview!} alt="Preview" className="w-full h-full object-cover" />
                      </div>
                      <div>
                        <p className="font-medium text-yellow-800">{logoFile.name}</p>
                        <p className="text-sm text-yellow-700">{(logoFile.size / 1024).toFixed(1)} KB</p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => { setLogoFile(null); setLogoPreview(null); }}
                        className="btn-secondary text-sm"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleLogoUpload}
                        disabled={uploadLogoMutation.isPending}
                        className="btn-primary text-sm"
                      >
                        {uploadLogoMutation.isPending ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                            Uploading...
                          </>
                        ) : (
                          'Upload'
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {!logoFile && !logoPreview && !brand?.logo_url && (
                <div className="text-center">
                  <label className="btn-secondary cursor-pointer">
                    <Image className="h-4 w-4 mr-2" />
                    Upload Logo
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleLogoChange}
                      className="hidden"
                    />
                  </label>
                  <p className="mt-2 text-sm text-gray-500">PNG, JPG up to 5MB. Recommended: 512x512px with transparent background.</p>
                </div>
              )}

              {brand?.logo_url && !logoFile && (
                <div className="text-center">
                  <label className="btn-secondary cursor-pointer">
                    <Image className="h-4 w-4 mr-2" />
                    Replace Logo
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleLogoChange}
                      className="hidden"
                    />
                  </label>
                </div>
              )}
            </div>
          )}

          {activeTab === 'advanced' && (
            <div className="space-y-6">
              <div className="card p-4 bg-gray-50 border-gray-200">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center">
                    <CheckCircle className="h-5 w-5 text-primary-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-medium text-gray-900">OpenAI Only Mode</h3>
                    <p className="text-sm text-gray-600 mt-1">
                      When enabled, all AI generation uses OpenAI models instead of free OpenRouter models.
                      This ensures your prompts and brand data are not logged by free model providers.
                    </p>
                  </div>
                </div>
              </div>

              <div>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    {...register('use_openai_only')}
                    type="checkbox"
                    className="h-5 w-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <div>
                    <p className="font-medium text-gray-900">Use OpenAI models only (no free models)</p>
                    <p className="text-sm text-gray-500">Recommended for sensitive brands and regulated industries</p>
                  </div>
                </label>
              </div>

              <div className="card p-4 border-l-4 border-primary-500">
                <h4 className="font-medium text-gray-900 mb-2">How Brand Kit is Used</h4>
                <ul className="space-y-1 text-sm text-gray-600">
                  <li>• Company name, tagline, and tone are injected into every AI prompt</li>
                  <li>• Logo and address are composited onto images via code (not AI) for accuracy</li>
                  <li>• Primary/secondary colors guide image generation style</li>
                  <li>• OpenAI Only mode prevents prompt logging by free model providers</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}