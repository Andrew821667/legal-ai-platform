'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { apiMethods } from '@/lib/api'
import { ArrowLeft, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import Link from 'next/link'

interface DebugInfo {
  timestamp: string
  test: string
  status: 'success' | 'error' | 'pending'
  message: string
  data?: any
}

export default function DebugPage() {
  const [debugLogs, setDebugLogs] = useState<DebugInfo[]>([])
  const [isRunning, setIsRunning] = useState(false)

  const addLog = (test: string, status: 'success' | 'error' | 'pending', message: string, data?: any) => {
    setDebugLogs(prev => [...prev, {
      timestamp: new Date().toLocaleTimeString(),
      test,
      status,
      message,
      data
    }])
  }

  const runDiagnostics = async () => {
    setIsRunning(true)
    setDebugLogs([])

    // Test 1: Environment variables
    addLog('Environment', 'pending', 'Checking environment variables...')
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL
      const nodeEnv = process.env.NODE_ENV
      const botUsername = process.env.NEXT_PUBLIC_BOT_USERNAME

      addLog('Environment', 'success', 'Environment variables loaded', {
        NEXT_PUBLIC_API_URL: apiUrl || 'NOT SET',
        NEXT_PUBLIC_BOT_USERNAME: botUsername || 'NOT SET',
        NODE_ENV: nodeEnv,
        window_location: typeof window !== 'undefined' ? window.location.href : 'N/A',
        api_base_url: apiUrl
      })
    } catch (error: any) {
      addLog('Environment', 'error', error.message)
    }

    // Test 2: Telegram WebApp
    addLog('Telegram', 'pending', 'Checking Telegram WebApp...')
    try {
      if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
        const initData = window.Telegram.WebApp.initDataUnsafe
        addLog('Telegram', 'success', 'Telegram WebApp available', {
          user_id: initData?.user?.id || 'N/A',
          username: initData?.user?.username || 'N/A',
          first_name: initData?.user?.first_name || 'N/A',
          platform: (window.Telegram.WebApp as any).platform || 'unknown'
        })
      } else {
        addLog('Telegram', 'error', 'Telegram WebApp not available')
      }
    } catch (error: any) {
      addLog('Telegram', 'error', error.message)
    }

    // Test 3: Dashboard Stats API
    addLog('API /dashboard/stats', 'pending', 'Testing dashboard stats endpoint...')
    try {
      const response = await apiMethods.getDashboardStats()
      addLog('API /dashboard/stats', 'success', 'API call successful', {
        total_drafts: response.data.total_drafts,
        total_published: response.data.total_published,
        response_size: JSON.stringify(response.data).length + ' bytes'
      })
    } catch (error: any) {
      addLog('API /dashboard/stats', 'error', error.message, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        config_url: error.config?.url,
        config_baseURL: error.config?.baseURL
      })
    }

    // Test 4: Drafts API
    addLog('API /drafts', 'pending', 'Testing drafts endpoint...')
    try {
      const response = await apiMethods.getDrafts(5)
      addLog('API /drafts', 'success', 'API call successful', {
        count: response.data.length,
        first_draft: response.data[0] ? {
          id: response.data[0].id,
          title: response.data[0].title?.substring(0, 50) + '...'
        } : null
      })
    } catch (error: any) {
      addLog('API /drafts', 'error', error.message, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data
      })
    }

    // Test 5: Published API
    addLog('API /published', 'pending', 'Testing published endpoint...')
    try {
      const response = await apiMethods.getPublished(5)
      addLog('API /published', 'success', 'API call successful', {
        count: response.data.length,
        first_article: response.data[0] ? {
          id: response.data[0].id,
          title: response.data[0].title?.substring(0, 50) + '...'
        } : null
      })
    } catch (error: any) {
      addLog('API /published', 'error', error.message, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data
      })
    }

    // Test 6: Settings API
    addLog('API /settings', 'pending', 'Testing settings endpoint...')
    try {
      const response = await apiMethods.getSettings()
      addLog('API /settings', 'success', 'API call successful', {
        sources_count: Object.keys(response.data.sources || {}).length,
        llm_models: response.data.llm_models
      })
    } catch (error: any) {
      addLog('API /settings', 'error', error.message, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data
      })
    }

    // Test 7: Debug Health Check
    addLog('API /debug/health', 'pending', 'Testing debug health endpoint...')
    try {
      const response = await apiMethods.debugHealthCheck()
      addLog('API /debug/health', 'success', 'API call successful', {
        status: response.data.status,
        auth_status: response.data.auth_status,
        db_status: response.data.database,
        db_stats: response.data.db_stats,
        environment: response.data.environment
      })
    } catch (error: any) {
      addLog('API /debug/health', 'error', error.message, {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data
      })
    }

    setIsRunning(false)
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />
      case 'pending':
        return <AlertCircle className="w-5 h-5 text-yellow-500 animate-pulse" />
      default:
        return null
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'border-l-4 border-green-500 bg-green-50'
      case 'error':
        return 'border-l-4 border-red-500 bg-red-50'
      case 'pending':
        return 'border-l-4 border-yellow-500 bg-yellow-50'
      default:
        return ''
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-4xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center gap-4 py-2">
          <Link href="/">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">🔧 Debug Console</h1>
            <p className="text-sm text-muted-foreground">
              Diagnostic tool for API connectivity
            </p>
          </div>
        </div>

        {/* Run Tests Button */}
        <Card>
          <CardContent className="pt-6">
            <Button
              onClick={runDiagnostics}
              disabled={isRunning}
              className="w-full"
              size="lg"
            >
              {isRunning ? '⏳ Running tests...' : '🚀 Run All Diagnostics'}
            </Button>
          </CardContent>
        </Card>

        {/* Debug Logs */}
        {debugLogs.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Test Results</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {debugLogs.map((log, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-lg ${getStatusColor(log.status)}`}
                >
                  <div className="flex items-start gap-3">
                    {getStatusIcon(log.status)}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <h3 className="font-semibold text-sm">{log.test}</h3>
                        <span className="text-xs text-gray-500">{log.timestamp}</span>
                      </div>
                      <p className="text-sm mb-2">{log.message}</p>
                      {log.data && (
                        <details className="text-xs bg-white bg-opacity-50 rounded p-2 mt-2">
                          <summary className="cursor-pointer font-medium mb-2">
                            📊 Details
                          </summary>
                          <pre className="overflow-x-auto whitespace-pre-wrap break-words">
                            {JSON.stringify(log.data, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Summary */}
        {!isRunning && debugLogs.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-green-600">
                    {debugLogs.filter(l => l.status === 'success').length}
                  </div>
                  <div className="text-xs text-muted-foreground">Passed</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-600">
                    {debugLogs.filter(l => l.status === 'error').length}
                  </div>
                  <div className="text-xs text-muted-foreground">Failed</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-gray-600">
                    {debugLogs.length}
                  </div>
                  <div className="text-xs text-muted-foreground">Total</div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Instructions */}
        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="pt-6">
            <h3 className="font-semibold mb-2">📝 How to use:</h3>
            <ol className="text-sm space-y-1 list-decimal list-inside">
              <li>Click "Run All Diagnostics" button</li>
              <li>Wait for all tests to complete</li>
              <li>Check which tests failed (red icons)</li>
              <li>Click "Details" on failed tests to see error info</li>
              <li>Share screenshot with developer if needed</li>
            </ol>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
