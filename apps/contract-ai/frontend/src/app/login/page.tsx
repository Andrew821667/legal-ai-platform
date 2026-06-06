'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import {
  ArrowRightIcon,
  DocumentMagnifyingGlassIcon,
  EnvelopeIcon,
  LockClosedIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'
import api from '@/services/api'
import LegalConsentPanel from '@/components/LegalConsentPanel'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [legalAccepted, setLegalAccepted] = useState(false)

  useEffect(() => {
    setLegalAccepted(localStorage.getItem('contract_ai_legal_consent_v1') === 'accepted')
  }, [])

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!legalAccepted) {
      toast.error('Примите документы сервиса перед входом')
      return
    }

    setIsLoading(true)
    try {
      const response = await api.login({ username: email, password })
      await api.acceptLegalConsent()
      toast.success(`Добро пожаловать, ${response.user.name}`)
      router.push('/dashboard')
    } catch (error: any) {
      console.error('Login error:', error)
      toast.error(error.response?.data?.detail || error.message || 'Неверный email или пароль')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto grid min-h-screen max-w-6xl lg:grid-cols-[0.86fr_1.14fr]">
        <section className="flex flex-col justify-between border-b border-slate-800 px-6 py-8 sm:px-10 lg:border-b-0 lg:border-r lg:py-12">
          <button
            type="button"
            onClick={() => router.push('/')}
            className="flex w-fit items-center gap-3 text-left"
          >
            <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-amber-400 text-slate-950">
              <DocumentMagnifyingGlassIcon className="h-6 w-6" aria-hidden="true" />
            </span>
            <span>
              <span className="block text-lg font-bold text-white">Contract AI</span>
              <span className="block text-xs text-slate-400">AI Verdict</span>
            </span>
          </button>

          <div className="my-12 max-w-md lg:my-0">
            <p className="text-xs font-semibold uppercase text-amber-300">Рабочий контур</p>
            <h1 className="mt-3 text-4xl font-bold leading-tight text-white">
              Проверка договоров без визуального шума
            </h1>
            <p className="mt-5 text-base leading-7 text-slate-300">
              Загружайте документы, фиксируйте риски и собирайте рекомендации в одном защищённом пространстве.
            </p>
            <div className="mt-8 space-y-4 border-t border-slate-800 pt-7">
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <ShieldCheckIcon className="h-5 w-5 text-emerald-400" aria-hidden="true" />
                Согласия и действия фиксируются в системе
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-300">
                <LockClosedIcon className="h-5 w-5 text-sky-400" aria-hidden="true" />
                Документы доступны только авторизованному пользователю
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-500">AI Verdict · Contract AI</p>
        </section>

        <section className="flex items-center justify-center px-4 py-10 sm:px-8 lg:px-12">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-md"
          >
            <p className="text-sm font-semibold text-amber-300">Вход в рабочее пространство</p>
            <h2 className="mt-2 text-3xl font-bold text-white">Продолжить работу</h2>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              Используйте корпоративный или личный аккаунт Contract AI.
            </p>

            <form onSubmit={handleLogin} className="mt-8 space-y-5">
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-200">Email</span>
                <span className="relative block">
                  <EnvelopeIcon className="pointer-events-none absolute left-3.5 top-3.5 h-5 w-5 text-slate-500" aria-hidden="true" />
                  <input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-900 py-3 pl-11 pr-4 text-white outline-none transition placeholder:text-slate-600 focus:border-amber-300 focus:ring-2 focus:ring-amber-300/10"
                    placeholder="name@company.ru"
                    autoComplete="email"
                    required
                  />
                </span>
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-200">Пароль</span>
                <span className="relative block">
                  <LockClosedIcon className="pointer-events-none absolute left-3.5 top-3.5 h-5 w-5 text-slate-500" aria-hidden="true" />
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-slate-900 py-3 pl-11 pr-4 text-white outline-none transition placeholder:text-slate-600 focus:border-amber-300 focus:ring-2 focus:ring-amber-300/10"
                    placeholder="Введите пароль"
                    autoComplete="current-password"
                    required
                  />
                </span>
              </label>

              <LegalConsentPanel
                accepted={legalAccepted}
                onChange={setLegalAccepted}
                disabled={isLoading}
                tone="dark"
              />

              <button
                type="submit"
                disabled={isLoading || !legalAccepted}
                className="flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-amber-400 px-5 py-3 text-sm font-bold text-slate-950 transition hover:bg-amber-300 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
              >
                {isLoading ? 'Проверяем данные...' : 'Войти'}
                {!isLoading && <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />}
              </button>
            </form>

            <div className="mt-7 border-t border-slate-800 pt-6 text-center">
              <span className="text-sm text-slate-400">Нет аккаунта? </span>
              <button
                type="button"
                onClick={() => router.push('/register')}
                className="text-sm font-bold text-white underline decoration-slate-600 underline-offset-4 hover:decoration-amber-300"
              >
                Зарегистрироваться
              </button>
            </div>
          </motion.div>
        </section>
      </div>
    </main>
  )
}
