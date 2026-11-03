import api from './client'
import type {
  Token, UserRegister, UserLogin, UserResponse,
  JobCreate, JobResponse, JobListResponse, JobStatus,
  ContentResponse, ReviewResponse, RegenerateRequest, ApproveRequest,
  ChannelConnection, PublishRequest, PublishAttemptResponse,
  BufferConnectResponse, BufferConnectRequest,
  LibraryImageResponse, LibrarySearchResponse, LibrarySearchRequest, SaveToLibraryRequest, ImageTag,
  BrandKitResponse, BrandKitCreate, BrandKitUpdate,
  QuotaResponse,
} from './types'

// Auth
export const authApi = {
  register: (data: UserRegister) => api.post<UserResponse>('/auth/register', data),
  login: (data: UserLogin) => api.post<Token>('/auth/login', data),
  refresh: (refreshToken: string) => api.post<Token>('/auth/refresh', { refresh_token: refreshToken }),
  me: () => api.get<UserResponse>('/auth/me'),
  logout: () => api.post('/auth/logout'),
}

// Jobs
export const jobsApi = {
  create: (data: JobCreate) => api.post<JobResponse>('/jobs', data),
  list: (params?: { page?: number; page_size?: number; status?: JobStatus }) => 
    api.get<JobListResponse>('/jobs', { params }),
  get: (id: string) => api.get<JobResponse>(`/jobs/${id}`),
  cancel: (id: string) => api.delete(`/jobs/${id}`),
  simulateProgress: (id: string) => api.post<JobResponse>(`/jobs/${id}/simulate-progress`),
}

// Review
export const reviewApi = {
  get: (jobId: string) => api.get<ReviewResponse>(`/review/${jobId}`),
  regenerate: (jobId: string, data: RegenerateRequest) => 
    api.post<ReviewResponse>(`/review/${jobId}/regenerate`, data),
  approve: (jobId: string, data: ApproveRequest) => 
    api.post<ContentResponse>(`/review/${jobId}/approve`, data),
}

// Publish
export const publishApi = {
  listChannels: () => api.get<ChannelConnection[]>('/publish/channels'),
  getBufferAuthUrl: () => api.get<BufferConnectResponse>('/publish/buffer/connect'),
  connectBuffer: (data: BufferConnectRequest) => 
    api.post<ChannelConnection>('/publish/buffer/connect', data),
  disconnectChannel: (channelId: string) => api.delete(`/publish/buffer/channels/${channelId}`),
  publish: (data: PublishRequest) => 
    api.post<PublishAttemptResponse[]>('/publish', data),
  getAttempts: (contentId: string) => 
    api.get<PublishAttemptResponse[]>(`/publish/attempts/${contentId}`),
  retry: (attemptId: string) => 
    api.post<PublishAttemptResponse>(`/publish/attempts/${attemptId}/retry`),
}

// Library
export const libraryApi = {
  search: (params: LibrarySearchRequest) => 
    api.get<LibrarySearchResponse>('/library/search', { params }),
  get: (imageId: string) => api.get<LibraryImageResponse>(`/library/${imageId}`),
  save: (data: SaveToLibraryRequest) => 
    api.post<LibraryImageResponse>('/library', data),
  updateTags: (imageId: string, tags: string[]) => 
    api.patch<LibraryImageResponse>(`/library/${imageId}/tags`, { tags }),
  delete: (imageId: string) => api.delete(`/library/${imageId}`),
  getPopularTags: (limit?: number) => 
    api.get<ImageTag[]>('/library/tags/popular', { params: { limit } }),
}

// Brand
export const brandApi = {
  get: () => api.get<BrandKitResponse>('/brand'),
  upsert: (data: BrandKitCreate) => api.put<BrandKitResponse>('/brand', data),
  update: (data: BrandKitUpdate) => api.patch<BrandKitResponse>('/brand', data),
  uploadLogo: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<BrandKitResponse>('/brand/logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  deleteLogo: () => api.delete<BrandKitResponse>('/brand/logo'),
}

// Health
export const healthApi = {
  check: () => api.get('/health'),
  db: () => api.get('/health/db'),
  redis: () => api.get('/health/redis'),
  all: () => api.get('/health/all'),
}

// Legal
export const legalApi = {
  getPrivacy: () => api.get('/legal/privacy', { responseType: 'text' }),
  getTerms: () => api.get('/legal/terms', { responseType: 'text' }),
  getPrivacyMarkdown: () => api.get<{ markdown: string }>('/legal/privacy/markdown'),
  getTermsMarkdown: () => api.get<{ markdown: string }>('/legal/terms/markdown'),
}