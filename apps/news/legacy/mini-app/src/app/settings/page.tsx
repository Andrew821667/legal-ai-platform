'use client'

import { useEffect, useState, useRef } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiMethods, SystemSettings } from '@/lib/api'
import { ArrowLeft, Save } from 'lucide-react'
import Link from 'next/link'

export default function SettingsPage() {
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  // Загрузка настроек при монтировании
  useEffect(() => {
    loadSettings()
  }, [])

  // Автообновление каждые 30 секунд
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      loadSettings(true) // Тихое обновление
    }, 30000) // 30 секунд

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  // Обновление при возврате на страницу
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        loadSettings(true) // Тихое обновление
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [])

  const loadSettings = async (silent = false) => {
    try {
      if (!silent) {
        console.log('[Settings] Loading from API...')
      }
      const response = await apiMethods.getSettings()
      if (!silent) {
        console.log('[Settings] Received:', response.data)
      }
      setSettings(response.data)
    } catch (error: any) {
      console.error('[Settings] Failed to load:', error)

      // Показываем ошибку только при первой загрузке, не при автообновлении
      if (!silent) {
        const errorMessage = error?.response?.data?.detail || error?.message || 'Неизвестная ошибка'

        if (window.Telegram?.WebApp) {
          window.Telegram.WebApp.showAlert(`Ошибка загрузки настроек: ${errorMessage}`)
        } else {
          alert(`Ошибка загрузки настроек: ${errorMessage}`)
        }
      }
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }

  const handleSave = async () => {
    if (!settings) return

    setSaving(true)
    try {
      await apiMethods.updateSettings(settings)
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.showAlert('Настройки успешно сохранены!')
      }
    } catch (error: any) {
      console.error('Failed to save settings:', error)
      const errorMessage = error?.response?.data?.detail || error?.message || 'Ошибка при сохранении настроек'
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.showAlert(`Ошибка: ${errorMessage}`)
      } else {
        alert(`Ошибка: ${errorMessage}`)
      }
    } finally {
      setSaving(false)
    }
  }

  const toggleSource = (source: string) => {
    if (!settings) return
    setSettings({
      ...settings,
      sources: {
        ...settings.sources,
        [source]: !settings.sources[source],
      },
    })
  }

  const updateDalle = (key: string, value: any) => {
    if (!settings) return
    setSettings({
      ...settings,
      dalle: {
        ...settings.dalle,
        [key]: value,
      },
    })
  }

  const updateAutoPublish = (key: string, value: any) => {
    if (!settings) return
    setSettings({
      ...settings,
      auto_publish: {
        ...settings.auto_publish,
        [key]: value,
      },
    })
  }

  const updateFiltering = (key: string, value: any) => {
    if (!settings) return
    setSettings({
      ...settings,
      filtering: {
        ...settings.filtering,
        [key]: value,
      },
    })
  }

  const updateFetcher = (key: string, value: any) => {
    if (!settings) return
    setSettings({
      ...settings,
      fetcher: {
        ...settings.fetcher,
        [key]: value,
      },
    })
  }

  const updateBudget = (key: string, value: any) => {
    if (!settings) return
    setSettings({
      ...settings,
      budget: {
        ...settings.budget,
        [key]: value,
      },
    })
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

  if (!settings) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-red-500 mb-4">Ошибка загрузки настроек</p>
          <Button onClick={() => loadSettings()}>Попробовать снова</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between py-2">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <h1 className="text-2xl font-bold">Настройки системы</h1>
          </div>
          <Button onClick={handleSave} disabled={saving}>
            <Save className="w-4 h-4 mr-2" />
            Сохранить
          </Button>
        </div>

        {/* Sources */}
        <Card>
          <CardHeader>
            <CardTitle>Источники новостей</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(settings?.sources || {}).map(([source, enabled]) => {
              const sourceNames: Record<string, string> = {
                google_news_ru: 'Google News (RU)',
                google_news_en: 'Google News (EN)',
                habr: 'Habr',
                perplexity_ru: 'Perplexity (RU)',
                perplexity_en: 'Perplexity (EN)',
                telegram_channels: 'Telegram каналы',
              }

              return (
                <div key={source} className="flex items-center justify-between">
                  <span>{sourceNames[source] || source}</span>
                  <button
                    onClick={() => toggleSource(source)}
                    className={`w-12 h-6 rounded-full transition-colors ${
                      enabled ? 'bg-green-500' : 'bg-gray-300'
                    }`}
                  >
                    <div
                      className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                        enabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              )
            })}
          </CardContent>
        </Card>

        {/* LLM Models */}
        <Card>
          <CardHeader>
            <CardTitle>Модели LLM</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">
                Модель для анализа
              </label>
              <select
                value={settings?.llm_models.analysis}
                onChange={(e) =>
                  setSettings({
                    ...settings!,
                    llm_models: {
                      ...settings!.llm_models,
                      analysis: e.target.value,
                    },
                  })
                }
                className="w-full p-2 border rounded"
              >
                <optgroup label="DeepSeek">
                  <option value="deepseek-chat">DeepSeek Chat</option>
                </optgroup>
                <optgroup label="OpenAI">
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                  <option value="gpt-4o">GPT-4o</option>
                </optgroup>
                <optgroup label="Perplexity">
                  <option value="sonar">Sonar</option>
                </optgroup>
              </select>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">
                Модель для генерации драфтов
              </label>
              <select
                value={settings?.llm_models.draft_generation}
                onChange={(e) =>
                  setSettings({
                    ...settings!,
                    llm_models: {
                      ...settings!.llm_models,
                      draft_generation: e.target.value,
                    },
                  })
                }
                className="w-full p-2 border rounded"
              >
                <optgroup label="DeepSeek">
                  <option value="deepseek-chat">DeepSeek Chat</option>
                </optgroup>
                <optgroup label="OpenAI">
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                  <option value="gpt-4o">GPT-4o</option>
                </optgroup>
                <optgroup label="Perplexity">
                  <option value="sonar">Sonar</option>
                </optgroup>
              </select>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">
                Модель для ранжирования
              </label>
              <select
                value={settings?.llm_models.ranking}
                onChange={(e) =>
                  setSettings({
                    ...settings!,
                    llm_models: {
                      ...settings!.llm_models,
                      ranking: e.target.value,
                    },
                  })
                }
                className="w-full p-2 border rounded"
              >
                <optgroup label="DeepSeek">
                  <option value="deepseek-chat">DeepSeek Chat</option>
                </optgroup>
                <optgroup label="OpenAI">
                  <option value="gpt-4o-mini">GPT-4o Mini</option>
                  <option value="gpt-4o">GPT-4o</option>
                </optgroup>
                <optgroup label="Perplexity">
                  <option value="sonar">Sonar</option>
                </optgroup>
              </select>
            </div>
          </CardContent>
        </Card>

        {/* DALL-E */}
        <Card>
          <CardHeader>
            <CardTitle>DALL-E генерация</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span>Включено</span>
              <button
                onClick={() => updateDalle('enabled', !settings?.dalle.enabled)}
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings?.dalle.enabled ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    settings?.dalle.enabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Модель</label>
              <select
                value={settings?.dalle.model}
                onChange={(e) => updateDalle('model', e.target.value)}
                className="w-full p-2 border rounded"
              >
                <option value="dall-e-3">DALL-E 3</option>
                <option value="dall-e-2">DALL-E 2</option>
              </select>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Качество</label>
              <select
                value={settings?.dalle.quality}
                onChange={(e) => updateDalle('quality', e.target.value)}
                className="w-full p-2 border rounded"
              >
                <option value="standard">Standard</option>
                <option value="hd">HD</option>
              </select>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Размер</label>
              <select
                value={settings?.dalle.size}
                onChange={(e) => updateDalle('size', e.target.value)}
                className="w-full p-2 border rounded"
              >
                <option value="1024x1024">1024x1024 (квадрат)</option>
                <option value="1024x1792">1024x1792 (вертикаль)</option>
                <option value="1792x1024">1792x1024 (горизонт)</option>
              </select>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm">Авто-генерация для всех постов</span>
              <button
                onClick={() => updateDalle('auto_generate', !settings?.dalle.auto_generate)}
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings?.dalle.auto_generate ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    settings?.dalle.auto_generate ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm">Спрашивать при модерации</span>
              <button
                onClick={() => updateDalle('ask_on_review', !settings?.dalle.ask_on_review)}
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings?.dalle.ask_on_review ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    settings?.dalle.ask_on_review ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Auto Publish */}
        <Card>
          <CardHeader>
            <CardTitle>Автопубликация</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span>Включено</span>
              <button
                onClick={() =>
                  updateAutoPublish('enabled', !settings?.auto_publish.enabled)
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings?.auto_publish.enabled ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    settings?.auto_publish.enabled
                      ? 'translate-x-6'
                      : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">Режим публикации</label>
              <select
                value={settings?.auto_publish.mode}
                onChange={(e) => updateAutoPublish('mode', e.target.value)}
                className="w-full p-2 border rounded"
              >
                <option value="best_time">Лучшее время</option>
                <option value="schedule">По расписанию</option>
                <option value="even">Равномерно</option>
              </select>
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">
                Макс. статей в день
              </label>
              <input
                type="number"
                value={settings?.auto_publish.max_per_day}
                onChange={(e) =>
                  updateAutoPublish('max_per_day', parseInt(e.target.value))
                }
                className="w-full p-2 border rounded"
                min="1"
                max="20"
              />
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm">Только в будни</span>
              <button
                onClick={() =>
                  updateAutoPublish('weekdays_only', !settings?.auto_publish.weekdays_only)
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings?.auto_publish.weekdays_only ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    settings?.auto_publish.weekdays_only ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm">Пропускать праздники</span>
              <button
                onClick={() =>
                  updateAutoPublish('skip_holidays', !settings?.auto_publish.skip_holidays)
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings?.auto_publish.skip_holidays ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    settings?.auto_publish.skip_holidays ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Filtering */}
        <Card>
          <CardHeader>
            <CardTitle>Фильтрация</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">
                Мин. оценка качества: {settings?.filtering.min_score?.toFixed(1)}
              </label>
              <input
                type="range"
                value={settings?.filtering.min_score}
                onChange={(e) =>
                  updateFiltering('min_score', parseFloat(e.target.value))
                }
                className="w-full"
                min="0"
                max="1"
                step="0.1"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">
                Мин. длина контента (символов)
              </label>
              <input
                type="number"
                value={settings?.filtering.min_content_length}
                onChange={(e) =>
                  updateFiltering('min_content_length', parseInt(e.target.value))
                }
                className="w-full p-2 border rounded"
                min="100"
                max="5000"
                step="50"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">
                Порог схожести: {settings?.filtering.similarity_threshold?.toFixed(2)}
              </label>
              <input
                type="range"
                value={settings?.filtering.similarity_threshold}
                onChange={(e) =>
                  updateFiltering('similarity_threshold', parseFloat(e.target.value))
                }
                className="w-full"
                min="0"
                max="1"
                step="0.05"
              />
            </div>
          </CardContent>
        </Card>

        {/* News Fetcher */}
        <Card>
          <CardHeader>
            <CardTitle>Сбор новостей</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">
                Максимум статей на источник
              </label>
              <input
                type="number"
                value={settings?.fetcher?.max_articles_per_source || 300}
                onChange={(e) => updateFetcher('max_articles_per_source', parseInt(e.target.value))}
                className="w-full p-2 border rounded"
                min="10"
                max="1000"
                step="10"
              />
              <p className="text-xs text-gray-500 mt-1">
                Сколько статей брать из каждого источника (10-1000)
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Budget */}
        <Card>
          <CardHeader>
            <CardTitle>Бюджет API</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">
                Макс. бюджет в месяц ($)
              </label>
              <input
                type="number"
                value={settings?.budget.max_per_month}
                onChange={(e) =>
                  updateBudget('max_per_month', parseFloat(e.target.value))
                }
                className="w-full p-2 border rounded"
                min="1"
                max="1000"
                step="0.5"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-2 block">
                Порог предупреждения ($)
              </label>
              <input
                type="number"
                value={settings?.budget.warning_threshold}
                onChange={(e) =>
                  updateBudget('warning_threshold', parseFloat(e.target.value))
                }
                className="w-full p-2 border rounded"
                min="1"
                max="1000"
                step="0.5"
              />
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm">Остановить при превышении лимита</span>
              <button
                onClick={() =>
                  updateBudget('stop_on_exceed', !settings?.budget.stop_on_exceed)
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings?.budget.stop_on_exceed ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    settings?.budget.stop_on_exceed ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm">Переключиться на дешевые модели</span>
              <button
                onClick={() =>
                  updateBudget('switch_to_cheap', !settings?.budget.switch_to_cheap)
                }
                className={`w-12 h-6 rounded-full transition-colors ${
                  settings?.budget.switch_to_cheap ? 'bg-green-500' : 'bg-gray-300'
                }`}
              >
                <div
                  className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    settings?.budget.switch_to_cheap ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </CardContent>
        </Card>

        <div className="pb-4">
          <Button onClick={handleSave} disabled={saving} className="w-full">
            <Save className="w-4 h-4 mr-2" />
            Сохранить все настройки
          </Button>
        </div>
      </div>
    </div>
  )
}
