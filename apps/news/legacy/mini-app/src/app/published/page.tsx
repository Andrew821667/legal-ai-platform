'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiMethods, PublishedArticle } from '@/lib/api'
import { ArrowLeft, Eye, Heart, TrendingUp, ExternalLink } from 'lucide-react'
import Link from 'next/link'

export default function PublishedPage() {
  const [articles, setArticles] = useState<PublishedArticle[]>([])
  const [selectedArticle, setSelectedArticle] = useState<PublishedArticle | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadPublished()
  }, [])

  const loadPublished = async () => {
    try {
      console.log('[Published] Loading from API...')
      const response = await apiMethods.getPublished(50)
      console.log('[Published] Received', response.data.length, 'articles')
      setArticles(response.data)
    } catch (error: any) {
      console.error('[Published] Failed to load:', error)
      console.error('[Published] Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
      })

      // Show error to user
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.showAlert(`Ошибка загрузки публикаций: ${error.message}`)
      }

      // Mock data ONLY in development
      if (process.env.NODE_ENV === 'development') {
        console.warn('[Published] Using mock data (development mode)')
        setArticles([
          {
            id: 1,
            title: 'Новый закон о персональных данных принят Госдумой',
            content: 'Государственная Дума одобрила законопроект об ужесточении требований к обработке персональных данных...',
            published_at: new Date(Date.now() - 86400000).toISOString(),
            views: 1234,
            reactions: 89,
            engagement_rate: 7.2,
            source: 'Google News',
            quality_score: 8.5,
          },
          {
            id: 2,
            title: 'ИИ помогает судьям в принятии решений',
            content: 'Судебная коллегия по экономическим спорам начала использовать AI...',
            published_at: new Date(Date.now() - 172800000).toISOString(),
            views: 892,
            reactions: 54,
            engagement_rate: 6.1,
            source: 'Habr',
            quality_score: 7.8,
          },
        ])
      }
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (isoString: string) => {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    const diffDays = Math.floor(diffHours / 24)

    if (diffHours < 24) {
      return `${diffHours} ч назад`
    } else if (diffDays < 7) {
      return `${diffDays} дн назад`
    } else {
      return date.toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
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
          <div>
            <h1 className="text-2xl font-bold">Опубликованные статьи</h1>
            <p className="text-sm text-muted-foreground">
              {articles.length} {articles.length === 1 ? 'статья' : 'статей'} опубликовано
            </p>
          </div>
        </div>

        {articles.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-muted-foreground">Нет опубликованных статей</p>
            </CardContent>
          </Card>
        ) : !selectedArticle ? (
          /* List view */
          <div className="space-y-3">
            {articles.map((article) => (
              <Card
                key={article.id}
                className="cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => setSelectedArticle(article)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-lg mb-1 line-clamp-2">
                        {article.title}
                      </h3>
                      <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                        {article.content}
                      </p>
                      <div className="flex flex-wrap gap-2 items-center text-xs">
                        <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
                          {article.source}
                        </span>
                        <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded flex items-center gap-1">
                          <Eye className="w-3 h-3" />
                          {article.views ?? 0}
                        </span>
                        <span className="px-2 py-1 bg-pink-100 text-pink-700 rounded flex items-center gap-1">
                          <Heart className="w-3 h-3" />
                          {article.reactions ?? 0}
                        </span>
                        <span className="px-2 py-1 bg-green-100 text-green-700 rounded flex items-center gap-1">
                          <TrendingUp className="w-3 h-3" />
                          {(article.engagement_rate ?? 0).toFixed(1)}%
                        </span>
                        <span className="text-muted-foreground">
                          {formatDate(article.published_at)}
                        </span>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          /* Detail view */
          <div className="space-y-4">
            <Button
              variant="ghost"
              onClick={() => setSelectedArticle(null)}
              className="mb-2"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Назад к списку
            </Button>

            <Card>
              <CardHeader>
                <CardTitle className="text-xl">{selectedArticle.title}</CardTitle>
                <div className="flex flex-wrap gap-2 mt-2">
                  <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">
                    {selectedArticle.source}
                  </span>
                  {selectedArticle.quality_score && (
                    <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">
                      Оценка: {selectedArticle.quality_score.toFixed(1)}/10
                    </span>
                  )}
                  <span className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded">
                    {formatDate(selectedArticle.published_at)}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Metrics */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 bg-purple-50 rounded-lg border border-purple-200 text-center">
                    <Eye className="w-5 h-5 text-purple-600 mx-auto mb-1" />
                    <p className="text-lg font-bold text-purple-900">
                      {selectedArticle.views ?? 0}
                    </p>
                    <p className="text-xs text-purple-700">Просмотры</p>
                  </div>
                  <div className="p-3 bg-pink-50 rounded-lg border border-pink-200 text-center">
                    <Heart className="w-5 h-5 text-pink-600 mx-auto mb-1" />
                    <p className="text-lg font-bold text-pink-900">
                      {selectedArticle.reactions ?? 0}
                    </p>
                    <p className="text-xs text-pink-700">Реакции</p>
                  </div>
                  <div className="p-3 bg-green-50 rounded-lg border border-green-200 text-center">
                    <TrendingUp className="w-5 h-5 text-green-600 mx-auto mb-1" />
                    <p className="text-lg font-bold text-green-900">
                      {(selectedArticle.engagement_rate ?? 0).toFixed(1)}%
                    </p>
                    <p className="text-xs text-green-700">Вовлечённость</p>
                  </div>
                </div>

                {/* Content */}
                <div>
                  <p className="text-sm font-medium mb-2">Содержание:</p>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {selectedArticle.content}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
