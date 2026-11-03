import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, FileText, Shield, ExternalLink } from 'lucide-react'
import { clsx } from 'clsx'
import { legalApi } from '../api/services'

export function LegalPage() {
  const { page } = useParams<{ page: 'privacy' | 'terms' }>()
  const navigate = useNavigate()
  const [content, setContent] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchContent = async () => {
      try {
        const response = page === 'privacy' 
          ? await legalApi.getPrivacyMarkdown()
          : await legalApi.getTermsMarkdown()
        setContent(response.data.markdown)
      } catch (err) {
        setError('Failed to load content')
      } finally {
        setIsLoading(false)
      }
    }
    fetchContent()
  }, [page])

  const renderMarkdown = (markdown: string) => {
    // Simple markdown rendering for basic elements
    return markdown
      .split('\n')
      .map((line) => {
        if (line.startsWith('# ')) {
          return <h1 key={line} className="text-3xl font-bold text-gray-900 mt-8 mb-4 pb-2 border-b border-gray-200">{line.slice(2)}</h1>
        }
        if (line.startsWith('## ')) {
          return <h2 key={line} className="text-2xl font-semibold text-gray-900 mt-6 mb-3">{line.slice(3)}</h2>
        }
        if (line.startsWith('**') && line.endsWith('**')) {
          return <p key={line} className="font-medium text-gray-900 mt-2">{line.slice(2, -2)}</p>
        }
        if (line.startsWith('- ')) {
          return <li key={line} className="ml-4 mb-1 text-gray-700">{line.slice(2)}</li>
        }
        if (line.trim() === '') {
          return <br key={line} />
        }
        return <p key={line} className="text-gray-700 mt-2">{line}</p>
      })
  }

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto py-12 text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent mx-auto" />
        <p className="mt-4 text-gray-500">Loading...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto py-12 text-center">
        <FileText className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <h2 className="text-lg font-medium text-gray-900">Failed to load</h2>
        <button onClick={() => navigate('/dashboard')} className="mt-4 btn-primary">
          Back to Dashboard
        </button>
      </div>
    )
  }

  const title = page === 'privacy' ? 'Privacy Policy' : 'Terms of Service'
  const icon = page === 'privacy' ? Shield : FileText
  const IconComponent = icon
  // ...

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/dashboard')} className="btn-ghost p-2" aria-label="Go back">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <div className="flex items-center gap-2">
            <IconComponent className="h-6 w-6 text-primary-600" />
            <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          </div>
          <p className="text-gray-500">Last updated: 2026-11-03 | Version 1.0</p>
        </div>
      </div>

      {/* Content */}
      <div className="card p-6 prose prose-gray max-w-none">
        <div className="whitespace-pre-wrap text-gray-700 leading-relaxed">
          {content.split('\n').map((line, i) => {
            if (line.startsWith('# ')) {
              return <h1 key={i} className="text-3xl font-bold text-gray-900 mt-8 mb-4 pb-2 border-b border-gray-200">{line.slice(2)}</h1>
            }
            if (line.startsWith('## ')) {
              return <h2 key={i} className="text-2xl font-semibold text-gray-900 mt-6 mb-3">{line.slice(3)}</h2>
            }
            if (line.startsWith('**') && line.endsWith('**')) {
              return <p key={i} className="font-medium text-gray-900 mt-2">{line.slice(2, -2)}</p>
            }
            if (line.startsWith('- ')) {
              return <li key={i} className="ml-4 mb-1 text-gray-700">{line.slice(2)}</li>
            }
            if (line.trim() === '') {
              return <br key={i} />
            }
            return <p key={i} className="text-gray-700 mt-2">{line}</p>
          })}
        </div>
      </div>

      {/* Back link */}
      <div className="text-center">
        <button onClick={() => navigate('/dashboard')} className="btn-secondary">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Dashboard
        </button>
      </div>
    </div>
  )
}

import { useState } from 'react'