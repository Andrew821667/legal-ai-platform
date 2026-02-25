'use client'

import { useEffect, useState } from 'react'
import { SDKProvider, useLaunchParams } from '@telegram-apps/sdk-react'

export function TelegramProvider({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return null
  }

  return (
    <SDKProvider acceptCustomStyles debug>
      <AppContent>{children}</AppContent>
    </SDKProvider>
  )
}

function AppContent({ children }: { children: React.ReactNode }) {
  const launchParams = useLaunchParams()

  useEffect(() => {
    // Initialize Telegram WebApp
    if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp
      tg.ready()
      tg.expand()

      // Set header color to match theme
      tg.setHeaderColor('#ffffff')
      tg.setBackgroundColor('#ffffff')
    }
  }, [])

  return <>{children}</>
}

// Type declaration for Telegram WebApp
declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        ready: () => void
        expand: () => void
        close: () => void
        showAlert: (message: string, callback?: () => void) => void
        setHeaderColor: (color: string) => void
        setBackgroundColor: (color: string) => void
        MainButton: {
          text: string
          color: string
          textColor: string
          isVisible: boolean
          isActive: boolean
          setText: (text: string) => void
          onClick: (callback: () => void) => void
          offClick: (callback: () => void) => void
          show: () => void
          hide: () => void
          enable: () => void
          disable: () => void
          showProgress: (leaveActive: boolean) => void
          hideProgress: () => void
        }
        initData: string
        initDataUnsafe: {
          user?: {
            id: number
            first_name: string
            last_name?: string
            username?: string
            language_code?: string
          }
          query_id?: string
          auth_date?: number
          hash?: string
        }
      }
    }
  }
}
