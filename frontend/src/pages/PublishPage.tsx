import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { 
  ArrowLeft, Send, CheckCircle, AlertCircle, Clock, 
  Loader2, RefreshCw, Calendar, X, ChevronRight
} from 'lucide-react'
import { publishApi } from '../api/services'
import type { ChannelConnection, PublishAttemptResponse, PublishStatus, Platform } from '../api/types'
import clsx from 'clsx'
import { format, formatDistanceToNow } from 'date-fns'

const statusConfig: Record<PublishStatus, { label: string; color: string; icon: React.ComponentType<{ className?: string }> }> = {
  pending: { label: 'Pending', color: 'yellow', icon: Clock },
  sent: { label: 'Published', color: 'green', icon: CheckCircle },
  failed: { label: 'Failed', color: 'red', icon: AlertCircle },
  retrying: { label: 'Retrying', color: 'blue', icon: RefreshCw },
}

const platformColors: Record<Platform, string> = {
  instagram: 'bg-gradient-to-r from-purple-500 to-pink-500',
  facebook: 'bg-blue-600',
  linkedin: 'bg-blue-700',
}

const platformIcons: Record<Platform, React.ComponentType<{ className?: string }>> = {
  instagram: Send,
  facebook: Send,
  linkedin: Send,
}

export function PublishPage() {
  const { contentId } = useParams<{ contentId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [scheduleAt, setScheduleAt] = useState<Date | null>(null)
  const [selectedChannels, setSelectedChannels] = useState<string[]>([])

  const { data: channelsResponse, isLoading: channelsLoading } = useQuery({
    queryKey: ['publish', 'channels'],
    queryFn: () => publishApi.listChannels(),
  })

  const { data: attemptsResponse, isLoading: attemptsLoading } = useQuery({
    queryKey: ['publish', 'attempts', contentId],
    queryFn: () => publishApi.getAttempts(contentId!),
    enabled: !!contentId,
    refetchInterval: 5000,
  })

  const publishMutation = useMutation({
    mutationFn: (data: { content_id: string; channel_ids: string[]; schedule_at?: string }) => 
      publishApi.publish(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publish', 'attempts', contentId] })
      setSelectedChannels([])
      setScheduleAt(null)
    },
  })

  const retryMutation = useMutation({
    mutationFn: (attemptId: string) => publishApi.retry(attemptId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publish', 'attempts', contentId] })
    },
  })

  const channels = channelsResponse?.data || []
  const attempts = attemptsResponse?.data || []

  const handlePublish = () => {
    if (selectedChannels.length === 0) {
      alert('Please select at least one channel')
      return
    }

    publishMutation.mutate({
      content_id: contentId!,
      channel_ids: selectedChannels,
      schedule_at: scheduleAt?.toISOString(),
    })
  }

  const toggleChannel = (channelId: string) => {
    setSelectedChannels((prev) => prev.includes(channelId) 
      ? prev.filter((id) => id !== channelId) 
      : [...prev, channelId]
    )
  }

  const getLatestAttempt = (channelId: string) => {
    return attempts
      .filter((a) => a.channel_id === channelId)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0]
  }

  if (channelsLoading) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-12 w-12 animate-spin text-primary-600" />
        </div>
      </div>
    )
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
          <h1 className="text-2xl font-bold text-gray-900">Publish Content</h1>
          <p className="text-gray-500">Select channels and schedule your post</p>
        </div>
      </div>

      {/* Channel Selection */}
      <div className="card">
        <div className="p-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Select Channels</h2>
          <p className="text-sm text-gray-500">Choose where to publish this content</p>
        </div>
        <div className="p-4 space-y-3">
          {channels.length === 0 ? (
            <div className="text-center py-8">
              <Send className="h-12 w-12 text-gray-300 mx-auto mb-3" />
              <h3 className="font-medium text-gray-900">No channels connected</h3>
              <p className="mt-1 text-gray-500">Connect your social accounts in Settings</p>
              <button className="mt-4 btn-primary" onClick={() => navigate('/settings')}>
                Go to Settings
              </button>
            </div>
          ) : (
            channels.map((channel) => {
              const latestAttempt = getLatestAttempt(channel.id)
              const isSelected = selectedChannels.includes(channel.id)
              const status = latestAttempt?.status

              return (
                <button
                  key={channel.id}
                  onClick={() => toggleChannel(channel.id)}
                  className={clsx(
                    'w-full flex items-center gap-4 p-4 rounded-lg border-2 transition-all',
                    isSelected
                      ? 'border-primary-500 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300'
                  )}
                >
                  <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center', platformColors[channel.platform])}>
                    <platformIcons[channel.platform] className="h-5 w-5 text-white" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">{channel.account_name}</p>
                    <p className="text-sm text-gray-500 capitalize">{channel.platform}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {latestAttempt && (
                      <div className={clsx(
                        'flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
                        status === 'sent' && 'bg-green-100 text-green-700',
                        status === 'failed' && 'bg-red-100 text-red-700',
                        status === 'pending' && 'bg-yellow-100 text-yellow-700',
                        status === 'retrying' && 'bg-blue-100 text-blue-700'
                      )}>
                        <statusConfig[status!]?.icon className="h-3 w-3" />
                        {statusConfig[status!]?.label}
                      </div>
                    )}
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleChannel(channel.id)}
                      className="h-5 w-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                    />
                  </div>
                </button>
              )
            )}
          )}
        </div>
      </div>

      {/* Schedule Options */}
      <div className="card p-4 bg-gray-50 border-gray-200">
        <h3 className="font-medium text-gray-900 mb-3">Publishing Time</h3>
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
              <Calendar className="h-5 w-5 text-gray-400" />
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
                <X className="h-4 w-4" />
                Remove
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Publish Button */}
      <div className="flex justify-end">
        <button
          onClick={handlePublish}
          disabled={publishMutation.isPending || selectedChannels.length === 0}
          className="btn-primary"
        >
          {publishMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Publishing...
            </>
          ) : scheduleAt ? (
            <>
              <Clock className="h-4 w-4 mr-2" />
              Schedule ({selectedChannels.length})
            </>
          ) : (
            <>
              <Send className="h-4 w-4 mr-2" />
              Publish Now ({selectedChannels.length})
            </>
          )}
        </button>
      </div>

      {/* Publishing History */}
      {attempts.length > 0 && (
        <div className="card">
          <div className="p-4 border-b border-gray-200">
            <h2 className="font-semibold text-gray-900">Publishing History</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Channel</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Scheduled</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Published</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Attempts</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {channels.map((channel) => {
                  const channelAttempts = attempts.filter((a) => a.channel_id === channel.id)
                  const latest = channelAttempts[0]
                  const status = latest?.status || 'pending'

                  return (
                    <tr key={channel.id}>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', platformColors[channel.platform])}>
                            <platformIcons[channel.platform] className="h-4 w-4 text-white" />
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">{channel.account_name}</p>
                            <p className="text-sm text-gray-500 capitalize">{channel.platform}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={clsx(
                          'flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
                          status === 'sent' && 'bg-green-100 text-green-700',
                          status === 'failed' && 'bg-red-100 text-red-700',
                          status === 'pending' && 'bg-yellow-100 text-yellow-700',
                          status === 'retrying' && 'bg-blue-100 text-blue-700'
                        )}>
                          <statusConfig[status]?.icon className="h-3 w-3" />
                          {statusConfig[status]?.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {latest?.scheduled_at ? formatDistanceToNow(new Date(latest.scheduled_at), { addSuffix: true }) : '—'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {latest?.published_at ? formatDistanceToNow(new Date(latest.published_at), { addSuffix: true }) : '—'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {channelAttempts.length}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {latest?.status === 'failed' && (
                          <button
                            onClick={() => retryMutation.mutate(latest.id)}
                            disabled={retryMutation.isPending}
                            className="btn-secondary text-sm"
                          >
                            {retryMutation.isPending ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <>
                                <RefreshCw className="h-4 w-4 mr-1" />
                                Retry
                              </>
                            )}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}