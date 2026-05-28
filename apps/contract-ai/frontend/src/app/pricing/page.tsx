import type { Metadata } from 'next'

import PricingClient from '@/components/pages/PricingClient'

export const metadata: Metadata = {
  title: 'Форматы запуска',
  description:
    'Форматы запуска Contract AI System: демо-контур, 3 бесплатных договора в месяц, пилот и рабочий контур.',
  alternates: {
    canonical: '/pricing',
  },
}

export default function PricingPage() {
  return <PricingClient />
}
