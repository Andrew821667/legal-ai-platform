'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { useForm } from 'react-hook-form'
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  DocumentMagnifyingGlassIcon,
  EnvelopeIcon,
  LockClosedIcon,
  UserIcon,
} from '@heroicons/react/24/outline'
import api from '@/services/api'
import LegalConsentPanel from '@/components/LegalConsentPanel'
import toast from 'react-hot-toast'

interface RegisterFormData {
  name: string
  email: string
  password: string
  confirmPassword: string
}

export default function RegisterPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [legalAccepted, setLegalAccepted] = useState(false)
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormData>()

  const password = watch('password')

  const onSubmit = async (data: RegisterFormData) => {
    if (!legalAccepted) {
      toast.error('Примите документы сервиса для регистрации')
      return
    }

    setIsLoading(true)
    try {
      await api.register({
        name: data.name,
        email: data.email,
        password: data.password,
        legal_consent_accepted: true,
      })
      localStorage.setItem('contract_ai_legal_consent_v1', 'accepted')
      toast.success('Аккаунт создан. Теперь войдите в систему.')
      router.push('/login?registered=true')
    } catch (error: any) {
      console.error('Registration error:', error)
      toast.error(error.response?.data?.detail || 'Не удалось создать аккаунт')
    } finally {
      setIsLoading(false)
    }
  }

  const inputClass =
    'w-full rounded-lg border border-slate-300 bg-white py-3 pl-11 pr-4 text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-950 focus:ring-2 focus:ring-slate-950/10'

  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <button type="button" onClick={() => router.push('/')} className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-950 text-amber-300">
              <DocumentMagnifyingGlassIcon className="h-5 w-5" aria-hidden="true" />
            </span>
            <span className="text-left">
              <span className="block text-base font-bold">Contract AI</span>
              <span className="block text-xs text-slate-500">AI Verdict</span>
            </span>
          </button>
          <button
            type="button"
            onClick={() => router.push('/login')}
            className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-950"
          >
            <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
            Войти
          </button>
        </div>
      </header>

      <section className="mx-auto grid max-w-5xl gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[0.7fr_1.3fr] lg:py-16">
        <div className="pt-2">
          <p className="text-xs font-semibold uppercase text-amber-700">Новый аккаунт</p>
          <h1 className="mt-3 text-3xl font-bold leading-tight text-slate-950">
            Подготовьте рабочее пространство
          </h1>
          <p className="mt-4 text-sm leading-7 text-slate-600">
            После регистрации вы сможете загрузить договор и получить структурированный список рисков и рекомендаций.
          </p>
          <div className="mt-8 border-t border-slate-300 pt-6">
            <p className="text-sm font-bold text-slate-950">Что фиксируется при регистрации</p>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-600">
              <li>• версия пользовательского соглашения;</li>
              <li>• дата принятия политики ПД;</li>
              <li>• технические данные для журнала безопасности.</li>
            </ul>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
        >
          <div className="border-b border-slate-200 pb-5">
            <p className="text-xs font-semibold uppercase text-slate-500">Шаг 1 из 1</p>
            <h2 className="mt-1 text-2xl font-bold">Данные аккаунта</h2>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-5">
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">Имя</span>
              <span className="relative block">
                <UserIcon className="pointer-events-none absolute left-3.5 top-3.5 h-5 w-5 text-slate-400" aria-hidden="true" />
                <input
                  {...register('name', {
                    required: 'Введите ваше имя',
                    minLength: { value: 2, message: 'Минимум 2 символа' },
                  })}
                  type="text"
                  placeholder="Иван Иванов"
                  className={inputClass}
                  autoComplete="name"
                />
              </span>
              {errors.name && <p className="mt-1 text-sm text-red-700">{errors.name.message}</p>}
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-slate-700">Email</span>
              <span className="relative block">
                <EnvelopeIcon className="pointer-events-none absolute left-3.5 top-3.5 h-5 w-5 text-slate-400" aria-hidden="true" />
                <input
                  {...register('email', {
                    required: 'Введите email',
                    pattern: {
                      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                      message: 'Некорректный email',
                    },
                  })}
                  type="email"
                  placeholder="name@company.ru"
                  className={inputClass}
                  autoComplete="email"
                />
              </span>
              {errors.email && <p className="mt-1 text-sm text-red-700">{errors.email.message}</p>}
            </label>

            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">Пароль</span>
                <span className="relative block">
                  <LockClosedIcon className="pointer-events-none absolute left-3.5 top-3.5 h-5 w-5 text-slate-400" aria-hidden="true" />
                  <input
                    {...register('password', {
                      required: 'Введите пароль',
                      minLength: { value: 8, message: 'Минимум 8 символов' },
                    })}
                    type="password"
                    placeholder="Минимум 8 символов"
                    className={inputClass}
                    autoComplete="new-password"
                  />
                </span>
                {errors.password && <p className="mt-1 text-sm text-red-700">{errors.password.message}</p>}
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-slate-700">Повторите пароль</span>
                <span className="relative block">
                  <LockClosedIcon className="pointer-events-none absolute left-3.5 top-3.5 h-5 w-5 text-slate-400" aria-hidden="true" />
                  <input
                    {...register('confirmPassword', {
                      required: 'Подтвердите пароль',
                      validate: (value) => value === password || 'Пароли не совпадают',
                    })}
                    type="password"
                    placeholder="Повторите пароль"
                    className={inputClass}
                    autoComplete="new-password"
                  />
                </span>
                {errors.confirmPassword && (
                  <p className="mt-1 text-sm text-red-700">{errors.confirmPassword.message}</p>
                )}
              </label>
            </div>

            <LegalConsentPanel
              accepted={legalAccepted}
              onChange={setLegalAccepted}
              disabled={isLoading}
            />

            <button
              type="submit"
              disabled={isLoading || !legalAccepted}
              className="flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-slate-950 px-5 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500"
            >
              {isLoading ? 'Создаём аккаунт...' : 'Создать аккаунт'}
              {!isLoading && <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />}
            </button>
          </form>
        </motion.div>
      </section>
    </main>
  )
}
