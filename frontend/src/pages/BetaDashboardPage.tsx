import { useQuery } from '@tanstack/react-query'
import { 
  Users, TrendingUp, CheckCircle, AlertCircle, 
  MessageSquare, Star, Zap, Clock, RefreshCw,
  ArrowLeft, ExternalLink, Download, BarChart2, Loader2
} from 'lucide-react'
import { betaApi } from '../api/services'
import type { BetaDashboardResponse, BetaMetricsResponse } from '../api/types'
import { format, formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'

type MetricCard = {
  key: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  color: keyof typeof iconColors
  suffix?: string
}

const metricCards: MetricCard[] = [
  { key: 'total_invited', label: 'Total Invited', icon: Users, color: 'blue' },
  { key: 'active_users', label: 'Active Users', icon: Users, color: 'green' },
  { key: 'activation_rate', label: 'Activation Rate', icon: TrendingUp, color: 'purple', suffix: '%' },
  { key: 'completed_onboarding', label: 'Onboarding Done', icon: CheckCircle, color: 'orange' },
]

const generationCards: MetricCard[] = [
  { key: 'total_generations', label: 'Total Generations', icon: Zap, color: 'blue' },
  { key: 'approved_generations', label: 'Approved', icon: CheckCircle, color: 'green' },
  { key: 'approval_rate', label: 'Approval Rate', icon: TrendingUp, color: 'purple', suffix: '%' },
  { key: 'avg_regenerations_per_post', label: 'Avg Regenerations', icon: Zap, color: 'orange' },
]

const publishCards: MetricCard[] = [
  { key: 'total_publishes', label: 'Total Publishes', icon: Zap, color: 'blue' },
  { key: 'successful_publishes', label: 'Successful', icon: CheckCircle, color: 'green' },
  { key: 'publish_success_rate', label: 'Success Rate', icon: TrendingUp, color: 'purple', suffix: '%' },
  { key: 'failed_publishes', label: 'Failed', icon: AlertCircle, color: 'red' },
]

const colorClasses = {
  blue: 'bg-blue-100 text-blue-700',
  green: 'bg-green-100 text-green-700',
  purple: 'bg-purple-100 text-purple-700',
  orange: 'bg-orange-100 text-orange-700',
  red: 'bg-red-100 text-red-700',
}

const iconColors = {
  blue: 'text-blue-600 bg-blue-100',
  green: 'text-green-600 bg-green-100',
  purple: 'text-purple-600 bg-purple-100',
  orange: 'text-orange-600 bg-orange-100',
  red: 'text-red-600 bg-red-100',
}

export function BetaDashboardPage() {
  const { data: dashboardResponse, isLoading, error, refetch } = useQuery({
    queryKey: ['beta', 'dashboard'],
    queryFn: () => betaApi.getDashboard(),
    staleTime: 30000,
  })

  const { data: metricsResponse } = useQuery({
    queryKey: ['beta', 'metrics', 30],
    queryFn: () => betaApi.getMetrics(30),
  })

  const dashboard = dashboardResponse?.data
  const metrics = metricsResponse?.data

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto py-12">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-12 w-12 animate-spin text-primary-600" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto py-12">
        <div className="card p-12 text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-medium text-gray-900">Failed to load dashboard</h2>
          <button onClick={() => refetch()} className="mt-4 btn-primary">Try again</button>
        </div>
      </div>
    )
  }

  const summary = dashboard?.summary || {}
  const generation = dashboard?.generation_metrics || {}
  const publish = dashboard?.publish_metrics || {}
  const feedback = dashboard?.recent_feedback || []

  const renderMetricCard = ({ key, label, icon: Icon, color, suffix = '', value: propValue }: { key: string; label: string; icon: React.ComponentType<{ className?: string }>; color: keyof typeof iconColors; suffix?: string; value?: number }) => {
    const value = (propValue ?? summary[key] ?? generation[key] ?? publish[key] ?? 0)
    const formatted = suffix ? `${value}${suffix}` : (typeof value === 'number' ? value.toLocaleString() : value)
    
    return (
      <div className="card p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500">{label}</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{formatted}</p>
          </div>
          <div className={clsx('w-12 h-12 rounded-xl flex items-center justify-center', iconColors[color] || 'text-gray-600 bg-gray-100')}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </div>
    )
  }

  const renderFeedbackItem = (f: any) => (
    <div key={f.id} className="card p-4 border-l-4 border-primary-500">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={clsx(
              'px-2 py-0.5 rounded text-xs font-medium',
              f.priority === 'critical' && 'bg-red-100 text-red-700',
              f.priority === 'high' && 'bg-orange-100 text-orange-700',
              f.priority === 'medium' && 'bg-yellow-100 text-yellow-700',
              f.priority === 'low' && 'bg-gray-100 text-gray-700'
            )}>
              {f.priority}
            </span>
            <span className="text-sm text-gray-500">{f.type.replace('_', ' ')}</span>
          </div>
          <h4 className="font-medium text-gray-900 truncate">{f.title}</h4>
          <p className="text-sm text-gray-500 mt-1">{formatDistanceToNow(new Date(f.created_at), { addSuffix: true })}</p>
        </div>
      </div>
    </div>
  )

  if (!dashboard) {
    return (
      <div className="max-w-7xl mx-auto py-12 text-center">
        <BarChart2 className="h-16 w-16 text-gray-300 mx-auto mb-4" />
        <h2 className="text-lg font-medium text-gray-900">No beta data yet</h2>
        <p className="mt-1 text-gray-500">Invite beta users to start tracking metrics</p>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Beta Dashboard</h1>
          <p className="text-gray-500">Monitor beta program health and user feedback</p>
        </div>
        <div className="flex gap-3">
          <button onClick={() => refetch()} className="btn-secondary">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
          <button className="btn-primary">
            <Download className="h-4 w-4 mr-2" />
            Export Report
          </button>
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metricCards.map(card => renderMetricCard({ ...card, value: summary[card.key] }))}
      </div>

      {/* Generation Metrics */}
      <div className="card">
        <div className="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Zap className="h-5 w-5 text-primary-600" />
            Generation Metrics (Last 7 Days)
          </h2>
        </div>
        <div className="p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {generationCards.map(card => renderMetricCard({ ...card, value: generation[card.key] }))}
        </div>
      </div>

      {/* Publish Metrics */}
      <div className="card">
        <div className="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Zap className="h-5 w-5 text-green-600" />
            Publishing Metrics (Last 7 Days)
          </h2>
        </div>
        <div className="p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {publishCards.map(card => renderMetricCard({ ...card, value: publish[card.key] }))}
        </div>
      </div>

      {/* Recent Feedback */}
      <div className="card">
        <div className="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-purple-600" />
            Recent Feedback
          </h2>
          <a href="/beta/feedback" className="text-sm text-primary-600 hover:text-primary-700">
            View All
          </a>
        </div>
        <div className="p-6 space-y-3">
          {feedback.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p>No feedback yet</p>
            </div>
          ) : (
            feedback.map(renderFeedbackItem)
          )}
        </div>
      </div>

      {/* Trends Chart (Placeholder) */}
      {metrics && metrics.length > 0 && (
        <div className="card">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <BarChart2 className="h-5 w-5 text-gray-600" />
              30-Day Trends
            </h2>
          </div>
          <div className="p-6">
            <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center text-gray-400">
              <p>Chart visualization coming soon</p>
              <p className="text-sm mt-1">Daily metrics: generations, approvals, publishes, costs</p>
            </div>
          </div>
        </div>
      )}

      {/* Beta Users Table */}
      <div className="card">
        <div className="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Users className="h-5 w-5 text-gray-600" />
            Beta Users
          </h2>
        </div>
        <div className="p-6">
          <p className="text-center text-gray-500 py-8">Beta user management coming soon</p>
        </div>
      </div>
    </div>
  )
}