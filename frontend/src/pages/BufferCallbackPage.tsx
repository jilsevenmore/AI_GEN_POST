import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react'
import { publishApi } from '../api/services'
import { SEO } from '../components/SEO'

export function BufferCallbackPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const attemptedKeyRef = useRef<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const state = params.get('state')
    const errorParam = params.get('error')

    if (errorParam) {
      setError(`Buffer authorization was denied: ${errorParam}`)
      setLoading(false)
      return
    }

    if (!code || !state) {
      setError('Missing authorization code from Buffer')
      setLoading(false)
      return
    }

    const attemptKey = `${code}:${state}`
    if (attemptedKeyRef.current === attemptKey) {
      return
    }
    attemptedKeyRef.current = attemptKey

    publishApi
      .connectBuffer({ code, state })
      .then(() => {
        setSuccess(true)
        setLoading(false)
        setTimeout(() => {
          navigate('/settings')
        }, 1500)
      })
      .catch((err: any) => {
        setError(err?.response?.data?.detail || err?.message || 'Failed to connect Buffer')
        setLoading(false)
      })
  }, [navigate])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <SEO title="Connecting Buffer" description="Completing Buffer authorization." path="/auth/buffer/callback" robots="noindex,nofollow" />
        <div className="text-center">
          <Loader2 className="h-10 w-10 animate-spin text-primary-600 mx-auto mb-4" />
          <h2 className="text-lg font-medium text-gray-900">Connecting to Buffer...</h2>
          <p className="text-sm text-gray-500 mt-1">
            Please wait while we authorize your account.
          </p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <SEO title="Buffer Connection Failed" description="Buffer authorization failed." path="/auth/buffer/callback" robots="noindex,nofollow" />
        <div className="text-center max-w-md px-4">
          <AlertCircle className="h-10 w-10 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-medium text-gray-900">Connection Failed</h2>
          <p className="text-sm text-gray-500 mb-6">{error}</p>
          <button
            onClick={() => navigate('/settings')}
            className="btn-primary"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Settings
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <SEO title="Buffer Connected" description="Buffer account connected successfully." path="/auth/buffer/callback" robots="noindex,nofollow" />
      <div className="text-center max-w-md px-4">
        <CheckCircle className="h-10 w-10 text-green-500 mx-auto mb-4" />
        <h2 className="text-lg font-medium text-gray-900">Buffer Connected!</h2>
        <p className="text-sm text-gray-500 mb-6">
          Your Buffer account has been connected. You can now publish posts to your social channels.
        </p>
        <button
          onClick={() => navigate('/settings')}
          className="btn-primary"
        >
          Go to Settings
        </button>
      </div>
    </div>
  )
}
