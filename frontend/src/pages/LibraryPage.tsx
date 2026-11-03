import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Filter, Tag, Plus, Image, Download, Trash2, Globe, Building2 } from 'lucide-react'
import { libraryApi } from '../api/services'
import type { LibraryImageResponse, LibrarySearchRequest, ImageAspectRatio } from '../api/types'
import clsx from 'clsx'

const ASPECT_RATIOS: { value: ImageAspectRatio; label: string }[] = [
  { value: '1:1', label: 'Square (1:1)' },
  { value: '4:5', label: 'Portrait (4:5)' },
  { value: '1.91:1', label: 'Landscape (1.91:1)' },
  { value: '9:16', label: 'Story (9:16)' },
]

export function LibraryPage() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [selectedAspectRatio, setSelectedAspectRatio] = useState<ImageAspectRatio | ''>('')
  const [showGlobalOnly, setShowGlobalOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [selectedImages, setSelectedImages] = useState<string[]>([])

  const { data: searchResponse, isLoading, error } = useQuery({
    queryKey: ['library', searchQuery, selectedTags, selectedAspectRatio, showGlobalOnly, page],
    queryFn: () => libraryApi.search({
      query: searchQuery || undefined,
      tags: selectedTags,
      aspect_ratio: selectedAspectRatio || undefined,
      is_global: showGlobalOnly || undefined,
      page,
      page_size: 20,
    }),
  })

  const { data: popularTags } = useQuery({
    queryKey: ['library', 'tags'],
    queryFn: () => libraryApi.getPopularTags(20),
  })

  const images = searchResponse?.data?.images || []
  const total = searchResponse?.data?.total || 0
  const totalPages = Math.ceil(total / 20)

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) => prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag])
    setPage(1)
  }

  const toggleImageSelection = (imageId: string) => {
    setSelectedImages((prev) => prev.includes(imageId) ? prev.filter((id) => id !== imageId) : [...prev, imageId])
  }

  const selectAllImages = () => {
    if (selectedImages.length === images.length) {
      setSelectedImages([])
    } else {
      setSelectedImages(images.map((img) => img.id))
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Image Library</h1>
          <p className="text-gray-500">Browse and manage your approved images</p>
        </div>
        <button className="btn-primary">
          <Plus className="h-4 w-4 mr-2" />
          Upload Image
        </button>
      </div>

      {/* Search & Filters */}
      <div className="card p-4 space-y-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
              placeholder="Search by prompt, tags..."
              className="input pl-10"
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <select
              value={selectedAspectRatio}
              onChange={(e) => { setSelectedAspectRatio(e.target.value as ImageAspectRatio); setPage(1); }}
              className="input w-auto"
            >
              <option value="">All Aspect Ratios</option>
              {ASPECT_RATIOS.map((ar) => (
                <option key={ar.value} value={ar.value}>{ar.label}</option>
              ))}
            </select>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showGlobalOnly}
                onChange={(e) => { setShowGlobalOnly(e.target.checked); setPage(1); }}
                className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-gray-700">Global only</span>
            </label>
          </div>
        </div>

        {/* Popular Tags */}
        {popularTags?.data && popularTags.data.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <Tag className="h-4 w-4 text-gray-400 mt-1" />
            {popularTags.data.slice(0, 10).map((tag) => (
              <button
                key={tag.name}
                onClick={() => toggleTag(tag.name)}
                className={clsx(
                  'px-3 py-1 rounded-full text-sm transition-colors',
                  selectedTags.includes(tag.name)
                    ? 'bg-primary-100 text-primary-700'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                )}
              >
                {tag.name} <span className="ml-1 opacity-50">({tag.count})</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Results */}
      <div className="card">
        <div className="p-4 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">
              {total} image{total !== 1 ? 's' : ''} found
            </span>
            {selectedImages.length > 0 && (
              <span className="badge badge-primary">
                {selectedImages.length} selected
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <select
              value={page}
              onChange={(e) => setPage(Number(e.target.value))}
              className="input w-auto text-sm py-1"
              disabled={totalPages <= 1}
            >
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                <option key={p} value={p}>Page {p}</option>
              ))}
            </select>
          </div>
        </div>

        {isLoading ? (
          <div className="p-12 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent mx-auto" />
          </div>
        ) : error ? (
          <div className="p-12 text-center text-red-500">Failed to load images</div>
        ) : images.length === 0 ? (
          <div className="p-12 text-center">
            <Image className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No images found</h3>
            <p className="mt-1 text-gray-500">Try adjusting your search or filters</p>
          </div>
        ) : (
          <>
            {/* Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 p-4">
              {images.map((image) => (
                <div
                  key={image.id}
                  className={clsx(
                    'relative group cursor-pointer rounded-lg overflow-hidden bg-gray-100 transition-shadow',
                    selectedImages.includes(image.id) ? 'ring-2 ring-primary-500' : 'hover:shadow-lg'
                  )}
                  onClick={() => toggleImageSelection(image.id)}
                >
                  <div className="aspect-square relative">
                    <img
                      src={image.thumbnail_url || image.url}
                      alt={image.prompt}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                    {image.is_global && (
                      <div className="absolute top-2 right-2">
                        <Globe className="h-4 w-4 text-white bg-black/50 rounded-full p-1" />
                      </div>
                    )}
                    <div className="absolute bottom-2 left-2 right-2 flex justify-between">
                      <span className="badge badge-gray">{image.aspect_ratio}</span>
                      <input
                        type="checkbox"
                        checked={selectedImages.includes(image.id)}
                        onChange={() => toggleImageSelection(image.id)}
                        className="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                    </div>
                  </div>
                  <div className="p-2 space-y-1">
                    <p className="text-xs font-medium text-gray-900 truncate" title={image.prompt}>
                      {image.prompt}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {image.tags.slice(0, 3).map((tag) => (
                        <span key={tag} className="badge badge-gray text-xs">{tag}</span>
                      ))}
                      {image.tags.length > 3 && (
                        <span className="badge badge-gray text-xs">+{image.tags.length - 3}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
                <span className="text-sm text-gray-500">
                  Page {page} of {totalPages}
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="btn-secondary text-sm"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="btn-secondary text-sm"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Bulk Actions */}
      {selectedImages.length > 0 && (
        <div className="fixed bottom-4 right-4 left-4 sm:left-auto sm:w-auto z-50 animate-slide-up">
          <div className="card p-4 shadow-lg max-w-md mx-auto sm:mx-0">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium text-gray-900">
                {selectedImages.length} image{selectedImages.length !== 1 ? 's' : ''} selected
              </h3>
              <button
                onClick={() => setSelectedImages([])}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <div className="flex gap-2">
              <button className="btn-primary flex-1">
                <Tag className="h-4 w-4 mr-2" />
                Edit Tags
              </button>
              <button className="btn-secondary flex-1">
                <Download className="h-4 w-4 mr-2" />
                Download
              </button>
              <button className="btn-danger flex-1">
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}