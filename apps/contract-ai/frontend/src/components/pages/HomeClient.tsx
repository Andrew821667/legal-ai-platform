'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'

const freeLimits = [
  { value: '0 ₽', label: 'стоимость демо-доступа' },
  { value: '3', label: 'договора бесплатно в месяц' },
  { value: '5 МБ', label: 'размер одного файла' },
]

export default function Home() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      router.push('/dashboard')
    } else {
      setIsLoading(false)
    }
  }, [router])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
          className="w-16 h-16 border-4 border-primary-500 border-t-transparent rounded-full"
        />
      </div>
    )
  }

  const features = [
    {
      icon: '🔍',
      title: 'Умный анализ',
      description: 'AI-анализ договоров с выявлением рисков и юридических проблем'
    },
    {
      icon: '⚡',
      title: 'Молниеносно',
      description: 'Анализ 50+ пунктов за 30 секунд. В 100x быстрее юриста'
    },
    {
      icon: '📊',
      title: 'Детальные отчеты',
      description: 'Подробные рекомендации с ссылками на ГК РФ'
    },
    {
      icon: '✨',
      title: 'Генерация',
      description: 'Создание договоров по шаблонам с AI-заполнением'
    },
    {
      icon: '🔄',
      title: 'Сравнение версий',
      description: 'Отслеживание изменений между редакциями договора'
    },
    {
      icon: '📤',
      title: 'Экспорт',
      description: 'Выгрузка в DOCX, PDF, JSON с форматированием'
    }
  ]

  const stats = [
    { value: '3/мес', label: 'Договора бесплатно' },
    { value: '0 ₽', label: 'Стоимость первого шага' },
    { value: '30 сек', label: 'Ориентир быстрой проверки' },
    { value: '24/7', label: 'Доступность системы' }
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Навигация */}
      <nav className="bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3"
            >
              <div className="w-10 h-10 bg-gradient-primary rounded-xl shadow-lg flex items-center justify-center">
                <span className="text-2xl">📄</span>
              </div>
              <span className="text-xl font-bold gradient-text">Contract AI</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-4"
            >
              <Button variant="outline" size="sm" onClick={() => router.push('/login')}>
                Вход
              </Button>
              <Button variant="primary" size="sm" onClick={() => router.push('/register')}>
                Открыть демо
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative overflow-hidden py-20 px-4">
        {/* Background decoration */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <motion.div
            className="absolute top-20 right-20 w-96 h-96 bg-primary-200/30 rounded-full blur-3xl"
            animate={{ scale: [1, 1.2, 1], rotate: [0, 90, 0] }}
            transition={{ duration: 20, repeat: Infinity }}
          />
          <motion.div
            className="absolute bottom-20 left-20 w-96 h-96 bg-secondary-200/30 rounded-full blur-3xl"
            animate={{ scale: [1.2, 1, 1.2], rotate: [90, 0, 90] }}
            transition={{ duration: 25, repeat: Infinity }}
          />
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <div className="text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <h1 className="text-6xl md:text-7xl font-bold mb-6">
                <span className="gradient-text">Умная работа</span>
                <br />
                с договорами
              </h1>
              <p className="text-xl md:text-2xl text-gray-600 mb-8 max-w-3xl mx-auto">
                Contract AI System помогает быстро проверить договорный сценарий на реальных документах,
                начать с 3 бесплатных договоров в месяц, а затем перейти к пилоту и рабочему контуру
                без лишней архитектурной сложности.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="flex flex-col sm:flex-row gap-4 justify-center"
            >
              <Button
                variant="primary"
                size="lg"
                onClick={() => router.push('/register')}
                icon={
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                }
              >
                Открыть демо-контур
              </Button>
              <Button
                variant="outline"
                size="lg"
                onClick={() => router.push('/pricing')}
              >
                Форматы запуска
              </Button>
            </motion.div>

            {/* Demo Image/Animation */}
            <motion.div
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.4 }}
              className="mt-16"
            >
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-primary opacity-20 blur-3xl rounded-3xl" />
                <div className="relative bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-white/20">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <Card hover className="text-center">
                      <div className="text-5xl mb-3">📄</div>
                      <h3 className="font-bold text-lg mb-2">Загрузите</h3>
                      <p className="text-sm text-gray-600">Договор в PDF или DOCX</p>
                    </Card>
                    <Card hover className="text-center">
                      <div className="text-5xl mb-3">🤖</div>
                      <h3 className="font-bold text-lg mb-2">Анализ AI</h3>
                      <p className="text-sm text-gray-600">Автоматический анализ рисков</p>
                    </Card>
                    <Card hover className="text-center">
                      <div className="text-5xl mb-3">📊</div>
                      <h3 className="font-bold text-lg mb-2">Получите отчет</h3>
                      <p className="text-sm text-gray-600">С рекомендациями и рисками</p>
                    </Card>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-16 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {stats.map((stat, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
              >
                <Card className="text-center">
                  <div className="text-3xl md:text-4xl font-bold gradient-text mb-2">
                    {stat.value}
                  </div>
                  <div className="text-sm text-gray-600">{stat.label}</div>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-8 px-4">
        <div className="max-w-7xl mx-auto">
          <Card className="bg-white/90 border-2 border-primary-100">
            <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-8 items-center">
              <div>
                <p className="text-sm font-semibold uppercase tracking-wide text-primary-600 mb-3">
                  Бесплатный вход
                </p>
                <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
                  3 договора бесплатно каждый месяц
                </h2>
                <p className="text-lg text-gray-600">
                  Бесплатный режим нужен для спокойной проверки сценария: загрузить документ,
                  посмотреть структуру отчета и понять, подходит ли система под ваш процесс.
                  Оплата появляется только на следующем этапе — пилоте или рабочем контуре.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-4">
                {freeLimits.map((limit) => (
                  <div key={limit.label} className="rounded-2xl border border-gray-100 bg-slate-50 p-5">
                    <div className="text-3xl font-bold gradient-text">{limit.value}</div>
                    <div className="text-sm text-gray-600 mt-1">{limit.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-4">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl md:text-5xl font-bold gradient-text mb-4">
              Возможности системы
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto">
              Все инструменты для профессиональной работы с договорами в одной системе
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
              >
                <Card hover className="h-full">
                  <div className="text-5xl mb-4">{feature.icon}</div>
                  <h3 className="text-xl font-bold mb-2">{feature.title}</h3>
                  <p className="text-gray-600">{feature.description}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
          >
            <Card className="text-center bg-gradient-to-br from-primary-50 to-secondary-50 border-2 border-primary-200">
              <div className="py-8">
                <h2 className="text-3xl md:text-4xl font-bold gradient-text mb-4">
                  Готовы попробовать?
                </h2>
                <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
                  Начните с 3 бесплатных договоров в месяц. Если нужен следующий этап, обсудим пилот
                  на ваших документах и только потом зафиксируем рабочий формат.
                </p>
                <Button
                  variant="primary"
                  size="lg"
                  onClick={() => router.push('/register')}
                  icon={
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                  }
                >
                  Открыть демо-контур
                </Button>
                <div className="mt-4">
                  <Button
                    variant="outline"
                    size="lg"
                    onClick={() => router.push('/pricing')}
                  >
                    Посмотреть форматы запуска
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white/80 backdrop-blur-lg border-t border-gray-200 py-12 px-4">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
                  <span className="text-xl">📄</span>
                </div>
                <span className="font-bold gradient-text">Contract AI</span>
              </div>
              <p className="text-sm text-gray-600">
                Умная работа с договорами на основе искусственного интеллекта
              </p>
            </div>

            <div>
              <h4 className="font-bold mb-4">Продукт</h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li><a href="#features" className="hover:text-primary-600">Возможности</a></li>
                <li><a href="/pricing" className="hover:text-primary-600">Форматы запуска</a></li>
                <li><a href="/register" className="hover:text-primary-600">Демо</a></li>
              </ul>
            </div>

            <div>
              <h4 className="font-bold mb-4">Компания</h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li><a href="https://ai-verdict.ru/about" className="hover:text-primary-600">О нас</a></li>
                <li><a href="https://ai-verdict.ru/content-cases" className="hover:text-primary-600">Контент / Кейсы</a></li>
                <li><a href="https://ai-verdict.ru/about#contacts" className="hover:text-primary-600">Контакты</a></li>
              </ul>
            </div>

            <div>
              <h4 className="font-bold mb-4">Поддержка</h4>
              <ul className="space-y-2 text-sm text-gray-600">
                <li><a href="/dashboard" className="hover:text-primary-600">Кабинет</a></li>
                <li><a href="/pricing" className="hover:text-primary-600">Форматы запуска</a></li>
                <li><a href="/privacy" className="hover:text-primary-600">Конфиденциальность</a></li>
                <li><a href="/terms" className="hover:text-primary-600">Условия использования</a></li>
              </ul>
            </div>
          </div>

          <div className="pt-8 border-t border-gray-200 text-center text-sm text-gray-600">
            <p>© 2024 Contract AI System. Все права защищены.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
