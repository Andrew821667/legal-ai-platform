import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { TelegramProvider } from '@/components/TelegramProvider'

const inter = Inter({ subsets: ['latin', 'cyrillic'] })

export const metadata: Metadata = {
  title: 'AI Verdict News',
  description: 'AI-powered legal news aggregator and analytics with channel analytics',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru">
      <body className={inter.className}>
        <TelegramProvider>
          {children}
        </TelegramProvider>
      </body>
    </html>
  )
}
