'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiMethods } from '@/lib/api'
import { formatNumber } from '@/lib/utils'
import { BarChart3, FileText, TrendingUp, Users, ArrowRight, Target, DollarSign } from 'lucide-react'
import Link from 'next/link'

// Debug alerts for mobile
if (typeof window !== "undefined") {
  window.alert("=== MINI APP DEBUG ===\nAPI URL: " + (process.env.NEXT_PUBLIC_API_URL || "NOT SET") + "\nHostname: " + window.location.hostname);
}

interface DashboardStats {
  total_drafts: number
  total_published: number
  avg_quality_score: number
  total_views: number
  total_reactions: number
  engagement_rate: number
  articles_today: number
  top_sources: Array<{ source: string; count: number }>
}

interface LeadStats {
  user_lead_score: number
  user_lead_status: string | null
  total_leads: number
  qualified_leads: number
  conversion_rate: number
  avg_lead_score: number
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [leadStats, setLeadStats] = useState<LeadStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStats()
    loadLeadStats()
  }, [])

  const loadStats = async () => {
    try {
      console.log('[Dashboard] Loading stats from API:', process.env.NEXT_PUBLIC_API_URL)
      const response = await apiMethods.getDashboardStats()
      console.log('[Dashboard] API response:', response.data)
      setStats(response.data)
      setLoading(false)
    } catch (error: any) {
      console.error('[Dashboard] Failed to load stats:', error)
      console.error('[Dashboard] Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
        headers: error.response?.headers,
      })

      // Show error to user - try multiple methods
      const errorMessage = `Ошибка загрузки данных: ${error.message}\n\nAPI URL: ${process.env.NEXT_PUBLIC_API_URL || 'NOT SET'}`
      setError(errorMessage)

      if (typeof window !== 'undefined') {
        if (window.Telegram?.WebApp) {
          window.Telegram.WebApp.showAlert(errorMessage)
        } else if (window.alert) {
          window.alert(errorMessage)
        }
      }

      // Use fallback data in production too (don't leave user with infinite spinner)
      console.warn('[Dashboard] Using fallback data')
      setStats({
        total_drafts: 0,
        total_published: 0,
        avg_quality_score: 0,
        total_views: 0,
        total_reactions: 0,
        engagement_rate: 0,
        articles_today: 0,
        top_sources: []
      })

      setLoading(false)
    }
  }

  const loadLeadStats = async () => {
    try {
      console.log('[Dashboard] Loading lead stats from API')
      const response = await apiMethods.getLeadStats()
      console.log('[Dashboard] Lead stats response:', response.data)
      setLeadStats(response.data)
    } catch (error: any) {
      console.error('[Dashboard] Failed to load lead stats:', error)

      // Use fallback data for lead stats too
      setLeadStats({
        user_lead_score: 0,
        user_lead_status: null,
        total_leads: 0,
        qualified_leads: 0,
        conversion_rate: 0,
        avg_lead_score: 0
      })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-muted-foreground">Загрузка...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center p-4">
          <div className="text-red-500 text-xl mb-4">⚠️ Ошибка загрузки</div>
          <p className="text-muted-foreground mb-4">{error}</p>
          <Button onClick={() => window.location.reload()}>
            Попробовать снова
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white p-4">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center py-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Legal AI News
          </h1>
          <p className="text-gray-600">
            AI-driven news aggregation and analytics
          </p>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Черновики
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{stats?.total_drafts || 0}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Требуют модерации
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <BarChart3 className="w-4 h-4" />
                Опубликовано
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{stats?.total_published || 0}</div>
              <p className="text-xs text-green-600 mt-1">
                +{stats?.articles_today || 0} сегодня
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Users className="w-4 h-4" />
                Просмотры
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {formatNumber(stats?.total_views || 0)}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Всего просмотров
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                Вовлеченность
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {stats?.engagement_rate?.toFixed(1) || '0.0'}%
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {formatNumber(stats?.total_reactions || 0)} реакций
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Target className="w-4 h-4" />
                Лиды
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {leadStats?.total_leads || 0}
              </div>
              <p className="text-xs text-green-600 mt-1">
                {leadStats?.qualified_leads || 0} квалифицированных
              </p>
              <p className="text-xs text-blue-600 mt-1">
                Конверсия: {leadStats?.conversion_rate?.toFixed(1) || '0.0'}%
              </p>
              {leadStats?.user_lead_score && leadStats.user_lead_score > 0 && (
                <p className="text-xs text-purple-600 mt-1">
                  Ваш скор: {leadStats.user_lead_score}/100
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-2 gap-4">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href="/drafts">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Модерация контента</span>
                  <ArrowRight className="w-5 h-5 text-primary" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  Проверьте и одобрите новые статьи, собранные AI
                </p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full"
                      style={{ width: '60%' }}
                    ></div>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {stats?.total_drafts || 0} ожидают
                  </span>
                </div>
              </CardContent>
            </Link>
          </Card>

          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href="/analytics">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Аналитика публикаций</span>
                  <ArrowRight className="w-5 h-5 text-primary" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  Детальная статистика по публикациям и источникам
                </p>
                <div className="flex gap-4">
                  <div>
                    <div className="text-2xl font-bold text-green-600">
                      {stats?.avg_quality_score?.toFixed(1) || '0.0'}
                    </div>
                    <p className="text-xs text-muted-foreground">Ср. качество</p>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-blue-600">
                      {stats?.total_published || 0}
                    </div>
                    <p className="text-xs text-muted-foreground">Статей</p>
                  </div>
                </div>
              </CardContent>
            </Link>
          </Card>

          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href="/channelanalytics">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Аналитика каналов</span>
                  <ArrowRight className="w-5 h-5 text-primary" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  Статистика переходов из Telegram канала
                </p>
                <div className="flex gap-4">
                  <div>
                    <div className="text-2xl font-bold text-purple-600">
                      33.3%
                    </div>
                    <p className="text-xs text-muted-foreground">Конверсия</p>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-orange-600">
                      4
                    </div>
                    <p className="text-xs text-muted-foreground">Переходов</p>
                  </div>
                </div>
              </CardContent>
            </Link>
          </Card>

          <Card className="hover:shadow-lg transition-shadow cursor-pointer">
            <Link href="/leads">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Аналитика лидов</span>
                  <ArrowRight className="w-5 h-5 text-primary" />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  ROI лид-магнита и конверсионные метрики
                </p>
                <div className="flex gap-4">
                  <div>
                    <div className="text-2xl font-bold text-green-600">
                      {leadStats?.conversion_rate?.toFixed(1) || '0.0'}%
                    </div>
                    <p className="text-xs text-muted-foreground">Конверсия</p>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-blue-600">
                      {leadStats?.avg_lead_score?.toFixed(0) || '0'}
                    </div>
                    <p className="text-xs text-muted-foreground">Ср. скор</p>
                  </div>
                </div>
              </CardContent>
            </Link>
          </Card>
        </div>

        {/* Additional Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Быстрые действия</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <Link href="/settings">
                <Button variant="outline" className="w-full">
                  Настройки
                </Button>
              </Link>
              <Link href="/published">
                <Button variant="outline" className="w-full">
                  Опубликованное
                </Button>
              </Link>
              <Link href="/leads">
                <Button variant="outline" className="w-full border-purple-300 text-purple-700 hover:bg-purple-50">
                  📊 Лиды
                </Button>
              </Link>
              <Link href="/debug">
                <Button variant="outline" className="w-full border-orange-300 text-orange-700 hover:bg-orange-50">
                  🔧 Debug
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
