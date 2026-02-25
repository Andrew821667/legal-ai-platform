'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiMethods } from '@/lib/api'
import { formatNumber } from '@/lib/utils'
import { ArrowLeft, TrendingUp, Eye, Heart, X, ExternalLink } from 'lucide-react'
import Link from 'next/link'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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

interface PublishedStats {
  period: string
  total_articles: number
  total_views: number
  total_reactions: number
  avg_quality_score: number
  engagement_rate: number
  top_articles: Array<{
    id: number
    title: string
    content: string
    views: number
    reactions: number
    published_at: string
    message_id?: number
    channel_id?: string
  }>
  daily_stats: Array<{
    date: string
    views: number
    reactions: number
    articles: number
  }>
}

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<'7d' | '30d' | '90d'>('7d')
  const [stats, setStats] = useState<PublishedStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedArticle, setSelectedArticle] = useState<PublishedStats['top_articles'][0] | null>(null)

  useEffect(() => {
    loadStats()
  }, [period])

  const openInTelegram = (article: PublishedStats['top_articles'][0]) => {
    if (article.channel_id && article.message_id) {
      const channelUsername = article.channel_id.replace('@', '')
      const url = `https://t.me/${channelUsername}/${article.message_id}`
      window.open(url, '_blank')
    }
  }

  const loadStats = async () => {
    setLoading(true)
    try {
      console.log('[Analytics] Loading stats for period:', period)
      const response = await apiMethods.getPublishedStats(period)
      console.log('[Analytics] Received stats:', response.data)
      setStats(response.data)
    } catch (error: any) {
      console.error('[Analytics] Failed to load stats:', error)
      console.error('[Analytics] Error details:', {
        message: error.message,
        status: error.response?.status,
        data: error.response?.data
      })

      // Show error to user
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.showAlert(`Ошибка загрузки аналитики: ${error.message}`)
      }

      // Mock data ONLY in development
      if (process.env.NODE_ENV === 'development') {
        console.warn('[Analytics] Using mock data (development mode)')
        setStats({
          period,
          total_articles: 45,
          total_views: 12500,
          total_reactions: 680,
          avg_quality_score: 8.2,
          engagement_rate: 5.4,
          top_articles: [
            {
              id: 1,
              title: 'Верховный суд разъяснил вопросы применения ИИ',
              content: 'Верховный суд РФ опубликовал разъяснения по применению искусственного интеллекта...',
              views: 2340,
              reactions: 156,
              published_at: new Date().toISOString(),
              message_id: 123,
              channel_id: '@test_channel',
            },
            {
              id: 2,
              title: 'Новые требования к обработке ПДн в 2025',
              content: 'С 1 января 2025 года вступают в силу новые требования...',
              views: 1980,
              reactions: 124,
              published_at: new Date().toISOString(),
              message_id: 124,
              channel_id: '@test_channel',
            },
          ],
          daily_stats: [
            { date: '01.12', views: 450, reactions: 28, articles: 3 },
            { date: '02.12', views: 680, reactions: 42, articles: 4 },
            { date: '03.12', views: 520, reactions: 31, articles: 3 },
            { date: '04.12', views: 890, reactions: 58, articles: 5 },
            { date: '05.12', views: 720, reactions: 45, articles: 4 },
            { date: '06.12', views: 960, reactions: 64, articles: 6 },
            { date: '07.12', views: 810, reactions: 52, articles: 4 },
          ],
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
          <p className="text-muted-foreground">Загрузка...</p>
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
          <h1 className="text-2xl font-bold">Аналитика</h1>
        </div>

        {/* Period selector */}
        <div className="flex gap-2">
          <Button
            variant={period === '7d' ? 'default' : 'outline'}
            onClick={() => setPeriod('7d')}
            size="sm"
          >
            7 дней
          </Button>
          <Button
            variant={period === '30d' ? 'default' : 'outline'}
            onClick={() => setPeriod('30d')}
            size="sm"
          >
            30 дней
          </Button>
          <Button
            variant={period === '90d' ? 'default' : 'outline'}
            onClick={() => setPeriod('90d')}
            size="sm"
          >
            90 дней
          </Button>
        </div>

        {/* Summary stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground mb-1">Статей</div>
              <div className="text-2xl font-bold">{stats?.total_articles || 0}</div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground flex items-center gap-1 mb-1">
                <Eye className="w-3 h-3" />
                Просмотры
              </div>
              <div className="text-2xl font-bold">
                {formatNumber(stats?.total_views || 0)}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground flex items-center gap-1 mb-1">
                <Heart className="w-3 h-3" />
                Реакции
              </div>
              <div className="text-2xl font-bold">
                {formatNumber(stats?.total_reactions || 0)}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="text-sm text-muted-foreground flex items-center gap-1 mb-1">
                <TrendingUp className="w-3 h-3" />
                Вовлеченность
              </div>
              <div className="text-2xl font-bold">
                {stats?.engagement_rate?.toFixed(1) || '0.0'}%
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        {stats?.daily_stats && stats.daily_stats.length > 0 && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Динамика просмотров и реакций</CardTitle>
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
                      dataKey="views"
                      stroke="#3b82f6"
                      name="Просмотры"
                    />
                    <Line
                      type="monotone"
                      dataKey="reactions"
                      stroke="#10b981"
                      name="Реакции"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Публикации по дням</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={stats.daily_stats}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="articles" fill="#3b82f6" name="Статьи" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </>
        )}

        {/* Top articles */}
        <Card>
          <CardHeader>
            <CardTitle>Топ статей</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats?.top_articles?.map((article, index) => (
                <div
                  key={article.id}
                  onClick={() => setSelectedArticle(article)}
                  className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors"
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
                        {formatNumber(article.views)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Heart className="w-3 h-3" />
                        {formatNumber(article.reactions)}
                      </span>
                      <span>
                        {((article.reactions / article.views) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Quality metrics */}
        <Card>
          <CardHeader>
            <CardTitle>Качество контента</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>Средняя оценка качества</span>
                  <span className="font-semibold">
                    {stats?.avg_quality_score?.toFixed(1) || '0.0'} / 10
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-green-500 h-2 rounded-full"
                    style={{
                      width: `${((stats?.avg_quality_score || 0) / 10) * 100}%`,
                    }}
                  ></div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Article preview dialog */}
      <Dialog open={!!selectedArticle} onOpenChange={() => setSelectedArticle(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-lg">
              {selectedArticle?.title}
            </DialogTitle>
          </DialogHeader>
          <div className="px-6 pb-6 space-y-4">
            {/* Stats */}
            <div className="flex gap-6 text-sm text-muted-foreground border-b pb-3">
              <span className="flex items-center gap-1">
                <Eye className="w-4 h-4" />
                {formatNumber(selectedArticle?.views || 0)} просмотров
              </span>
              <span className="flex items-center gap-1">
                <Heart className="w-4 h-4" />
                {formatNumber(selectedArticle?.reactions || 0)} реакций
              </span>
              <span>
                {selectedArticle?.published_at &&
                  new Date(selectedArticle.published_at).toLocaleDateString('ru-RU', {
                    day: 'numeric',
                    month: 'long',
                    year: 'numeric',
                  })}
              </span>
            </div>

            {/* Content */}
            <div className="prose prose-sm max-w-none">
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {selectedArticle?.content}
              </p>
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-3 border-t">
              {selectedArticle?.message_id && selectedArticle?.channel_id && (
                <Button
                  onClick={() => selectedArticle && openInTelegram(selectedArticle)}
                  variant="default"
                  className="flex items-center gap-2"
                >
                  <ExternalLink className="w-4 h-4" />
                  Открыть в канале
                </Button>
              )}
              <Button
                onClick={() => setSelectedArticle(null)}
                variant="outline"
              >
                Закрыть
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
