import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, FileText, Image, Clock, CheckCircle, AlertCircle, RefreshCw, Palette, TrendingUp, Layers, Send } from 'lucide-react'
import { useJobPolling, useJobsList, useJobActions } from '../hooks/useJobs'
import type { JobResponse, JobStatus } from '../api/types'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'
import { SEO } from '../components/SEO'
import { TableRowSkeleton, JobCardSkeleton, QuickActionSkeleton } from '../components/Skeleton'
import { useAuth } from '../hooks/useAuth'

const statusConfig: Record<JobStatus, { label: string; icon: React.ComponentType<{ className?: string }>; color: string }> = {
  pending: { label: 'Queued', icon: Clock, color: 'gray' },
  expanding_prompt: { label: 'Expanding', icon: RefreshCw, color: 'blue' },
  writing_text: { label: 'Writing', icon: FileText, color: 'blue' },
  generating_image: { label: 'Generating', icon: Image, color: 'purple' },
  safety_check: { label: 'Safety check', icon: AlertCircle, color: 'yellow' },
  adapting: { label: 'Adapting', icon: RefreshCw, color: 'blue' },
  awaiting_review: { label: 'Ready for review', icon: CheckCircle, color: 'green' },
  approved: { label: 'Approved', icon: CheckCircle, color: 'green' },
  regenerating: { label: 'Regenerating', icon: RefreshCw, color: 'blue' },
  publishing: { label: 'Publishing', icon: Send, color: 'purple' },
  published: { label: 'Published', icon: CheckCircle, color: 'green' },
  failed: { label: 'Failed', icon: AlertCircle, color: 'red' },
}

const statusColors: Record<string, string> = {
  gray: 'bg-gray-100 text-gray-700',
  blue: 'bg-blue-100 text-blue-700',
  purple: 'bg-purple-100 text-purple-700',
  yellow: 'bg-amber-100 text-amber-700',
  green: 'bg-emerald-100 text-emerald-700',
  red: 'bg-red-100 text-red-700',
}

const ACTIVE_STATUSES: JobStatus[] = [
  'pending', 'expanding_prompt', 'writing_text',
  'generating_image', 'safety_check', 'adapting', 'regenerating',
]

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

export function DashboardPage() {
  const { user } = useAuth()
  const { jobs, total, isLoading, error, refetch } = useJobsList({ page_size: 20 })
  const { cancelJob } = useJobActions()

  const activeJob = jobs.find((j) => ACTIVE_STATUSES.includes(j.status))
  const { job: polledJob } = useJobPolling(activeJob?.id || null, !!activeJob)

  const displayJobs = jobs.map((job) => {
    if (polledJob && polledJob.id === job.id) return polledJob
    return job
  })

  const getStatusConfig = (status: JobStatus) => statusConfig[status] || statusConfig.pending

  // Stats derived from loaded jobs
  const approvedCount = jobs.filter(j => ['approved', 'published'].includes(j.status)).length
  const publishedCount = jobs.filter(j => j.status === 'published').length
  const reviewCount = jobs.filter(j => j.status === 'awaiting_review').length

  const firstName = user?.email?.split('@')[0] ?? 'there'

  if (error) {
    return (
      <div className="card p-8 text-center">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-lg font-medium text-gray-900">Failed to load jobs</h2>
        <p className="mt-1 text-gray-500">{(error as Error).message}</p>
        <button onClick={() => refetch()} className="mt-4 btn-primary">Try again</button>
      </div>
    )
  }

  return (
    <div className="w-full space-y-6 pb-12">
      <SEO title="Dashboard" description="Manage your AI-generated content." path="/dashboard" />

      {/* ── Header with greeting ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 tracking-tight">
            {getGreeting()}, {firstName} 👋
          </h1>
          <p className="text-gray-500 text-sm mt-1">Here's what's happening with your content today.</p>
        </div>
        <div className="flex gap-3">
          <Link to="/create/post" className="btn-primary">
            <Plus className="h-4 w-4 mr-2" />
            Create Post
          </Link>
          <Link to="/create/blog" className="btn-secondary">
            <FileText className="h-4 w-4 mr-2" />
            Write Blog
          </Link>
        </div>
      </div>

      {/* ── Stats row ── */}
      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-5 space-y-2">
              <div className="h-3 w-20 bg-gray-100 rounded animate-pulse" />
              <div className="h-7 w-12 bg-gray-100 rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Generations', value: total, icon: Layers, color: 'text-primary-600', bg: 'bg-primary-50' },
            { label: 'Approved', value: approvedCount, icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-50' },
            { label: 'Published', value: publishedCount, icon: TrendingUp, color: 'text-blue-600', bg: 'bg-blue-50' },
            { label: 'Needs Review', value: reviewCount, icon: AlertCircle, color: 'text-amber-600', bg: 'bg-amber-50' },
          ].map(({ label, value, icon: Icon, color, bg }) => (
            <div key={label} className="card p-5 flex items-center gap-4">
              <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', bg)}>
                <Icon className={clsx('h-5 w-5', color)} />
              </div>
              <div>
                <p className="text-xs text-gray-500 font-medium">{label}</p>
                <p className="text-2xl font-bold text-gray-900">{value}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Quick Actions ── */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <QuickActionSkeleton key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link to="/create/post" className="card-hover p-6 group block">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center mb-4 text-white shadow-md group-hover:scale-110 transition-transform duration-200">
              <Plus className="h-6 w-6" />
            </div>
            <h3 className="font-semibold text-gray-900">Create Social Post</h3>
            <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">Generate posts for Instagram, Facebook & LinkedIn</p>
          </Link>
          <Link to="/create/blog" className="card-hover p-6 group block">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center mb-4 text-white shadow-md group-hover:scale-110 transition-transform duration-200">
              <FileText className="h-6 w-6" />
            </div>
            <h3 className="font-semibold text-gray-900">Write Blog Post</h3>
            <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">Create long-form blog content with matching images</p>
          </Link>
          <Link to="/library" className="card-hover p-6 group block">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-500 to-violet-700 flex items-center justify-center mb-4 text-white shadow-md group-hover:scale-110 transition-transform duration-200">
              <Image className="h-6 w-6" />
            </div>
            <h3 className="font-semibold text-gray-900">Image Library</h3>
            <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">Browse and reuse approved image assets</p>
          </Link>
          <Link to="/brand" className="card-hover p-6 group block">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center mb-4 text-white shadow-md group-hover:scale-110 transition-transform duration-200">
              <Palette className="h-6 w-6" />
            </div>
            <h3 className="font-semibold text-gray-900">Brand Kit</h3>
            <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">Manage identity, colors, tone & OpenAI mode</p>
          </Link>
        </div>
      )}

      {/* ── Recent Jobs ── */}
      <div className="card">
        <div className="px-6 py-5 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Recent Generations</h2>
            <p className="text-sm text-gray-400 mt-0.5">{total} jobs total</p>
          </div>
          <button onClick={() => refetch()} className="btn-secondary text-sm self-start sm:self-auto">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
        </div>

        {isLoading ? (
          <>
            {/* Mobile skeleton */}
            <div className="sm:hidden divide-y divide-gray-50 p-4 space-y-3">
              {[...Array(3)].map((_, i) => <JobCardSkeleton key={i} />)}
            </div>
            {/* Desktop skeleton */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full">
                <tbody className="divide-y divide-gray-50">
                  {[...Array(3)].map((_, i) => <TableRowSkeleton key={i} />)}
                </tbody>
              </table>
            </div>
          </>
        ) : displayJobs.length === 0 ? (
          <div className="p-16 text-center">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-100 to-purple-100 flex items-center justify-center mx-auto mb-4">
              <Plus className="h-8 w-8 text-primary-500" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900">Ready to create?</h3>
            <p className="mt-2 text-gray-500 text-sm max-w-xs mx-auto">Generate your first AI post or blog — it only takes a minute.</p>
            <div className="mt-6 flex justify-center gap-3">
              <Link to="/create/post" className="btn-primary">
                <Plus className="h-4 w-4 mr-2" />
                Create Post
              </Link>
              <Link to="/create/blog" className="btn-secondary">Write Blog</Link>
            </div>
          </div>
        ) : (
          <>
            {/* ── Mobile: card list ── */}
            <div className="sm:hidden divide-y divide-gray-50">
              {displayJobs.map((job) => {
                const config = getStatusConfig(job.status)
                const Icon = config.icon
                const isActive = ACTIVE_STATUSES.includes(job.status)
                return (
                  <div key={job.id} className="p-4 space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-gray-900 truncate">{job.title}</p>
                        <p className="text-xs text-gray-400 truncate mt-0.5">{job.topic}</p>
                      </div>
                      <span className={clsx('badge flex-shrink-0', job.type === 'blog' ? 'badge-blue' : 'badge-purple')}>
                        {job.type === 'blog' ? 'Blog' : 'Post'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={clsx('badge', statusColors[config.color])}>
                        <Icon className="h-3 w-3" />
                        {config.label}
                      </span>
                      <span className="text-xs text-gray-400">
                        {formatDistanceToNow(new Date(job.updated_at), { addSuffix: true })}
                      </span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={clsx('h-full rounded-full', isActive ? 'bg-gradient-to-r from-primary-500 to-primary-600 animate-pulse' : 'bg-gradient-to-r from-primary-500 to-primary-600')}
                        style={{ width: `${job.progress}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">{job.progress}% complete</span>
                      <div className="flex gap-2">
                        {job.status === 'awaiting_review' && (
                          <Link to={`/review/${job.id}`} className="btn-primary text-xs px-3 py-1.5">Review</Link>
                        )}
                        {['approved', 'published', 'failed'].includes(job.status) && (
                          <Link to={`/review/${job.id}`} className="btn-secondary text-xs px-3 py-1.5">View</Link>
                        )}
                        {isActive && (
                          <button className="btn-secondary text-xs px-3 py-1.5" disabled>
                            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* ── Desktop: table ── */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50/60 border-b border-gray-100">
                    <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Title</th>
                    <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Progress</th>
                    <th className="px-6 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Updated</th>
                    <th className="px-6 py-3.5 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {displayJobs.map((job) => {
                    const config = getStatusConfig(job.status)
                    const Icon = config.icon
                    const isActive = ACTIVE_STATUSES.includes(job.status)
                    return (
                      <tr key={job.id} className="hover:bg-gray-50/70 transition-colors duration-100">
                        <td className="px-6 py-4">
                          <div>
                            <p className="text-sm font-medium text-gray-900 truncate max-w-xs">{job.title}</p>
                            <p className="text-xs text-gray-400 truncate max-w-xs mt-0.5">{job.topic}</p>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={clsx('badge', job.type === 'blog' ? 'badge-blue' : 'badge-purple')}>
                            {job.type === 'blog' ? 'Blog' : 'Post'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className={clsx('badge', statusColors[config.color])}>
                            <Icon className="h-3 w-3" />
                            {config.label}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="w-28">
                            <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className={clsx('h-full rounded-full transition-all duration-500', isActive ? 'bg-gradient-to-r from-primary-500 to-primary-600 animate-pulse' : 'bg-gradient-to-r from-primary-500 to-primary-600')}
                                style={{ width: `${job.progress}%` }}
                              />
                            </div>
                            <p className="mt-1 text-xs text-gray-400 text-right">{job.progress}%</p>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">
                          {formatDistanceToNow(new Date(job.updated_at), { addSuffix: true })}
                        </td>
                        <td className="px-6 py-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {job.status === 'awaiting_review' && (
                              <Link to={`/review/${job.id}`} className="btn-primary text-xs px-3 py-1.5">Review</Link>
                            )}
                            {['approved', 'published', 'failed'].includes(job.status) && (
                              <Link to={`/review/${job.id}`} className="btn-secondary text-xs px-3 py-1.5">View</Link>
                            )}
                            {isActive && (
                              <button className="btn-secondary text-xs px-3 py-1.5" disabled>
                                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
