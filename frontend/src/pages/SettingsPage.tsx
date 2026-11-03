import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../hooks/useAuth'
import { 
  User, Key, Shield, Globe, Send, Database, 
  Loader2, AlertCircle, CheckCircle, ExternalLink,
  ChevronRight, Trash2, Image
} from 'lucide-react'
import { publishApi, authApi } from '../api/services'
import type { ChannelConnection } from '../api/types'
import clsx from 'clsx'
import { formatDistanceToNow, format } from 'date-fns'

const platformColors: Record<string, string> = {
  instagram: 'bg-gradient-to-r from-purple-500 to-pink-500',
  facebook: 'bg-blue-600',
  linkedin: 'bg-blue-700',
}

const platformIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  instagram: Send,
  facebook: Send,
  linkedin: Send,
}

export function SettingsPage() {
  const { user, logout } = useAuth()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'account' | 'channels' | 'security' | 'integrations'>('account')
  const [disconnectingChannel, setDisconnectingChannel] = useState<string | null>(null)

  const { data: channelsResponse, isLoading: channelsLoading } = useQuery({
    queryKey: ['publish', 'channels'],
    queryFn: () => publishApi.listChannels(),
  })

  const disconnectMutation = useMutation({
    mutationFn: (channelId: string) => publishApi.disconnectChannel(channelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['publish', 'channels'] })
      setDisconnectingChannel(null)
    },
  })

  const handleDisconnect = (channelId: string) => {
    if (confirm('Are you sure you want to disconnect this channel? You will need to re-authorize to use it again.')) {
      setDisconnectingChannel(channelId)
      disconnectMutation.mutate(channelId)
    }
  }

  const handleBufferConnect = async () => {
    try {
      const response = await publishApi.getBufferAuthUrl()
      window.location.href = response.data.authorization_url
    } catch (error) {
      alert('Failed to initiate Buffer connection')
    }
  }

  const handleLogout = async () => {
    await logout()
  }

  const channels = channelsResponse?.data || []

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500">Manage your account, connections, and preferences</p>
      </div>

      {/* Tabs */}
      <div className="card">
        <div className="border-b border-gray-200">
          <nav className="flex gap-1 p-1" aria-label="Settings tabs">
            {[
              { id: 'account', label: 'Account', icon: User },
              { id: 'channels', label: 'Channels', icon: Send },
              { id: 'security', label: 'Security', icon: Shield },
              { id: 'integrations', label: 'Integrations', icon: Globe },
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
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'account' && (
            <div className="space-y-6">
              <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
                <div className="w-16 h-16 rounded-full bg-primary-100 flex items-center justify-center">
                  <User className="h-8 w-8 text-primary-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">{user?.email}</h3>
                  <p className="text-sm text-gray-500">Company ID: {user?.company_id}</p>
                  <p className="text-sm text-gray-500">Member since: {format(new Date(user?.created_at || ''), 'MMMM yyyy')}</p>
                </div>
              </div>

              <div className="border-t border-gray-200 pt-6">
                <h4 className="font-medium text-gray-900 mb-4">Account Actions</h4>
                <div className="space-y-3">
                  <button
                    onClick={handleLogout}
                    className={clsx(
                      'w-full flex items-center justify-between px-4 py-3 rounded-lg border border-gray-200',
                      'hover:bg-gray-50 transition-colors text-left'
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
                        <Key className="h-5 w-5 text-red-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">Sign out</p>
                        <p className="text-sm text-gray-500">Sign out of your account</p>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-gray-400" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'channels' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-gray-900">Connected Channels</h3>
                <button
                  onClick={handleBufferConnect}
                  className="btn-primary"
                >
                  <Send className="h-4 w-4 mr-2" />
                  Connect Buffer
                </button>
              </div>

              {channelsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
                </div>
              ) : channels.length === 0 ? (
                <div className="text-center py-12">
                  <Send className="h-16 w-16 text-gray-300 mx-auto mb-4" />
                  <h3 className="font-medium text-gray-900">No channels connected</h3>
                  <p className="mt-1 text-gray-500 mb-4">Connect your Buffer account to publish to Instagram, Facebook, and LinkedIn</p>
                  <button onClick={handleBufferConnect} className="btn-primary">
                    <Send className="h-4 w-4 mr-2" />
                    Connect Buffer
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {channels.map((channel) => (
                    <div
                      key={channel.id}
                      className="flex items-center justify-between p-4 border border-gray-200 rounded-lg"
                    >
                      <div className="flex items-center gap-4">
                        <div className={clsx('w-12 h-12 rounded-lg flex items-center justify-center', platformColors[channel.platform])}>
                          <platformIcons[channel.platform] className="h-6 w-6 text-white" />
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{channel.account_name}</p>
                          <p className="text-sm text-gray-500 capitalize">{channel.platform}</p>
                          <p className="text-xs text-gray-400">Connected {formatDistanceToNow(new Date(channel.connected_at), { addSuffix: true })}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={clsx(
                          'flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
                          channel.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                        )}>
                          {channel.is_active ? <CheckCircle className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
                          {channel.is_active ? 'Active' : 'Inactive'}
                        </span>
                        <button
                          onClick={() => handleDisconnect(channel.id)}
                          disabled={disconnectingChannel === channel.id}
                          className="btn-ghost text-red-600 hover:bg-red-50"
                        >
                          {disconnectingChannel === channel.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'security' && (
            <div className="space-y-6">
              <div className="card p-4 bg-blue-50 border-blue-200">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                    <Shield className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="font-medium text-blue-900">Security Features</h3>
                    <ul className="mt-2 space-y-1 text-sm text-blue-700">
                      <li>• JWT access tokens (30 min expiry)</li>
                      <li>• Refresh tokens (7 day expiry, rotated on use)</li>
                      <li>• Passwords hashed with bcrypt</li>
                      <li>• OAuth tokens encrypted at rest</li>
                      <li>• Company-level data isolation (RLS)</li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-200 pt-6">
                <h4 className="font-medium text-gray-900 mb-4">Session Management</h4>
                <div className="space-y-3">
                  <button className={clsx(
                    'w-full flex items-center justify-between px-4 py-3 rounded-lg border border-gray-200',
                    'hover:bg-gray-50 transition-colors text-left'
                  )}>
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                        <Key className="h-5 w-5 text-purple-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">Change Password</p>
                        <p className="text-sm text-gray-500">Update your account password</p>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-gray-400" />
                  </button>
                  <button className={clsx(
                    'w-full flex items-center justify-between px-4 py-3 rounded-lg border border-gray-200',
                    'hover:bg-gray-50 transition-colors text-left'
                  )}>
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                        <Shield className="h-5 w-5 text-green-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">Enable 2FA</p>
                        <p className="text-sm text-gray-500">Add two-factor authentication (coming soon)</p>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-gray-400" />
                  </button>
                  <button className={clsx(
                    'w-full flex items-center justify-between px-4 py-3 rounded-lg border border-gray-200',
                    'hover:bg-gray-50 transition-colors text-left'
                  )}>
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center">
                        <Database className="h-5 w-5 text-orange-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">Active Sessions</p>
                        <p className="text-sm text-gray-500">View and manage active sessions (coming soon)</p>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-gray-400" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'integrations' && (
            <div className="space-y-6">
              <div className="card p-4 bg-gray-50 border-gray-200">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center">
                    <Globe className="h-5 w-5 text-primary-600" />
                  </div>
                  <div>
                    <h3 className="font-medium text-gray-900">Buffer Integration</h3>
                    <p className="text-sm text-gray-600 mt-1">
                      Buffer handles publishing to Instagram, Facebook, and LinkedIn via OAuth 2.0 with PKCE.
                      Your social account credentials are never stored on our servers.
                    </p>
                  </div>
                </div>
              </div>

              <div className="border-t border-gray-200 pt-6">
                <h4 className="font-medium text-gray-900 mb-4">AI Model Configuration</h4>
                <div className="space-y-4">
                  <div className="card p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                        <CheckCircle className="h-5 w-5 text-green-600" />
                      </div>
                      <div className="flex-1">
                        <h4 className="font-medium text-gray-900">Free Models (OpenRouter)</h4>
                        <p className="text-sm text-gray-600 mt-1">
                          Primary: Free OpenRouter models (Llama 3.1 8B, Mistral 7B, Gemma 2 9B)
                          <br />Fallback: OpenAI GPT-4o-mini on rate limits or failures
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="card p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                        <Image className="h-5 w-5 text-purple-600" />
                      </div>
                      <div className="flex-1">
                        <h4 className="font-medium text-gray-900">Image Generation (Sunburst)</h4>
                        <p className="text-sm text-gray-600 mt-1">
                          GPT Image 2.5 Sunburst for high-quality image generation and editing
                          with reference image support.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="card p-4">
                    <div className="flex items-start gap-3">
                      <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                        <Database className="h-5 w-5 text-blue-600" />
                      </div>
                      <div className="flex-1">
                        <h4 className="font-medium text-gray-900">Cloudinary</h4>
                        <p className="text-sm text-gray-600 mt-1">
                          Image storage and CDN. Public links generated at approval time.
                          Automatic cleanup of drafts (7 days) and published (30 days).
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}