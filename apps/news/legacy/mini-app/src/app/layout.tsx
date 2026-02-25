import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { TelegramProvider } from '@/components/TelegramProvider'

const inter = Inter({ subsets: ['latin', 'cyrillic'] })

export const metadata: Metadata = {
  title: 'Legal AI News',
  description: 'AI-powered legal news aggregator and analytics with channel analytics',
  viewport: 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no',
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
