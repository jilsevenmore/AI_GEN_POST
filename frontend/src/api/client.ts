import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { getAccessToken, setTokens, clearTokens } from './utils/tokens'
import { logger, sanitizeUrl } from '../utils/logger'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

interface RequestConfig extends InternalAxiosRequestConfig {
  __requestId?: string
  __startTime?: number
}

// Request interceptor: add auth token + log outgoing requests
api.interceptors.request.use(
  (config: RequestConfig) => {
    const token = getAccessToken()
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    config.__requestId =
      typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
        ? crypto.randomUUID()
        : Math.random().toString(36)
    config.__startTime = typeof performance !== 'undefined' ? performance.now() : 0

    logger.debug('api.request', {
      requestId: config.__requestId,
      method: config.method?.toUpperCase(),
      url: sanitizeUrl(config.url),
      hasAuthorization: Boolean(token),
    })
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: token refresh + log responses/errors
api.interceptors.response.use(
  (response) => {
    const config = response.config as RequestConfig
    const requestId = config.__requestId
    const start = config.__startTime
    const latencyMs = start ? Math.round((typeof performance !== 'undefined' ? performance.now() : 0) - start) : 0

    logger.info('api.response', {
      requestId,
      status: response.status,
      url: sanitizeUrl(config.url),
      latencyMs,
    })
    return response
  },
  async (error: AxiosError) => {
    const config = error.config as RequestConfig | undefined
    const requestId = config?.__requestId
    const start = config?.__startTime
    const latencyMs = start
      ? Math.round((typeof performance !== 'undefined' ? performance.now() : 0) - start)
      : 0
    const status = error.response?.status
    const message =
      (error.response?.data as { message?: string })?.message ?? error.message

    logger.error('api.error', {
      requestId,
      status,
      url: config ? sanitizeUrl(config.url) : undefined,
      latencyMs,
      error: typeof message === 'string' ? message.slice(0, 500) : String(message),
    })

    const originalRequest = config as InternalAxiosRequestConfig & { _retry?: boolean }

    const isAuthEndpoint = originalRequest.url?.includes('/auth/login') ||
                           originalRequest.url?.includes('/auth/register') ||
                           originalRequest.url?.includes('/auth/refresh')

    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      originalRequest._retry = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (!refreshToken) throw new Error('No refresh token')

        const response = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
        const { access_token, refresh_token } = response.data
        setTokens(access_token, refresh_token)

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`
        }
        return api(originalRequest)
      } catch {
        clearTokens()
        window.location.href = '/login'
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  }
)

export default api