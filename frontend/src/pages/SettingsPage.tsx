import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../hooks/useAuth'
import { 
  User, Key, Shield, Globe, Database, 
  Loader2, AlertCircle, CheckCircle, ExternalLink,
  ChevronRight, Trash2, Image, FileText, Share2, Layers
} from 'lucide-react'
import { publishApi } from '../api/services'
import type { ChannelConnection } from '../api/types'
import clsx from 'clsx'
import { formatDistanceToNow, format } from 'date-fns'
import { SEO } from '../components/SEO'
import { PlatformIcon, platformColors, platformBadgeColors } from '../components/PlatformIcon'
import { useToast } from '../components/Toast'

export function SettingsPage() {
  const { user, logout } = useAuth()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState<'account' | 'channels' | 'security' | 'integrations' | 'legal'>('account')
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
      toast({ message: 'Channel disconnected successfully', type: 'success' })
    },
    onError: () => {
      toast({ message: 'Failed to disconnect channel', type: 'error' })
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
      toast({ message: 'Failed to initiate Buffer connection', type: 'error' })
    }
  }

  const handleLogout = async () => {
    await logout()
  }

  const channels = channelsResponse?.data || []

  const navItems = [
    { id: 'account', label: 'Account', icon: User, desc: 'Profile and company info' },
    { id: 'channels', label: 'Channels', icon: Share2, desc: 'Social account sync', count: channels.length },
    { id: 'security', label: 'Security', icon: Shield, desc: 'Authentication & tokens' },
    { id: 'integrations', label: 'Integrations', icon: Globe, desc: 'AI models & storage' },
    { id: 'legal', label: 'Legal', icon: FileText, desc: 'Terms & privacy policies' },
  ]

  return (
    <div className="w-full space-y-6 pb-12">
      <SEO title="Settings" description="Manage account, channels, and integrations." path="/settings" robots="noindex,nofollow" />

      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 tracking-tight">Settings</h1>
        <p className="text-sm text-gray-500">Manage your organization profile, connected channels, and AI service preferences</p>
      </div>

      {/* Responsive layout: 2 columns on Desktop (sidebar tabs + main panel) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Navigation Sidebar (Desktop: 3 cols / Mobile: horizontal scroll) */}
        <div className="lg:col-span-3">
          {/* Desktop Vertical Menu */}
          <div className="hidden lg:block card p-2 space-y-1">
            {navItems.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as typeof activeTab)}
                  className={clsx(
                    'w-full flex items-center justify-between px-3.5 py-3 rounded-xl text-left text-sm font-medium transition-all duration-150',
                    isActive
                      ? 'bg-primary-50 text-primary-700 shadow-xs'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  )}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Icon className={clsx('h-4 w-4 flex-shrink-0', isActive ? 'text-primary-600' : 'text-gray-400')} />
                    <span className="truncate">{tab.label}</span>
                  </div>
                  {tab.count !== undefined && (
                    <span className={clsx(
                      'px-2 py-0.5 rounded-full text-xs font-semibold',
                      isActive ? 'bg-primary-100 text-primary-700' : 'bg-gray-100 text-gray-600'
                    )}>
                      {tab.count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Mobile Horizontal Menu */}
          <div className="lg:hidden card p-1 overflow-x-auto flex gap-1">
            {navItems.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as typeof activeTab)}
                  className={clsx(
                    'flex items-center gap-2 px-3.5 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors',
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-50'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span>{tab.label}</span>
                  {tab.count !== undefined && (
                    <span className="px-1.5 py-0.2 rounded-full text-xs bg-gray-100 font-semibold">
                      {tab.count}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* Content Panel (9 cols on Desktop) */}
        <div className="lg:col-span-9">
          <div className="card p-5 sm:p-7">
            {/* Account Tab */}
            {activeTab === 'account' && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Account Profile</h2>
                  <p className="text-xs text-gray-500">Your personal login and organization workspace</p>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center gap-4 p-5 bg-gray-50/80 border border-gray-200/70 rounded-2xl">
                  <div className="w-16 h-16 rounded-2xl bg-primary-100 flex items-center justify-center font-bold text-xl text-primary-700 shadow-xs flex-shrink-0">
                    {user?.email?.charAt(0).toUpperCase()}
                  </div>
                  <div className="space-y-1 min-w-0 flex-1">
                    <h3 className="font-semibold text-gray-900 text-lg truncate">{user?.email}</h3>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500 font-mono">
                      <span className="bg-white px-2 py-0.5 rounded border border-gray-200">
                        Workspace ID: {user?.company_id || 'Personal'}
                      </span>
                      <span>•</span>
                      <span>Member since {format(new Date(user?.created_at || ''), 'MMMM yyyy')}</span>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 pt-6">
                  <h4 className="font-semibold text-gray-900 text-sm mb-3">Session Actions</h4>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center justify-between p-4 rounded-xl border border-gray-200 hover:border-red-200 hover:bg-red-50/40 transition-colors text-left group"
                  >
                    <div className="flex items-center gap-3.5">
                      <div className="w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center text-red-600 group-hover:scale-105 transition-transform">
                        <Key className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-semibold text-gray-900 group-hover:text-red-700 transition-colors">Sign Out</p>
                        <p className="text-xs text-gray-500">Securely sign out of this device</p>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-red-600 transition-colors" />
                  </button>
                </div>
              </div>
            )}

            {/* Channels Tab */}
            {activeTab === 'channels' && (
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-gray-100">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">Connected Channels</h2>
                    <p className="text-xs text-gray-500">Social media accounts synced via Buffer for multi-platform delivery</p>
                  </div>
                  <button
                    onClick={handleBufferConnect}
                    className="btn-primary inline-flex items-center self-start sm:self-auto shadow-xs"
                  >
                    <Share2 className="h-4 w-4 mr-2" />
                    Connect Buffer
                  </button>
                </div>

                {channelsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
                  </div>
                ) : channels.length === 0 ? (
                  <div className="text-center py-12">
                    <Share2 className="h-14 w-14 text-gray-300 mx-auto mb-3" />
                    <h3 className="font-semibold text-gray-900">No channels connected yet</h3>
                    <p className="mt-1 text-sm text-gray-500 max-w-sm mx-auto mb-5">
                      Authorize your Buffer account to automatically publish to Instagram, Facebook, and LinkedIn.
                    </p>
                    <button onClick={handleBufferConnect} className="btn-primary">
                      Connect Buffer Account
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {channels.map((channel) => (
                      <div
                        key={channel.id}
                        className="flex items-center justify-between p-4 border border-gray-200/80 rounded-xl bg-white hover:border-gray-300 hover:shadow-xs transition-all"
                      >
                        <div className="flex items-center gap-3.5 min-w-0">
                          <div className={clsx(
                            'w-11 h-11 rounded-xl flex items-center justify-center shadow-xs flex-shrink-0',
                            platformColors[channel.platform] || 'bg-gray-700 text-white'
                          )}>
                            <PlatformIcon platform={channel.platform} className="h-5 w-5 text-white" />
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="font-semibold text-gray-900 text-sm truncate">{channel.account_name}</p>
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

                        <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                          <span className={clsx(
                            'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border',
                            channel.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-gray-100 text-gray-700 border-gray-200'
                          )}>
                            {channel.is_active ? <CheckCircle className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
                            {channel.is_active ? 'Active' : 'Inactive'}
                          </span>
                          <button
                            onClick={() => handleDisconnect(channel.id)}
                            disabled={disconnectingChannel === channel.id}
                            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            title="Disconnect channel"
                          >
                            {disconnectingChannel === channel.id ? (
                              <Loader2 className="h-4 w-4 animate-spin text-red-600" />
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

            {/* Security Tab */}
            {activeTab === 'security' && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Security & Authentication</h2>
                  <p className="text-xs text-gray-500">Security policies, token lifecycles, and session protection</p>
                </div>

                <div className="card p-5 bg-blue-50/60 border border-blue-200 rounded-xl">
                  <div className="flex items-start gap-3.5">
                    <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center flex-shrink-0 text-blue-600">
                      <Shield className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-blue-950 text-sm">Enterprise Security Controls</h3>
                      <ul className="mt-2.5 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-blue-800">
                        <li>• JWT access tokens with 30-minute rotation</li>
                        <li>• 7-day rolling refresh tokens</li>
                        <li>• Strong bcrypt password hashing</li>
                        <li>• OAuth 2.0 PKCE tokens encrypted at rest</li>
                        <li>• Tenant-isolated PostgreSQL Row-Level Security</li>
                        <li>• Strict CORS and rate-limiting enforcement</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 pt-6 space-y-3">
                  <h4 className="font-semibold text-gray-900 text-sm">Security Options</h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="p-4 border border-gray-200 rounded-xl">
                      <p className="font-semibold text-gray-900 text-sm">Password</p>
                      <p className="text-xs text-gray-500 mt-1">Managed securely through bcrypt hash</p>
                      <span className="mt-3 inline-block badge badge-green text-xs">Protected</span>
                    </div>
                    <div className="p-4 border border-gray-200 rounded-xl">
                      <p className="font-semibold text-gray-900 text-sm">Two-Factor Auth</p>
                      <p className="text-xs text-gray-500 mt-1">TOTP authentication support</p>
                      <span className="mt-3 inline-block badge badge-gray text-xs">Coming Soon</span>
                    </div>
                    <div className="p-4 border border-gray-200 rounded-xl">
                      <p className="font-semibold text-gray-900 text-sm">Session Invalidation</p>
                      <p className="text-xs text-gray-500 mt-1">Instant token revoke on logout</p>
                      <span className="mt-3 inline-block badge badge-green text-xs">Active</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Integrations Tab */}
            {activeTab === 'integrations' && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Configured Integrations</h2>
                  <p className="text-xs text-gray-500">Connected AI providers, storage endpoints, and social gateways</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="card p-5 border border-gray-200 rounded-xl flex flex-col justify-between">
                    <div>
                      <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-600 mb-3">
                        <CheckCircle className="h-5 w-5" />
                      </div>
                      <h4 className="font-semibold text-gray-900 text-sm">OpenRouter (Free)</h4>
                      <p className="text-xs text-gray-600 mt-1.5 leading-relaxed">
                        Llama 3.1 8B, Mistral 7B, and Gemma 2 models with automatic fallback to OpenAI GPT-4o-mini on rate limits.
                      </p>
                    </div>
                    <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                      <span>Status</span>
                      <span className="text-emerald-700 font-semibold">Active & Synced</span>
                    </div>
                  </div>

                  <div className="card p-5 border border-gray-200 rounded-xl flex flex-col justify-between">
                    <div>
                      <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center text-purple-600 mb-3">
                        <Image className="h-5 w-5" />
                      </div>
                      <h4 className="font-semibold text-gray-900 text-sm">GPT Image 2.5 Sunburst</h4>
                      <p className="text-xs text-gray-600 mt-1.5 leading-relaxed">
                        High-fidelity visual generation with brand reference alignment and multi-aspect ratio rendering.
                      </p>
                    </div>
                    <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                      <span>Status</span>
                      <span className="text-purple-700 font-semibold">Ready</span>
                    </div>
                  </div>

                  <div className="card p-5 border border-gray-200 rounded-xl flex flex-col justify-between">
                    <div>
                      <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center text-blue-600 mb-3">
                        <Database className="h-5 w-5" />
                      </div>
                      <h4 className="font-semibold text-gray-900 text-sm">Buffer Publishing</h4>
                      <p className="text-xs text-gray-600 mt-1.5 leading-relaxed">
                        Direct OAuth publishing to Instagram, Facebook, and LinkedIn with full retry queues and scheduling.
                      </p>
                    </div>
                    <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                      <span>Channels</span>
                      <span className="text-blue-700 font-semibold">{channels.length} Connected</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Legal Tab */}
            {activeTab === 'legal' && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Legal Documents & Compliance</h2>
                  <p className="text-xs text-gray-500">Terms of service, privacy disclosures, and model usage notices</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <button
                    onClick={() => window.open('/legal/privacy', '_blank')}
                    className="card p-6 hover:border-primary-400 hover:shadow-xs transition-all border border-gray-200 text-left group"
                  >
                    <div className="w-12 h-12 rounded-xl bg-primary-100 flex items-center justify-center text-primary-600 mb-4 group-hover:scale-105 transition-transform">
                      <Shield className="h-6 w-6" />
                    </div>
                    <h3 className="font-semibold text-gray-900 text-base">Privacy Policy</h3>
                    <p className="mt-1 text-xs text-gray-500">How customer data, generated assets, and prompts are handled.</p>
                    <div className="mt-4 flex items-center gap-1.5 text-primary-600 text-xs font-semibold">
                      <ExternalLink className="h-3.5 w-3.5" />
                      View Policy
                    </div>
                  </button>

                  <button
                    onClick={() => window.open('/legal/terms', '_blank')}
                    className="card p-6 hover:border-blue-400 hover:shadow-xs transition-all border border-gray-200 text-left group"
                  >
                    <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center text-blue-600 mb-4 group-hover:scale-105 transition-transform">
                      <FileText className="h-6 w-6" />
                    </div>
                    <h3 className="font-semibold text-gray-900 text-base">Terms of Service</h3>
                    <p className="mt-1 text-xs text-gray-500">Guidelines, software license terms, and operational warranties.</p>
                    <div className="mt-4 flex items-center gap-1.5 text-blue-600 text-xs font-semibold">
                      <ExternalLink className="h-3.5 w-3.5" />
                      View Terms
                    </div>
                  </button>
                </div>

                <div className="card p-4 border-l-4 border-amber-500 bg-amber-50 rounded-xl">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center text-amber-600 flex-shrink-0 mt-0.5">
                      <AlertCircle className="h-4 w-4" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-amber-900 text-xs">AI Data Notice</h4>
                      <p className="text-xs text-amber-800 mt-1 leading-relaxed">
                        When using free OpenRouter models, generation requests may be processed according to upstream provider guidelines.
                        Enable <strong>"OpenAI Only" mode</strong> in the Brand Kit to guarantee strict non-logging paid API routing.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
