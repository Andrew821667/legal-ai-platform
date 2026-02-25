'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiMethods } from '@/lib/api'
import { formatNumber } from '@/lib/utils'
import { TrendingUp, Users, Target, DollarSign, BarChart3, ArrowLeft, Calendar } from 'lucide-react'
import Link from 'next/link'

interface LeadAnalytics {
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

interface LeadROI {
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

interface LeadAnalyticsResponse {
  success: boolean
  data: LeadAnalytics
  roi: LeadROI
  period_days: number
}

export default function LeadsPage() {
  const [analytics, setAnalytics] = useState<LeadAnalytics | null>(null)
  const [roi, setRoi] = useState<LeadROI | null>(null)
  const [loading, setLoading] = useState(true)
  const [periodDays, setPeriodDays] = useState(30)

  useEffect(() => {
    loadAnalytics()
  }, [periodDays])

  const loadAnalytics = async () => {
    try {
      console.log('[Leads] Loading analytics from API')
      const response = await apiMethods.getLeadAnalytics(periodDays)
      console.log('[Leads] Analytics response:', response.data)
      setAnalytics(response.data.data)
      setRoi(response.data.roi)
    } catch (error: any) {
      console.error('[Leads] Failed to load analytics:', error)

      // Use mock data for development
      if (process.env.NODE_ENV === 'development') {
        console.warn('[Leads] Using mock data (development mode)')
        setAnalytics({
          period_days: periodDays,
          overview: {
            total_leads: 47,
            qualified_leads: 23,
            converted_leads: 5,
            completed_magnet: 35,
            qualification_rate: 48.9,
            conversion_rate: 21.7,
            magnet_completion_rate: 74.5,
            avg_lead_score: 68.2,
            with_email: 32,
            with_phone: 18,
            with_company: 29
          },
          daily_stats: [
            { date: '2025-01-01', new_leads: 3, completed_magnet: 2, qualified: 1, avg_score: 72 },
            { date: '2025-01-02', new_leads: 5, completed_magnet: 4, qualified: 2, avg_score: 68 },
            { date: '2025-01-03', new_leads: 2, completed_magnet: 1, qualified: 1, avg_score: 75 }
          ],
          top_leads: [
            {
              user_id: 123456789,
              username: 'lawyer_pro',
              full_name: 'Иванов Иван',
              email: 'ivanov@lawfirm.ru',
              company: 'Юридическая фирма "Право"',
              lead_score: 95,
              expertise_level: 'expert',
              business_focus: 'law_firm',
              created_at: '2025-01-01T10:00:00Z'
            }
          ],
          sources_stats: [
            { source: 'Telegram Channel', count: 47, avg_score: 68.2, completed_rate: 74.5 }
          ]
        })
        setRoi({
          period_days: periodDays,
          costs: {
            api_cost: 45.20,
            total_cost: 52.80
          },
          revenue: {
            total_leads: 47,
            quality_leads: 23,
            assumed_lead_value: 5000,
            estimated_revenue: 115000
          },
          metrics: {
            profit: 114947.20,
            roi_percent: 2175.3,
            cost_per_lead: 1.12,
            cost_per_quality_lead: 2.30,
            avg_lead_score: 68.2
          }
        })
      }
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-muted-foreground">Загрузка аналитики лидов...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white p-4">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link href="/">
              <Button variant="outline" size="sm">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Назад
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Аналитика лидов</h1>
              <p className="text-gray-600">
                ROI лид-магнита и конверсионные метрики
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Button
              variant={periodDays === 7 ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriodDays(7)}
            >
              7 дней
            </Button>
            <Button
              variant={periodDays === 30 ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriodDays(30)}
            >
              30 дней
            </Button>
            <Button
              variant={periodDays === 90 ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriodDays(90)}
            >
              90 дней
            </Button>
          </div>
        </div>

        {/* Overview Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Users className="w-4 h-4" />
                Всего лидов
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{analytics?.overview.total_leads || 0}</div>
              <p className="text-xs text-green-600 mt-1">
                +{analytics?.overview.completed_magnet || 0} завершили магнит
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <Target className="w-4 h-4" />
                Квалифицированные
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{analytics?.overview.qualified_leads || 0}</div>
              <p className="text-xs text-blue-600 mt-1">
                {analytics?.overview.qualification_rate?.toFixed(1) || '0.0'}% конверсия
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                Конверсия
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{analytics?.overview.conversion_rate?.toFixed(1) || '0.0'}%</div>
              <p className="text-xs text-purple-600 mt-1">
                {analytics?.overview.converted_leads || 0} конвертировано
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                <BarChart3 className="w-4 h-4" />
                Ср. скор
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{analytics?.overview.avg_lead_score?.toFixed(1) || '0.0'}</div>
              <p className="text-xs text-orange-600 mt-1">
                из 100 баллов
              </p>
            </CardContent>
          </Card>
        </div>

        {/* ROI Section */}
        {roi && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="w-5 h-5" />
                ROI лид-магнита
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-900">Затраты</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">API стоимость:</span>
                      <span className="font-medium">${roi.costs.api_cost.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Общие затраты:</span>
                      <span className="font-medium">${roi.costs.total_cost.toFixed(2)}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-900">Доходы</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Качественных лидов:</span>
                      <span className="font-medium">{roi.revenue.quality_leads}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Предположительная выручка:</span>
                      <span className="font-medium">${formatNumber(roi.revenue.estimated_revenue)}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-900">Метрики</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Прибыль:</span>
                      <span className={`font-medium ${roi.metrics.profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        ${roi.metrics.profit.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">ROI:</span>
                      <span className={`font-medium ${roi.metrics.roi_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {roi.metrics.roi_percent.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Стоимость лида:</span>
                      <span className="font-medium">${roi.metrics.cost_per_quality_lead.toFixed(2)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Top Leads */}
        <Card>
          <CardHeader>
            <CardTitle>Топ лидов</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {analytics?.top_leads.map((lead, index) => (
                <div key={lead.user_id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center space-x-4">
                    <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-sm font-medium text-blue-600">
                      {index + 1}
                    </div>
                    <div>
                      <p className="font-medium">{lead.username || `User ${lead.user_id}`}</p>
                      <p className="text-sm text-muted-foreground">
                        {lead.company || 'Компания не указана'} • {lead.expertise_level}
                      </p>
                      {lead.email && (
                        <p className="text-xs text-muted-foreground">{lead.email}</p>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-blue-600">{lead.lead_score}</div>
                    <p className="text-xs text-muted-foreground">баллов</p>
                  </div>
                </div>
              ))}

              {(!analytics?.top_leads || analytics.top_leads.length === 0) && (
                <div className="text-center py-8 text-muted-foreground">
                  <Users className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>Пока нет квалифицированных лидов</p>
                  <p className="text-sm">Лид-магнит ещё не запущен</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Sources Stats */}
        <Card>
          <CardHeader>
            <CardTitle>Источники лидов</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {analytics?.sources_stats.map((source, index) => (
                <div key={index} className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <p className="font-medium">{source.source}</p>
                    <p className="text-sm text-muted-foreground">
                      {source.completed_rate.toFixed(1)}% завершили магнит
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold">{source.count}</div>
                    <p className="text-xs text-muted-foreground">
                      ср. скор: {source.avg_score.toFixed(1)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}