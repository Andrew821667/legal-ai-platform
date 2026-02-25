'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiMethods, SystemSettings } from '@/lib/api'
import { ArrowLeft, Save } from 'lucide-react'
import Link from 'next/link'

export default function SettingsPage() {
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      console.log('[Settings] Loading from API...')
      const response = await apiMethods.getSettings()
      console.log('[Settings] Received:', response.data)
      setSettings(response.data)
    } catch (error: any) {
      console.error('[Settings] Failed to load:', error)
      const errorMessage = error?.response?.data?.detail || error?.message || 'Неизвестная ошибка'

      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.showAlert(`Ошибка загрузки настроек: ${errorMessage}`)
      } else {
        alert(`Ошибка загрузки настроек: ${errorMessage}`)
      }
    } finally {
      setLoading(false)
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
      console.error('[Settings] Failed to save:', error)
      if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.showAlert(`Ошибка сохранения: ${error.message}`)
      }
    } finally {
      setSaving(false)
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
        <div className="flex items-center justify-between py-2">
          <div className="flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="w-5 h-5" />
              </Button>
            </Link>
            <h1 className="text-2xl font-bold">Настройки системы</h1>
          </div>
          <Button onClick={handleSave} disabled={saving || !settings}>
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </div>

        {!settings ? (
          <div className="text-center py-8">
            <p className="text-muted-foreground">Не удалось загрузить настройки</p>
          </div>
        ) : (
          <div className="grid gap-6">
            {/* Settings content will go here */}
            <Card>
              <CardHeader>
                <CardTitle>Настройки загружены успешно</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Система настроек готова к работе.
                </p>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}