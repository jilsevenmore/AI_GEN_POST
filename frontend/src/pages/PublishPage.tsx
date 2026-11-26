import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { 
  ArrowLeft, Send, CheckCircle, AlertCircle, Clock, 
  Loader2, RefreshCw, Calendar, X, Check, Share2, Sparkles, CheckSquare, MinusCircle
} from 'lucide-react'
import { publishApi } from '../api/services'
import type { ChannelConnection, PublishAttemptResponse, PublishStatus, Platform } from '../api/types'
import clsx from 'clsx'
import { format, formatDistanceToNow, addHours, addDays, setHours, setMinutes } from 'date-fns'
import { PlatformIcon, platformColors, platformBadgeColors } from '../components/PlatformIcon'
import { SEO } from '../components/SEO'

const statusConfig: Record<PublishStatus, { label: string; color: string; icon: React.ComponentType<{ className?: string }> }> = {
  pending: { label: 'Pending', color: 'yellow', icon: Clock },
  sent: { label: 'Published', color: 'green', icon: CheckCircle },
  failed: { label: 'Failed', color: 'red', icon: AlertCircle },
  retrying: { label: 'Retrying', color: 'blue', icon: RefreshCw },
}

const StatusIcon = ({ status }: { status: PublishStatus }) => {
  const config = statusConfig[status]
  return <config.icon className="h-3 w-3" />
}

interface ChannelListProps {
  channels: ChannelConnection[]
  selectedChannels: string[]
  onToggleChannel: (channelId: string) => void
  getLatestAttempt: (channelId: string) => PublishAttemptResponse | undefined
}

const isChannelLocked = (attempt?: PublishAttemptResponse) =>
  attempt?.status === 'sent' || attempt?.status === 'pending' || attempt?.status === 'retrying'

const ChannelList = ({ channels, selectedChannels, onToggleChannel, getLatestAttempt }: ChannelListProps) => (
  <div className="space-y-2.5">
    {channels.map((channel) => {
      const latestAttempt = getLatestAttempt(channel.id)
      const isSelected = selectedChannels.includes(channel.id)
      const status = latestAttempt?.status
      const isLocked = isChannelLocked(latestAttempt)

      return (
        <button
          key={channel.id}
          type="button"
          disabled={isLocked}
          onClick={() => !isLocked && onToggleChannel(channel.id)}
          className={clsx(
            'group w-full text-left flex items-center justify-between p-3.5 sm:p-4 rounded-xl border transition-all duration-150',
            isLocked
              ? 'border-gray-200 bg-gray-50/60 opacity-80 cursor-not-allowed'
              : isSelected
              ? 'border-primary-500 bg-primary-50/50 shadow-xs ring-1 ring-primary-500/20'
              : 'border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50/70 hover:shadow-xs'
          )}
        >
          {/* Left: Platform Icon & Channel Name */}
          <div className="flex items-center gap-3.5 min-w-0">
            <div className={clsx(
              'w-11 h-11 rounded-xl flex items-center justify-center shadow-xs flex-shrink-0 transition-transform group-hover:scale-105',
              platformColors[channel.platform] || 'bg-gray-700 text-white'
            )}>
              <PlatformIcon platform={channel.platform} className="h-5 w-5 text-white" />
            </div>
            <div className="min-w-0 text-left">
              <div className="flex items-center gap-2">
                <p className="font-semibold text-gray-900 text-sm sm:text-base truncate">
                  {channel.account_name}
                </p>
                <span className={clsx(
                  'px-2 py-0.5 rounded-full text-xs font-medium border capitalize',
                  platformBadgeColors[channel.platform] || 'bg-gray-100 text-gray-700 border-gray-200'
                )}>
                  {channel.platform}
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">
                Connected {formatDistanceToNow(new Date(channel.connected_at), { addSuffix: true })}
              </p>
            </div>
          </div>

          {/* Right: Status badge & Checkbox */}
          <div className="flex items-center gap-3 ml-3 flex-shrink-0">
            {latestAttempt ? (
              <div className={clsx(
                'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border',
                status === 'sent' && 'bg-emerald-50 text-emerald-700 border-emerald-200',
                status === 'failed' && 'bg-red-50 text-red-700 border-red-200',
                status === 'pending' && 'bg-amber-50 text-amber-700 border-amber-200',
                status === 'retrying' && 'bg-blue-50 text-blue-700 border-blue-200'
              )}>
                <StatusIcon status={status!} />
                <span>{statusConfig[status!]?.label}</span>
              </div>
            ) : (
              <div className={clsx(
                'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border',
                isSelected
                  ? 'bg-primary-50 text-primary-700 border-primary-200'
                  : 'bg-gray-100 text-gray-500 border-gray-200'
              )}>
                {isSelected ? (
                  <>
                    <Check className="h-3 w-3" />
                    <span>Selected</span>
                  </>
                ) : (
                  <>
                    <MinusCircle className="h-3 w-3" />
                    <span>Not Selected</span>
                  </>
                )}
              </div>
            )}

            {!isLocked && (
              <div className={clsx(
                'w-5 h-5 rounded-md border flex items-center justify-center transition-all duration-150',
                isSelected
                  ? 'bg-primary-600 border-primary-600 text-white shadow-xs'
                  : 'border-gray-300 bg-white group-hover:border-primary-400'
              )}>
                {isSelected && <Check className="h-3.5 w-3.5 stroke-[3]" />}
              </div>
            )}
          </div>
        </button>
      )
    })}
  </div>
)

export function PublishPage() {
  const { contentId } = useParams<{ contentId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [scheduleMode, setScheduleMode] = useState<'now' | 'later'>('now')
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
    refetchInterval: (query) => {
      const items = query.state.data?.data
      if (!items || items.length === 0) return false
      return items.some((a) => a.status === 'pending' || a.status === 'retrying') ? 5000 : false
    },
  })

  const publishMutation = useMutation({
    mutationFn: (data: { content_id: string; channel_ids: string[]; schedule_at?: string }) =>
      scheduleMode === 'later'
        ? publishApi.schedule(data)
        : publishApi.publish(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publish', 'attempts', contentId] })
      setSelectedChannels([])
      setScheduleAt(null)
      setScheduleMode('now')
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

  const getLatestAttempt = (channelId: string) => {
    const channelAttempts = attempts
      .filter((a) => a.channel_id === channelId)
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    // Prefer a succeeded ('sent') attempt so a later duplicate/retry failure doesn't mask a live post
    return channelAttempts.find((a) => a.status === 'sent') ?? channelAttempts[0]
  }

  const selectableChannels = channels.filter((c) => !isChannelLocked(getLatestAttempt(c.id)))

  const handlePublish = () => {
    if (selectedChannels.length === 0) {
      alert('Please select at least one channel to publish to.')
      return
    }

    publishMutation.mutate({
      content_id: contentId!,
      channel_ids: selectedChannels,
      schedule_at: scheduleMode === 'later' && scheduleAt ? scheduleAt.toISOString() : undefined,
    })
  }

  const toggleChannel = (channelId: string) => {
    setSelectedChannels((prev) => prev.includes(channelId) 
      ? prev.filter((id) => id !== channelId) 
      : [...prev, channelId]
    )
  }

  const handleSelectAllToggle = () => {
    if (selectableChannels.length === 0) return
    if (selectedChannels.length === selectableChannels.length) {
      setSelectedChannels([])
    } else {
      setSelectedChannels(selectableChannels.map((c) => c.id))
    }
  }

  const setPresetTime = (preset: '1h' | '3h' | 'tomorrow_morning' | 'tomorrow_evening') => {
    const now = new Date()
    let target = new Date()
    if (preset === '1h') target = addHours(now, 1)
    if (preset === '3h') target = addHours(now, 3)
    if (preset === 'tomorrow_morning') target = setMinutes(setHours(addDays(now, 1), 9), 0)
    if (preset === 'tomorrow_evening') target = setMinutes(setHours(addDays(now, 1), 18), 0)
    setScheduleAt(target)
  }

  if (channelsLoading) {
    return (
      <div className="w-full">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-10 w-10 animate-spin text-primary-600" />
        </div>
      </div>
    )
  }

  return (
    <div className="w-full space-y-6 pb-12">
      <SEO title="Publish Content" description="Publish approved content to connected channels." path={contentId ? `/publish/${contentId}` : '/publish'} robots="noindex,nofollow" />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/dashboard')}
            className="p-2 rounded-xl text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition-colors"
            aria-label="Go back"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 tracking-tight">Publish Content</h1>
            <p className="text-sm text-gray-500">Choose connected channels and schedule your multi-platform release</p>
          </div>
        </div>

        {contentId && (
          <div className="flex items-center gap-2 text-xs font-mono text-gray-500 bg-gray-100 px-3 py-1.5 rounded-lg self-start sm:self-auto">
            <span>Content ID:</span>
            <span className="font-semibold text-gray-700">{contentId.slice(0, 8)}...</span>
          </div>
        )}
      </div>

      {/* Responsive 2-column layout on Desktop, 1-column on Mobile/Tablet */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Channels (7 cols on lg) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="card p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100">
              <div>
                <h2 className="font-semibold text-gray-900 text-base">Select Channels</h2>
                <p className="text-xs text-gray-500">Target accounts synced via Buffer</p>
              </div>
              {channels.length > 0 && (
                <div className="flex items-center gap-3">
                  <span className="text-xs font-medium text-gray-500 hidden sm:inline">
                    {selectedChannels.length} of {channels.length} selected
                  </span>
                  {selectableChannels.length > 0 && (
                    <button
                      type="button"
                      onClick={handleSelectAllToggle}
                      className="text-xs font-semibold text-primary-600 hover:text-primary-700 bg-primary-50 px-2.5 py-1 rounded-lg transition-colors"
                    >
                      {selectedChannels.length === selectableChannels.length ? 'Deselect All' : 'Select All'}
                    </button>
                  )}
                </div>
              )}
            </div>

            {channels.length === 0 ? (
              <div className="text-center py-10">
                <Share2 className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                <h3 className="font-medium text-gray-900">No channels connected</h3>
                <p className="mt-1 text-sm text-gray-500 mb-4">Connect your Buffer account in Settings to publish to Instagram, Facebook, and LinkedIn</p>
                <button className="btn-primary" onClick={() => navigate('/settings')}>
                  Connect Channels in Settings
                </button>
              </div>
            ) : (
              <ChannelList
                channels={channels}
                selectedChannels={selectedChannels}
                onToggleChannel={toggleChannel}
                getLatestAttempt={getLatestAttempt}
              />
            )}
          </div>
        </div>

        {/* Right Column: Schedule & Action (5 cols on lg) */}
        <div className="lg:col-span-5 space-y-6 lg:sticky lg:top-20">
          {/* Scheduling Card */}
          <div className="card p-5 sm:p-6 space-y-4">
            <div>
              <h3 className="font-semibold text-gray-900 text-base">Publishing Schedule</h3>
              <p className="text-xs text-gray-500">Deliver instantly or queue for optimal engagement</p>
            </div>

            {/* Mode Toggle */}
            <div className="grid grid-cols-2 gap-2 p-1 bg-gray-100 rounded-xl">
              <button
                type="button"
                onClick={() => { setScheduleMode('now'); setScheduleAt(null); }}
                className={clsx(
                  'flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-all',
                  scheduleMode === 'now'
                    ? 'bg-white text-gray-900 shadow-xs'
                    : 'text-gray-500 hover:text-gray-900'
                )}
              >
                <Send className="h-4 w-4" />
                Publish Now
              </button>
              <button
                type="button"
                onClick={() => { 
                  setScheduleMode('later'); 
                  if (!scheduleAt) setPresetTime('1h');
                }}
                className={clsx(
                  'flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-all',
                  scheduleMode === 'later'
                    ? 'bg-white text-gray-900 shadow-xs'
                    : 'text-gray-500 hover:text-gray-900'
                )}
              >
                <Clock className="h-4 w-4" />
                Schedule Later
              </button>
            </div>

            {/* Schedule Details */}
            {scheduleMode === 'later' && (
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl space-y-3 animate-slide-down">
                <label className="block text-xs font-semibold text-gray-700">Quick Presets</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setPresetTime('1h')}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white border border-gray-200 text-gray-700 hover:border-primary-400 hover:text-primary-600 transition-colors shadow-xs"
                  >
                    In 1 Hour
                  </button>
                  <button
                    type="button"
                    onClick={() => setPresetTime('3h')}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white border border-gray-200 text-gray-700 hover:border-primary-400 hover:text-primary-600 transition-colors shadow-xs"
                  >
                    In 3 Hours
                  </button>
                  <button
                    type="button"
                    onClick={() => setPresetTime('tomorrow_morning')}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white border border-gray-200 text-gray-700 hover:border-primary-400 hover:text-primary-600 transition-colors shadow-xs"
                  >
                    Tomorrow 9:00 AM
                  </button>
                  <button
                    type="button"
                    onClick={() => setPresetTime('tomorrow_evening')}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white border border-gray-200 text-gray-700 hover:border-primary-400 hover:text-primary-600 transition-colors shadow-xs"
                  >
                    Tomorrow 6:00 PM
                  </button>
                </div>

                <div className="pt-2">
                  <label className="block text-xs font-semibold text-gray-700 mb-1.5">Custom Date & Time</label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                    <input
                      type="datetime-local"
                      value={scheduleAt ? format(scheduleAt, "yyyy-MM-dd'T'HH:mm") : ''}
                      onChange={(e) => setScheduleAt(e.target.value ? new Date(e.target.value) : null)}
                      className="input pl-9 pr-3 py-2 text-sm w-full font-mono"
                    />
                  </div>
                  {scheduleAt && (
                    <p className="mt-2 text-xs text-primary-700 font-medium bg-primary-50 px-2.5 py-1 rounded-lg">
                      Scheduled for {format(scheduleAt, "MMM d, yyyy 'at' h:mm a")}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Action Card */}
          <div className="card p-5 space-y-4 bg-white border border-gray-200">
            <div>
              <p className="text-sm font-semibold text-gray-900">
                {selectedChannels.length === 0 ? (
                  <span className="text-gray-500 font-normal">Select channels to publish to</span>
                ) : (
                  <span>Ready to publish to <strong className="text-primary-600">{selectedChannels.length} channel{selectedChannels.length !== 1 ? 's' : ''}</strong></span>
                )}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                {scheduleMode === 'later' && scheduleAt
                  ? `Scheduled to queue at ${format(scheduleAt, "MMM d, h:mm a")}`
                  : 'Posts will be sent immediately via Buffer API'}
              </p>
            </div>

            <button
              onClick={handlePublish}
              disabled={publishMutation.isPending || selectedChannels.length === 0}
              className="btn-primary w-full py-3 shadow-sm flex items-center justify-center font-semibold text-base transition-transform active:scale-[0.99]"
            >
              {publishMutation.isPending ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin mr-2" />
                  Publishing...
                </>
              ) : scheduleMode === 'later' ? (
                <>
                  <Clock className="h-5 w-5 mr-2" />
                  Schedule Post ({selectedChannels.length})
                </>
              ) : (
                <>
                  <Send className="h-5 w-5 mr-2" />
                  Publish Now ({selectedChannels.length})
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Full-width Publishing History */}
      {attempts.length > 0 && (
        <div className="card overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-gray-900 text-base">Publishing History</h2>
              <p className="text-xs text-gray-500">Delivery status and retry attempts for this content</p>
            </div>
            <span className="badge badge-gray">{attempts.length} attempt{attempts.length !== 1 ? 's' : ''}</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Channel</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Scheduled</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Published</th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Attempts</th>
                  <th className="px-5 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-sm">
                {channels.map((channel) => {
                  const channelAttempts = attempts.filter((a) => a.channel_id === channel.id)
                  const latest = getLatestAttempt(channel.id)
                  const status = latest?.status

                  return (
                    <tr key={channel.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center shadow-xs', platformColors[channel.platform] || 'bg-gray-700 text-white')}>
                            <PlatformIcon platform={channel.platform} className="h-4 w-4 text-white" />
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">{channel.account_name}</p>
                            <p className="text-xs text-gray-500 capitalize">{channel.platform}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        {status ? (
                          <div className="space-y-1">
                            <span className={clsx(
                              'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border',
                              status === 'sent' && 'bg-emerald-50 text-emerald-700 border-emerald-200',
                              status === 'failed' && 'bg-red-50 text-red-700 border-red-200',
                              status === 'pending' && 'bg-amber-50 text-amber-700 border-amber-200',
                              status === 'retrying' && 'bg-blue-50 text-blue-700 border-blue-200'
                            )}>
                              <StatusIcon status={status} />
                              {statusConfig[status]?.label}
                            </span>
                            {status === 'failed' && latest?.error && (
                              <p className="text-xs text-red-600 max-w-xs truncate" title={latest.error}>
                                {latest.error}
                              </p>
                            )}
                          </div>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-gray-100 text-gray-500 border-gray-200">
                            <MinusCircle className="h-3 w-3" />
                            Not Selected
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3.5 text-xs text-gray-500">
                        {latest?.scheduled_at ? formatDistanceToNow(new Date(latest.scheduled_at), { addSuffix: true }) : '—'}
                      </td>
                      <td className="px-5 py-3.5 text-xs text-gray-500">
                        {latest?.published_at ? formatDistanceToNow(new Date(latest.published_at), { addSuffix: true }) : '—'}
                      </td>
                      <td className="px-5 py-3.5 text-xs text-gray-500">
                        <span className="font-mono">{channelAttempts.length}</span>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        {latest?.status === 'failed' && (
                          <button
                            onClick={() => retryMutation.mutate(latest.id)}
                            disabled={retryMutation.isPending}
                            className="btn-secondary text-xs px-2.5 py-1 inline-flex items-center"
                          >
                            {retryMutation.isPending ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <>
                                <RefreshCw className="h-3.5 w-3.5 mr-1" />
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
