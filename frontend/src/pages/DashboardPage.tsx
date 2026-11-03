import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Plus, FileText, Image, Clock, CheckCircle, AlertCircle, RefreshCw, Trash2 } from 'lucide-react'
import { jobsApi } from '../api/services'
import type { JobResponse, JobStatus } from '../api/types'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'

const statusConfig: Record<JobStatus, { label: string; icon: React.ComponentType<{ className?: string }>; color: string }> = {
  pending: { label: 'Queued', icon: Clock, color: 'gray' },
  expanding_prompt: { label: 'Expanding prompt', icon: RefreshCw, color: 'blue' },
  writing_text: { label: 'Writing text', icon: FileText, color: 'blue' },
  generating_image: { label: 'Generating image', icon: Image, color: 'purple' },
  safety_check: { label: 'Safety check', icon: AlertCircle, color: 'yellow' },
  adapting: { label: 'Adapting', icon: RefreshCw, color: 'blue' },
  awaiting_review: { label: 'Ready for review', icon: CheckCircle, color: 'green' },
  approved: { label: 'Approved', icon: CheckCircle, color: 'green' },
  regenerating: { label: 'Regenerating', icon: RefreshCw, color: 'blue' },
  publishing: { label: 'Publishing', icon: Image, color: 'purple' },
  published: { label: 'Published', icon: CheckCircle, color: 'green' },
  failed: { label: 'Failed', icon: AlertCircle, color: 'red' },
}

const statusColors: Record<string, string> = {
  gray: 'bg-gray-100 text-gray-700',
  blue: 'bg-blue-100 text-blue-700',
  purple: 'bg-purple-100 text-purple-700',
  yellow: 'bg-yellow-100 text-yellow-700',
  green: 'bg-green-100 text-green-700',
  red: 'bg-red-100 text-red-700',
}

export function DashboardPage() {
  const { data: jobsResponse, isLoading, error, refetch } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.list({ page_size: 20 }),
  })

  const jobs = jobsResponse?.data?.jobs || []

  const getStatusConfig = (status: JobStatus) => statusConfig[status] || statusConfig.pending

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-600 border-t-transparent" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="card p-8 text-center">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-lg font-medium text-gray-900">Failed to load jobs</h2>
        <p className="mt-1 text-gray-500">{(error as Error).message}</p>
        <button
          onClick={() => refetch()}
          className="mt-4 btn-primary"
        >
          Try again
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Manage your AI-generated content</p>
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

      {/* Quick Actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link to="/create/post" className="card p-6 hover:shadow-md transition-shadow">
          <div className="w-12 h-12 rounded-lg bg-primary-100 flex items-center justify-center mb-4">
            <Plus className="h-6 w-6 text-primary-600" />
          </div>
          <h3 className="font-semibold text-gray-900">Create Social Post</h3>
          <p className="mt-1 text-sm text-gray-500">Generate posts for Instagram, Facebook & LinkedIn</p>
        </Link>
        <Link to="/create/blog" className="card p-6 hover:shadow-md transition-shadow">
          <div className="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center mb-4">
            <FileText className="h-6 w-6 text-blue-600" />
          </div>
          <h3 className="font-semibold text-gray-900">Write Blog Post</h3>
          <p className="mt-1 text-sm text-gray-500">Create long-form blog content with images</p>
        </Link>
        <Link to="/library" className="card p-6 hover:shadow-md transition-shadow">
          <div className="w-12 h-12 rounded-lg bg-purple-100 flex items-center justify-center mb-4">
            <Image className="h-6 w-6 text-purple-600" />
          </div>
          <h3 className="font-semibold text-gray-900">Image Library</h3>
          <p className="mt-1 text-sm text-gray-500">Browse and reuse approved images</p>
        </Link>
        <Link to="/brand" className="card p-6 hover:shadow-md transition-shadow">
          <div className="w-12 h-12 rounded-lg bg-green-100 flex items-center justify-center mb-4">
            <FileText className="h-6 w-6 text-green-600" />
          </div>
          <h3 className="font-semibold text-gray-900">Brand Kit</h3>
          <p className="mt-1 text-sm text-gray-500">Manage your brand identity</p>
        </Link>
      </div>

      {/* Recent Jobs */}
      <div className="card">
        <div className="p-6 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Recent Generations</h2>
            <p className="text-sm text-gray-500">{jobs.length} jobs total</p>
          </div>
          <button
            onClick={() => refetch()}
            className="btn-secondary"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
        </div>

        {jobs.length === 0 ? (
          <div className="p-12 text-center">
            <Image className="h-16 w-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No generations yet</h3>
            <p className="mt-1 text-gray-500">Create your first blog post or social post</p>
            <div className="mt-4 flex justify-center gap-3">
              <Link to="/create/post" className="btn-primary">
                <Plus className="h-4 w-4 mr-2" />
                Create Post
              </Link>
              <Link to="/create/blog" className="btn-secondary">
                Write Blog
              </Link>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Progress</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Updated</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {jobs.map((job) => {
                  const config = getStatusConfig(job.status)
                  const Icon = config.icon
                  return (
                    <tr key={job.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div>
                          <p className="text-sm font-medium text-gray-900 truncate max-w-xs">{job.title}</p>
                          <p className="text-xs text-gray-500 truncate max-w-xs">{job.topic}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={clsx('badge', job.type === 'blog' ? 'badge-blue' : 'badge-purple')}>
                          {job.type === 'blog' ? 'Blog' : 'Post'}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={clsx('badge', statusColors[config.color])}>
                          <Icon className="h-3 w-3 mr-1" />
                          {config.label}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="w-24">
                          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary-600 transition-all duration-300"
                              style={{ width: `${job.progress}%` }}
                            />
                          </div>
                          <p className="mt-1 text-xs text-gray-500 text-right">{job.progress}%</p>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {formatDistanceToNow(new Date(job.updated_at), { addSuffix: true })}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {job.status === 'awaiting_review' && (
                            <Link
                              to={`/review/${job.id}`}
                              className="btn-primary text-sm"
                            >
                              Review
                            </Link>
                          )}
                          {['published', 'failed'].includes(job.status) && (
                            <Link
                              to={`/review/${job.id}`}
                              className="btn-secondary text-sm"
                            >
                              View
                            </Link>
                          )}
                          {['pending', 'expanding_prompt', 'writing_text', 'generating_image', 'safety_check', 'adapting', 'regenerating'].includes(job.status) && (
                            <button className="btn-secondary text-sm">
                              <RefreshCw className="h-4 w-4 animate-spin" />
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
        )}
      </div>
    </div>
  )
}