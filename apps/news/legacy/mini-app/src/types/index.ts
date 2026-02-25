export interface User {
  id: number
  first_name: string
  last_name?: string
  username?: string
}

export interface Article {
  id: number
  title: string
  content: string
  source: string
  created_at: string
  published_at?: string
  views?: number
  reactions?: number
  quality_score?: number
  ai_summary?: string
  tags?: string[]
  status: 'draft' | 'approved' | 'published' | 'rejected'
}

export interface Stats {
  total_drafts: number
  total_published: number
  avg_quality_score: number
  total_views: number
  total_reactions: number
  engagement_rate: number
  articles_today: number
}

export interface ChartData {
  date: string
  views: number
  reactions: number
  articles: number
}

export interface SourceStats {
  source: string
  count: number
  avg_quality: number
  total_views: number
}

export interface ChannelAnalytics {
  period_days: number
  total_interactions: number
  unique_users: number
  channel_clicks: number
  article_views_from_channel: number
  total_from_channel: number
  conversion_rate: number
  top_articles: Array<{
    publication_id: number
    title: string
    views_from_channel: number
    unique_users: number
    published_at: string
  }>
  daily_stats: Array<{
    date: string
    channel_clicks: number
    article_views: number
    unique_users: number
  }>
}

export interface LeadProfile {
  user_id: number
  username?: string
  full_name?: string
  email?: string
  company?: string
  lead_score: number
  lead_status: string
  expertise_level?: string
  business_focus?: string
  created_at: string
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
  top_leads: LeadProfile[]
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
