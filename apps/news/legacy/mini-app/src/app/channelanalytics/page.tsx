'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiMethods } from '@/lib/api'
import { formatNumber } from '@/lib/utils'
import { ArrowLeft, TrendingUp, Eye, Users, MousePointer, Target } from 'lucide-react'
import Link from 'next/link'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

interface ChannelAnalytics {
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

export default function ChannelAnalyticsPage() {
  const [period, setPeriod] = useState<7 | 30 | 90>(7) // Updated at: 2026-01-03
  const [stats, setStats] = useState<ChannelAnalytics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [period])

  const loadStats = async () => {
    setLoading(true)
    try {
      console.log('[Channel Analytics] Loading stats for period:', period)
      const response = await apiMethods.getChannelAnalytics(period)
      console.log('[Channel Analytics] Received stats:', response.data)
      setStats(response.data.data)
    } catch (error: any) {
      console.error('[Channel Analytics] Failed to load stats:', error)
      console.error('[Channel Analytics] Error details:', {
        message: error.message,
        status: error.response?.status,
        data: error.response?.data
      })

      // Show error to user
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.showAlert(`Ошибка загрузки аналитики каналов: ${error.message}`)
      }

      // Mock data ONLY in development
      if (process.env.NODE_ENV === 'development') {
        console.warn('[Channel Analytics] Using mock data (development mode)')
        setStats({
          period_days: period,
          total_interactions: 4,
          unique_users: 1,
          channel_clicks: 3,
          article_views_from_channel: 1,
          total_from_channel: 4,
          conversion_rate: 33.33,
          top_articles: [
            {
              publication_id: 1,
              title: 'Новый порядок для создания национальной политики в области AI',
              views_from_channel: 2,
              unique_users: 1,
              published_at: '2025-12-25T18:48:51.164103'
            },
            {
              publication_id: 2,
              title: 'Уроки для бизнеса из нового отчёта ABA о Legal AI',
              views_from_channel: 1,
              unique_users: 1,
              published_at: '2025-12-25T19:16:07.953308'
            },
            {
              publication_id: 3,
              title: 'Защита авторских прав в эпоху ИИ',
              views_from_channel: 1,
              unique_users: 1,
              published_at: '2025-12-25T20:24:18.836562'
            }
          ],
          daily_stats: [
            { date: '2026-01-03', channel_clicks: 3, article_views: 1, unique_users: 1 }
          ]
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
          <p className="text-muted-foreground">Загрузка аналитики каналов...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center gap-4 py-2">
          <Link href="/">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <h1 className="text-2xl font-bold">Аналитика каналов</h1>
        </div>

        {/* Period selector */}
        <div className="flex gap-2">
          <Button
            variant={period === 7 ? 'default' : 'outline'}
            onClick={() => setPeriod(7)}
            size="sm"
          >
            7 дней
          </Button>
          <Button
            variant={period === 30 ? 'default' : 'outline'}
            onClick={() => setPeriod(30)}
            size="sm"
          >
            30 дней
          </Button>
          <Button
            variant={period === 90 ? 'default' : 'outline'}
            onClick={() => setPeriod(90)}
            size="sm"
          >
            90 дней
          </Button>
        </div>

        {/* Summary stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground mb-1 flex items-center gap-1">
                <MousePointer className="w-3 h-3" />
                Переходы из канала
              </div>
              <div className="text-2xl font-bold">{stats?.total_from_channel || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground mb-1 flex items-center gap-1">
                <Users className="w-3 h-3" />
                Уникальные пользователи
              </div>
              <div className="text-2xl font-bold">{stats?.unique_users || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground mb-1 flex items-center gap-1">
                <Eye className="w-3 h-3" />
                Просмотры статей
              </div>
              <div className="text-2xl font-bold">{stats?.article_views_from_channel || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground mb-1 flex items-center gap-1">
                <Target className="w-3 h-3" />
                Конверсия
              </div>
              <div className="text-2xl font-bold">{stats?.conversion_rate?.toFixed(1) || '0.0'}%</div>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        {stats?.daily_stats && stats.daily_stats.length > 0 && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Динамика переходов из канала</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={stats.daily_stats}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="channel_clicks"
                      stroke="#3b82f6"
                      name="Клики из канала"
                    />
                    <Line
                      type="monotone"
                      dataKey="article_views"
                      stroke="#10b981"
                      name="Просмотры статей"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Уникальные пользователи по дням</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={stats.daily_stats}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="unique_users" fill="#3b82f6" name="Пользователи" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </>
        )}

        {/* Top articles */}
        <Card>
          <CardHeader>
            <CardTitle>Топ статей по переходам из канала</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats?.top_articles?.map((article, index) => (
                <div
                  key={article.publication_id}
                  className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center justify-center w-8 h-8 bg-primary text-white rounded-full font-bold flex-shrink-0">
                    {index + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-sm line-clamp-2 mb-1">
                      {article.title}
                    </h4>
                    <div className="flex gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Eye className="w-3 h-3" />
                        {formatNumber(article.views_from_channel)} просмотров
                      </span>
                      <span className="flex items-center gap-1">
                        <Users className="w-3 h-3" />
                        {article.unique_users} пользователей
                      </span>
                    </div>
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