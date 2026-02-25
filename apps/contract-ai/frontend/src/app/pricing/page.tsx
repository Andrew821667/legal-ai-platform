'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'

export default function PricingPage() {
  const router = useRouter()
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly')

  const plans = [
    {
      name: 'Demo',
      tier: 'demo',
      price: { monthly: 0, annual: 0 },
      description: 'Попробуйте возможности системы',
      gradient: 'from-gray-400 to-gray-600',
      popular: false,
      features: [
        { text: '3 договора в день', included: true },
        { text: '10 LLM запросов', included: true },
        { text: 'Базовый анализ', included: true },
        { text: 'Экспорт в PDF', included: false },
        { text: 'Генерация возражений', included: false },
        { text: 'Сравнение версий', included: false },
        { text: 'Приоритетная поддержка', included: false }
      ]
    },
    {
      name: 'Basic',
      tier: 'basic',
      price: { monthly: 1990, annual: 19900 },
      description: 'Для начинающих юристов',
      gradient: 'from-blue-500 to-cyan-600',
      popular: false,
      features: [
        { text: '50 договоров в день', included: true },
        { text: '100 LLM запросов', included: true },
        { text: 'Полный анализ', included: true },
        { text: 'Экспорт в PDF/DOCX', included: true },
        { text: 'Генерация возражений', included: true },
        { text: 'Сравнение версий', included: false },
        { text: 'Приоритетная поддержка', included: false }
      ]
    },
    {
      name: 'Pro',
      tier: 'pro',
      price: { monthly: 4990, annual: 49900 },
      description: 'Для профессиональных юристов',
      gradient: 'from-purple-500 to-pink-600',
      popular: true,
      features: [
        { text: '200 договоров в день', included: true },
        { text: '500 LLM запросов', included: true },
        { text: 'Глубокий анализ', included: true },
        { text: 'Экспорт в любых форматах', included: true },
        { text: 'Генерация возражений', included: true },
        { text: 'Сравнение версий', included: true },
        { text: 'Email поддержка', included: true }
      ]
    },
    {
      name: 'Enterprise',
      tier: 'enterprise',
      price: { monthly: 0, annual: 0 },
      description: 'Для компаний и юрфирм',
      gradient: 'from-orange-500 to-amber-600',
      popular: false,
      features: [
        { text: 'Неограниченно договоров', included: true },
        { text: 'Неограниченно запросов', included: true },
        { text: 'Все возможности Pro', included: true },
        { text: 'API доступ', included: true },
        { text: 'Кастомизация', included: true },
        { text: 'Выделенный менеджер', included: true },
        { text: '24/7 поддержка', included: true }
      ],
      isCustom: true
    }
  ]

  const getPrice = (plan: typeof plans[0]) => {
    if (plan.isCustom) return 'По запросу'
    if (plan.price.monthly === 0) return 'Бесплатно'
    const price = billingCycle === 'monthly' ? plan.price.monthly : plan.price.annual
    return `${price.toLocaleString('ru-RU')} ₽`
  }

  const getSavings = (plan: typeof plans[0]) => {
    if (billingCycle === 'annual' && !plan.isCustom && plan.price.monthly > 0) {
      const monthlyCost = plan.price.monthly * 12
      const annualCost = plan.price.annual
      const savings = monthlyCost - annualCost
      return `Экономия ${savings.toLocaleString('ru-RU')} ₽/год`
    }
    return null
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
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

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
            >
              <Button variant="outline" size="sm" onClick={() => router.push('/dashboard')}>
                ← Назад
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Title Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <h1 className="text-5xl md:text-6xl font-bold gradient-text mb-4">
            Тарифные планы
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-8">
            Выберите план, который соответствует вашим потребностям
          </p>

          {/* Billing Cycle Toggle */}
          <div className="inline-flex items-center bg-white rounded-2xl p-2 shadow-lg">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
                billingCycle === 'monthly'
                  ? 'bg-gradient-primary text-white shadow-lg'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Ежемесячно
            </button>
            <button
              onClick={() => setBillingCycle('annual')}
              className={`px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
                billingCycle === 'annual'
                  ? 'bg-gradient-primary text-white shadow-lg'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Ежегодно
              <Badge variant="success" size="sm" className="ml-2">-16%</Badge>
            </button>
          </div>
        </motion.div>

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-16">
          {plans.map((plan, idx) => (
            <motion.div
              key={plan.tier}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="relative"
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 transform -translate-x-1/2 z-10">
                  <Badge variant="warning" size="lg">
                    ⭐ Популярный
                  </Badge>
                </div>
              )}

              <Card
                className={`h-full relative overflow-hidden ${
                  plan.popular ? 'border-2 border-primary-300 shadow-2xl scale-105' : ''
                }`}
              >
                {/* Gradient Header */}
                <div className={`absolute top-0 left-0 right-0 h-2 bg-gradient-to-r ${plan.gradient}`} />

                <div className="pt-6">
                  {/* Plan Name */}
                  <h3 className="text-2xl font-bold text-gray-900 mb-2">{plan.name}</h3>
                  <p className="text-sm text-gray-600 mb-6">{plan.description}</p>

                  {/* Price */}
                  <div className="mb-6">
                    <div className="text-4xl font-bold gradient-text mb-1">
                      {getPrice(plan)}
                    </div>
                    {!plan.isCustom && plan.price.monthly > 0 && (
                      <div className="text-sm text-gray-500">
                        {billingCycle === 'monthly' ? 'в месяц' : 'в год'}
                      </div>
                    )}
                    {getSavings(plan) && (
                      <div className="text-sm text-success-600 font-semibold mt-1">
                        {getSavings(plan)}
                      </div>
                    )}
                  </div>

                  {/* Features */}
                  <ul className="space-y-3 mb-8">
                    {plan.features.map((feature, featureIdx) => (
                      <li key={featureIdx} className="flex items-start">
                        {feature.included ? (
                          <svg className="h-5 w-5 text-success-500 mr-2 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : (
                          <svg className="h-5 w-5 text-gray-300 mr-2 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        )}
                        <span className={feature.included ? 'text-gray-700' : 'text-gray-400'}>
                          {feature.text}
                        </span>
                      </li>
                    ))}
                  </ul>

                  {/* CTA Button */}
                  {plan.isCustom ? (
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={() => router.push('/contacts')}
                    >
                      Связаться с нами
                    </Button>
                  ) : plan.price.monthly === 0 ? (
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={() => router.push('/register')}
                    >
                      Попробовать
                    </Button>
                  ) : (
                    <Button
                      variant={plan.popular ? 'primary' : 'outline'}
                      className="w-full"
                      onClick={() => router.push('/register')}
                    >
                      Выбрать {plan.name}
                    </Button>
                  )}
                </div>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* FAQ Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="max-w-4xl mx-auto"
        >
          <h2 className="text-3xl font-bold gradient-text text-center mb-12">
            Часто задаваемые вопросы
          </h2>

          <div className="space-y-6">
            {[
              {
                q: 'Можно ли изменить тарифный план?',
                a: 'Да, вы можете повысить или понизить тарифный план в любое время из панели управления.'
              },
              {
                q: 'Как происходит оплата?',
                a: 'Мы принимаем банковские карты и электронные кошельки. Оплата происходит автоматически каждый месяц или год.'
              },
              {
                q: 'Есть ли бесплатный пробный период?',
                a: 'Да, Demo план доступен бесплатно с ограничением в 3 договора в день.'
              },
              {
                q: 'Что делать, если я превышу лимиты?',
                a: 'Вы можете перейти на более высокий тариф или дождаться следующего дня для восстановления лимитов.'
              }
            ].map((faq, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
              >
                <Card hover>
                  <h3 className="font-bold text-lg text-gray-900 mb-2">{faq.q}</h3>
                  <p className="text-gray-600">{faq.a}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* CTA Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-16 text-center"
        >
          <Card className="bg-gradient-to-br from-primary-50 to-secondary-50 border-2 border-primary-200">
            <div className="py-8">
              <h2 className="text-3xl font-bold gradient-text mb-4">
                Остались вопросы?
              </h2>
              <p className="text-gray-600 mb-6 max-w-2xl mx-auto">
                Свяжитесь с нами, и мы поможем выбрать оптимальный тарифный план для ваших задач
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button variant="primary" onClick={() => router.push('/contacts')}>
                  Связаться с нами
                </Button>
                <Button variant="outline" onClick={() => router.push('/register')}>
                  Начать бесплатно
                </Button>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
