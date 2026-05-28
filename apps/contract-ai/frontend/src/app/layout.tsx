import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'

const siteUrl = process.env.NEXT_PUBLIC_CONTRACT_SITE_URL || 'https://contract.ai-verdict.ru'

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: 'Contract AI System',
    template: '%s | Contract AI System',
  },
  description:
    'Интеллектуальная система AI Verdict для проверки договоров, выявления рисков и подготовки договорного контура.',
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-snippet': -1,
      'max-image-preview': 'large',
      'max-video-preview': -1,
    },
  },
  openGraph: {
    type: 'website',
    locale: 'ru_RU',
    url: siteUrl,
    title: 'Contract AI System',
    description:
      'Проверка договоров, подсветка рисков и демонстрационный контур с 3 бесплатными договорами в месяц.',
    siteName: 'Contract AI System',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru">
      <body className="font-sans">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}
