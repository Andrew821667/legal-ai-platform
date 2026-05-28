import type { Metadata } from 'next'

import HomeClient from '@/components/pages/HomeClient'

export const metadata: Metadata = {
  title: 'Contract AI System',
  description:
    'Contract AI System: проверка договоров, выявление рисков и демонстрационный контур с 3 бесплатными договорами в месяц.',
  alternates: {
    canonical: '/',
  },
}

export default function HomePage() {
  return <HomeClient />
}
