import axios from 'axios'
import { ChannelAnalytics } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Log API configuration on module load
console.log('[API Config] Initializing API client')
console.log('[API Config] NEXT_PUBLIC_API_URL:', process.env.NEXT_PUBLIC_API_URL)
console.log('[API Config] Using baseURL:', API_URL)
console.log('[API Config] NODE_ENV:', process.env.NODE_ENV)
console.log('[API Config] Is production:', typeof window !== 'undefined' && window.location.hostname !== 'localhost')

// Create axios instance without baseURL - we'll use full URLs
export const api = axios.create({
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': '*',
  },
})

// Helper function to build full API URLs
const buildApiUrl = (endpoint: string): string => {
  const baseUrl = API_URL.endsWith('/') ? API_URL.slice(0, -1) : API_URL
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  return `${baseUrl}${cleanEndpoint}`
}

// Add Telegram auth to requests
api.interceptors.request.use((config) => {
  console.log('[API Request]', config.method?.toUpperCase(), config.url)
  console.log('[API Request] Window available:', typeof window !== 'undefined')
  console.log('[API Request] Telegram available:', typeof window !== 'undefined' && !!window.Telegram)
  console.log('[API Request] WebApp available:', typeof window !== 'undefined' && !!window.Telegram?.WebApp)

  if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
    // Use the full initData string with signature for authentication
    const initData = window.Telegram.WebApp.initData
    const initDataUnsafe = window.Telegram.WebApp.initDataUnsafe

    console.log('[API Request] initData:', initData ? 'present (' + initData.length + ' chars)' : 'empty')
    console.log('[API Request] initDataUnsafe:', initDataUnsafe ? 'present' : 'empty')

    if (initData && initData.trim() !== '') {
      config.headers['X-Telegram-Init-Data'] = initData
      console.log('[API Request] Using full Telegram initData with signature')
      console.log('[API Request] User ID:', initDataUnsafe?.user?.id)
    } else {
      // Fallback: send minimal data for development
      console.warn('[Mini App] No Telegram initData available, using fallback')
      config.headers['X-Telegram-Init-Data'] = JSON.stringify({
        user: {
          id: 0,
          first_name: 'Dev',
          username: 'dev_user'
        }
      })
    }
  } else {
    console.warn('[API Request] No Telegram WebApp available, using fallback auth')
    console.log('[API Request] Telegram object:', typeof window !== 'undefined' ? (window.Telegram ? 'present' : 'undefined') : 'window undefined')
    config.headers['X-Telegram-Init-Data'] = JSON.stringify({
      user: {
        id: 0,
        first_name: 'Dev',
        username: 'dev_user'
      }
    })
  }

  console.log('[API Request] Final URL:', config.url)
  console.log('[API Request] Final Headers:', JSON.stringify(config.headers, null, 2))

  return config
})

// Add response/error logging
api.interceptors.response.use(
  (response) => {
    console.log('[API Response] Success:', response.config.url, response.status)
    return response
  },
  (error) => {
    console.error('[API Response] Error:', error.config?.url)
    console.error('[API Response] Status:', error.response?.status)
    console.error('[API Response] Data:', error.response?.data)
    console.error('[API Response] Full error:', error)
    return Promise.reject(error)
  }
)

// Types
export interface DraftArticle {
  id: number
  title: string
  content: string
  source: string
  ai_summary?: string
  quality_score?: number
  created_at: string
  status: string
  tags?: string[]
}

export interface PublishedArticle {
  id: number
  title: string
  content: string
  published_at: string
  views?: number
  reactions?: number
  engagement_rate?: number
  source: string
  quality_score?: number
}

export interface DashboardStats {
  total_drafts: number
  total_published: number
  avg_quality_score: number
  total_views: number
  total_reactions: number
  engagement_rate: number
  articles_today: number
  top_sources: Array<{ source: string; count: number }>
}

export interface ChannelAnalyticsResponse {
  success: boolean
  data: ChannelAnalytics
  period_days: number
}

export interface SystemSettings {
  sources: Record<string, boolean>
  llm_provider: string
  llm_models: {
    analysis: string
    draft_generation: string
    ranking: string
  }
  dalle: {
    enabled: boolean
    model: string
    quality: string
    size: string
    auto_generate: boolean
    ask_on_review: boolean
  }
  auto_publish: {
    enabled: boolean
    mode: string
    max_per_day: number
    weekdays_only: boolean
    skip_holidays: boolean
  }
  filtering: {
    min_score: number
    min_content_length: number
    similarity_threshold: number
  }
  budget: {
    max_per_month: number
    warning_threshold: number
    stop_on_exceed: boolean
    switch_to_cheap: boolean
  }
  fetcher: {
    max_articles_per_source: number
  }
}

export interface LeadAnalytics {
  period_days: number
  overview: {
    total_leads: number
    qualified_leads: number
    converted_leads: number
    completed_magnet: number
    qualification_rate: number
    conversion_rate: number
    magnet_completion_rate: number
    avg_lead_score: number
    with_email: number
    with_phone: number
    with_company: number
  }
  daily_stats: Array<{
    date: string
    new_leads: number
    completed_magnet: number
    qualified: number
    avg_score: number
  }>
  top_leads: Array<{
    user_id: number
    username: string
    full_name: string
    email: string
    company: string
    lead_score: number
    expertise_level: string
    business_focus: string
    created_at: string
  }>
  sources_stats: Array<{
    source: string
    count: number
    avg_score: number
    completed_rate: number
  }>
}

export interface LeadROI {
  period_days: number
  costs: {
    api_cost: number
    total_cost: number
  }
  revenue: {
    total_leads: number
    quality_leads: number
    assumed_lead_value: number
    estimated_revenue: number
  }
  metrics: {
    profit: number
    roi_percent: number
    cost_per_lead: number
    cost_per_quality_lead: number
    avg_lead_score: number
  }
}

export interface LeadAnalyticsResponse {
  success: boolean
  data: LeadAnalytics
  roi: LeadROI
  period_days: number
}

export interface LeadStats {
  user_lead_score: number
  user_lead_status: string | null
  total_leads: number
  qualified_leads: number
  conversion_rate: number
  avg_lead_score: number
}

// API methods
export const apiMethods = {
  // Dashboard
  getDashboardStats: () => api.get<DashboardStats>(buildApiUrl('/api/miniapp/dashboard/stats')),
  getChannelAnalytics: (days = 7) => api.get<ChannelAnalyticsResponse>(buildApiUrl(`/api/miniapp/dashboard/channel-analytics?days=${days}`)),
  getLeadAnalytics: (days = 30) => api.get<LeadAnalyticsResponse>(buildApiUrl(`/api/miniapp/dashboard/lead-analytics?days=${days}`)),
  getLeadStats: () => api.get<LeadStats>(buildApiUrl('/api/miniapp/leads/stats')),

  // Leads
  getTopLeads: (limit = 10) => api.get(buildApiUrl(`/api/miniapp/leads/top?limit=${limit}`)),

  // Drafts
  getDrafts: (limit = 50) => api.get<DraftArticle[]>(buildApiUrl(`/api/miniapp/drafts?limit=${limit}`)),
  getDraft: (id: number) => api.get<DraftArticle>(buildApiUrl(`/api/miniapp/drafts/${id}`)),
  approveDraft: (id: number) => api.post(buildApiUrl(`/api/miniapp/drafts/${id}/approve`)),
  rejectDraft: (id: number, reason?: string) =>
    api.post(buildApiUrl(`/api/miniapp/drafts/${id}/reject`), { reason }),

  // Published
  getPublished: (limit = 50, offset = 0) =>
    api.get<PublishedArticle[]>(buildApiUrl(`/api/miniapp/published?limit=${limit}&offset=${offset}`)),
  getPublishedStats: (period: '7d' | '30d' | '90d') =>
    api.get(buildApiUrl(`/api/miniapp/published/stats?period=${period}`)),

  // Settings
  getSettings: () => api.get<SystemSettings>(buildApiUrl('/api/miniapp/settings')),
  updateSettings: (settings: Partial<SystemSettings>) =>
    api.put(buildApiUrl('/api/miniapp/settings'), settings),

  // Workflow
  getWorkflowStats: () => api.get(buildApiUrl('/api/miniapp/workflow/stats')),

  // Debug
  debugHealthCheck: () => api.get(buildApiUrl('/api/miniapp/debug/health')),

}
