'use client'

import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'

const launchFormats = [
  {
    title: 'Демо-контур',
    badge: 'Без оплаты на первом шаге',
    description: 'Быстрый вход, чтобы проверить интерфейс, ограничения и общий сценарий работы с договором.',
    points: [
      'Ограниченный доступ для знакомства с продуктом',
      'Проверка базового сценария загрузки и анализа',
      'Подходит для первичной валидации гипотезы',
    ],
  },
  {
    title: 'Пилот на реальных документах',
    badge: 'Основной следующий этап',
    description: 'Разбираем ваши документы, процесс согласования и критерии качества до рабочего запуска.',
    points: [
      'Фиксируем scope, ограничения и KPI',
      'Проверяем эффект на конкретном процессе',
      'После пилота решаем, что масштабировать дальше',
    ],
  },
  {
    title: 'Рабочий контур',
    badge: 'После пилота',
    description: 'Полноценный сценарий для команды: доступы, маршруты, экспорт, контроль качества и развитие контура.',
    points: [
      'Настройка под вашу роль и процесс',
      'Интеграции и расширение функций по необходимости',
      'Не запускается как self-serve подписка по умолчанию',
    ],
  },
]

const pricingPrinciples = [
  'Обычный первый шаг — демо или диагностика, а не покупка тарифа вслепую.',
  'Стоимость обсуждаем после понимания объема документов, ролей и требований к качеству.',
  'Если нужен особый формат, его оформляем как отдельный проектный или консультационный контур.',
]

export default function PricingPage() {
  const router = useRouter()

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <nav className="bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3 cursor-pointer"
              onClick={() => router.push('/')}
            >
              <div className="w-10 h-10 bg-gradient-primary rounded-xl shadow-lg flex items-center justify-center">
                <span className="text-2xl">📄</span>
              </div>
              <span className="text-xl font-bold gradient-text">Contract AI</span>
            </motion.div>

            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
              <Button variant="outline" size="sm" onClick={() => router.push('/dashboard')}>
                ← Назад
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <Badge variant="warning" size="lg">Pilot-first model</Badge>
          <h1 className="text-5xl md:text-6xl font-bold gradient-text mt-6 mb-4">
            Форматы запуска
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Contract AI System сейчас позиционируется не как self-serve SaaS с тарифами для всех,
            а как вход в демо, пилот и последующий рабочий контур.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
          {launchFormats.map((format, idx) => (
            <motion.div
              key={format.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
            >
              <Card className="h-full">
                <div className="mb-5">
                  <Badge variant={idx === 1 ? 'warning' : 'default'} size="sm">{format.badge}</Badge>
                </div>
                <h2 className="text-2xl font-bold text-gray-900 mb-3">{format.title}</h2>
                <p className="text-gray-600 mb-6">{format.description}</p>
                <ul className="space-y-3">
                  {format.points.map((point) => (
                    <li key={point} className="flex items-start gap-2 text-gray-700">
                      <span className="text-amber-500 mt-0.5">✓</span>
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-12"
        >
          <Card className="bg-gradient-to-br from-slate-900 to-slate-800 text-white border-0">
            <h2 className="text-3xl font-bold mb-5">Как сейчас обсуждаем оплату</h2>
            <div className="space-y-3 text-slate-200">
              {pricingPrinciples.map((item) => (
                <div key={item} className="flex items-start gap-3">
                  <span className="text-amber-400 mt-0.5">•</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card className="text-center bg-gradient-to-br from-primary-50 to-secondary-50 border-2 border-primary-200">
            <div className="py-6">
              <h2 className="text-3xl font-bold gradient-text mb-4">Следующий шаг</h2>
              <p className="text-lg text-gray-600 max-w-3xl mx-auto mb-8">
                Если вы впервые в системе, начните с демо-контура. Если уже проверили базовый сценарий,
                следующий разговор должен быть не про “тариф”, а про пилот и рабочий формат запуска.
              </p>
              <div className="flex flex-col sm:flex-row justify-center gap-4">
                <Button variant="primary" size="lg" onClick={() => router.push('/register')}>
                  Открыть демо-контур
                </Button>
                <Button variant="outline" size="lg" onClick={() => router.push('/login')}>
                  Войти в кабинет
                </Button>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
