import { Info, X, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import clsx from 'clsx'

export function FreeModelNotice({ 
  isVisible = true, 
  onDismiss,
  className 
}: { 
  isVisible?: boolean 
  onDismiss?: () => void
  className?: string
}) {
  const [dismissed, setDismissed] = useState(false)

  if (!isVisible || dismissed) return null

  return (
    <div 
      className={clsx(
        'flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg',
        className
      )}
      role="status"
      aria-live="polite"
    >
      <Info className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-amber-800">
            Using Free AI Models
          </p>
          {onDismiss && (
            <button
              onClick={() => { setDismissed(true); onDismiss?.() }}
              className="text-amber-500 hover:text-amber-700 p-1"
              aria-label="Dismiss notice"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <p className="mt-1 text-sm text-amber-700">
          This generation uses free OpenRouter models. Quality may vary. 
          <a 
            href="/settings" 
            className="underline hover:text-amber-900 font-medium"
          >
            Upgrade to OpenAI
          </a> for consistent results.
        </p>
      </div>
    </div>
  )
}

// Banner version for top of page
export function FreeModelBanner({ isVisible = true }: { isVisible?: boolean }) {
  if (!isVisible) return null

  return (
    <div className="bg-amber-50 border-b border-amber-200" role="status">
      <div className="max-w-7xl mx-auto px-4 py-2 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-amber-600" />
            <span className="text-sm font-medium text-amber-800">
              Using free AI models — results may vary.{' '}
              <a href="/settings" className="underline hover:text-amber-900">
                Switch to OpenAI in Settings
              </a>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}