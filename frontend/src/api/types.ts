// API Types matching backend schemas

export type UUID = string

export type JobType = 'blog' | 'post'
export type JobStatus = 
  | 'pending' 
  | 'expanding_prompt' 
  | 'writing_text' 
  | 'generating_image' 
  | 'safety_check' 
  | 'adapting' 
  | 'awaiting_review' 
  | 'approved' 
  | 'regenerating' 
  | 'publishing' 
  | 'published' 
  | 'failed'

export type Platform = 'instagram' | 'facebook' | 'linkedin'
export type ContentType = 'blog' | 'social_post'
export type ImageAspectRatio = '1:1' | '4:5' | '1.91:1' | '9:16'
export type PublishStatus = 'pending' | 'sent' | 'failed' | 'retrying'

export interface TimestampMixin {
  created_at: string
  updated_at: string
}

export interface IDMixin {
  id: UUID
}

// Auth
export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserRegister {
  email: string
  password: string
  company_name: string
}

export interface UserLogin {
  email: string
  password: string
}

export interface UserResponse {
  id: UUID
  email: string
  company_id: UUID
  is_active: boolean
  created_at: string
}

// Brand Kit
export interface BrandKitBase {
  company_name: string
  tagline?: string
  address?: string
  logo_url?: string
  primary_color?: string
  secondary_color?: string
  tone?: string
  use_openai_only: boolean
}

export interface BrandKitCreate extends BrandKitBase {}
export interface BrandKitUpdate extends Partial<BrandKitBase> {}

export interface BrandKitResponse extends BrandKitBase, IDMixin, TimestampMixin {
  company_id: UUID
}

// Jobs
export interface JobCreate {
  type: JobType
  title: string
  topic: string
  tone?: string
  audience?: string
  keywords: string[]
  image_description?: string
  platforms: Platform[]
  use_references: boolean
  reference_image_ids: UUID[]
}

export interface JobResponse extends IDMixin, TimestampMixin {
  type: JobType
  title: string
  topic: string
  tone?: string
  audience?: string
  keywords: string[]
  image_description?: string
  platforms: Platform[]
  status: JobStatus
  progress: number
  current_step?: string
  error?: string
  company_id: UUID
  user_id: UUID
}

export interface JobListResponse {
  jobs: JobResponse[]
  total: number
  page: number
  page_size: number
}

// Content
export interface PlatformContent {
  platform: Platform
  text: string
  hashtags: string[]
  character_count: number
}

export interface ImageVariant {
  id: UUID
  url: string
  aspect_ratio: ImageAspectRatio
  width: number
  height: number
  is_primary: boolean
  prompt_used: string
  reference_image_ids: UUID[]
}

export interface ContentResponse extends IDMixin, TimestampMixin {
  job_id: UUID
  type: ContentType
  title: string
  long_text: string
  platform_contents: PlatformContent[]
  image_variants: ImageVariant[]
  primary_image_id?: UUID
  safety_check_passed: boolean
  safety_flags: string[]
}

// Review
export interface RegenerateRequest {
  feedback: string
  regenerate_text: boolean
  regenerate_image: boolean
  reference_image_ids: UUID[]
}

export interface ApproveRequest {
  selected_image_id: UUID
  edited_text?: Record<Platform, string>
  schedule_at?: string
}

export interface ReviewResponse {
  job_id: UUID
  content: ContentResponse
  can_regenerate: boolean
  regeneration_count: number
  max_regenerations: number
}

// Publish
export interface ChannelConnection extends IDMixin, TimestampMixin {
  platform: Platform
  external_account_id: string
  account_name: string
  is_active: boolean
  connected_at: string
}

export interface PublishRequest {
  content_id: UUID
  channel_ids: UUID[]
  schedule_at?: string
}

export interface PublishAttemptResponse extends IDMixin, TimestampMixin {
  content_id: UUID
  channel_id: UUID
  platform: Platform
  status: PublishStatus
  external_post_id?: string
  error?: string
  retry_count: number
  scheduled_at?: string
  published_at?: string
}

export interface BufferConnectRequest {
  code: string
  state: string
}

export interface BufferConnectResponse {
  authorization_url: string
  state: string
}

// Library
export interface ImageTag {
  name: string
  count: number
}

export interface LibraryImageResponse extends IDMixin, TimestampMixin {
  url: string
  thumbnail_url?: string
  prompt: string
  tags: string[]
  aspect_ratio: ImageAspectRatio
  width: number
  height: number
  is_global: boolean
  company_id: UUID
  approved_at: string
}

export interface LibrarySearchRequest {
  query?: string
  tags?: string[]
  aspect_ratio?: ImageAspectRatio
  is_global?: boolean
  page: number
  page_size: number
}

export interface LibrarySearchResponse {
  images: LibraryImageResponse[]
  total: number
  page: number
  page_size: number
  suggested_tags: ImageTag[]
}

export interface SaveToLibraryRequest {
  content_id: UUID
  image_id: UUID
  tags: string[]
  is_global: boolean
}

// Quotas
export interface QuotaResponse {
  daily_free_requests_used: number
  daily_free_requests_limit: number
  daily_spend_usd: number
  daily_spend_cap_usd: number
  regenerations_used: number
  regenerations_limit: number
}

// Error
export interface ErrorDetail {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface ErrorResponse {
  error: ErrorDetail
}

// Beta
export type BetaUserStatus = 'invited' | 'active' | 'inactive' | 'completed' | 'churned'
export type FeedbackType = 'bug' | 'feature_request' | 'usability' | 'content_quality' | 'performance' | 'general'
export type FeedbackPriority = 'low' | 'medium' | 'high' | 'critical'

export interface BetaUserInvite {
  email: string
  name?: string
}

export interface BetaUserResponse extends IDMixin, TimestampMixin {
  email: string
  name?: string
  status: BetaUserStatus
  invited_at: string
  activated_at?: string
  first_post_at?: string
  last_active_at?: string
  total_posts: number
  total_regenerations: number
  feedback_count: number
  nps_score?: number
}

export interface BetaFeedbackSubmit {
  type: FeedbackType
  title: string
  description: string
  priority?: FeedbackPriority
  context?: Record<string, any>
}

export interface BetaFeedbackResponse extends IDMixin, TimestampMixin {
  beta_user_id: UUID
  type: FeedbackType
  priority: FeedbackPriority
  title: string
  description: string
  context?: Record<string, any>
  status: string
}

export interface OnboardingStepResponse extends IDMixin, TimestampMixin {
  beta_user_id: UUID
  step_key: string
  step_name: string
  step_order: number
  completed: boolean
  completed_at?: string
  skipped: boolean
  time_spent_seconds: number
}

export interface OnboardingProgressResponse {
  total_steps: number
  completed_steps: number
  progress_percent: number
  steps: Array<{
    step_key: string
    step_name: string
    step_order: number
    completed: boolean
    completed_at?: string
    time_spent_seconds: number
  }>
}

export interface BetaMetricsResponse extends IDMixin, TimestampMixin {
  date: string
  company_id: UUID
  total_generations: number
  approved_generations: number
  rejected_generations: number
  total_regenerations: number
  avg_time_to_first_post: number
  avg_time_to_approve: number
  avg_regenerations_per_post: number
  total_publishes: number
  successful_publishes: number
  failed_publishes: number
  total_spend_usd: number
  free_requests_used: number
  openai_fallbacks: number
  active_users: number
  new_users: number
  churned_users: number
}

export interface BetaDashboardResponse {
  summary: Record<string, any>
  generation_metrics: Record<string, any>
  publish_metrics: Record<string, any>
  recent_feedback: Array<{
    id: UUID
    type: FeedbackType
    priority: FeedbackPriority
    title: string
    created_at: string
  }>
}