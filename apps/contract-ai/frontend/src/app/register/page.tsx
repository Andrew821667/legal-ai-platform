'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'
import Button from '@/components/ui/Button'

interface RegisterFormData {
  name: string
  email: string
  password: string
  confirmPassword: string
}

export default function RegisterPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const { register, handleSubmit, watch, formState: { errors } } = useForm<RegisterFormData>()

  const password = watch('password')

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true)

    try {
      // TODO: Replace with actual API call
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Mock registration - redirect to login
      router.push('/login?registered=true')
    } catch (error) {
      console.error('Registration error:', error)
      toast.error('Ошибка регистрации. Попробуйте снова.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute top-20 right-20 w-96 h-96 bg-primary-200/30 rounded-full blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            x: [0, 30, 0],
            y: [0, -30, 0]
          }}
          transition={{ duration: 8, repeat: Infinity }}
        />
        <motion.div
          className="absolute bottom-20 left-20 w-96 h-96 bg-secondary-200/30 rounded-full blur-3xl"
          animate={{
            scale: [1.2, 1, 1.2],
            x: [0, -30, 0],
            y: [0, 30, 0]
          }}
          transition={{ duration: 10, repeat: Infinity }}
        />
      </div>

      {/* Register Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="glass backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-white/20">
          {/* Logo */}
          <div className="text-center mb-8">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", duration: 0.6 }}
              className="w-16 h-16 bg-gradient-primary rounded-2xl shadow-lg mx-auto mb-4 flex items-center justify-center"
            >
              <span className="text-3xl">📄</span>
            </motion.div>
            <h1 className="text-3xl font-bold gradient-text mb-2">
              Регистрация
            </h1>
            <p className="text-gray-600">
              Создайте аккаунт и начните работать с договорами
            </p>
          </div>

          {/* Registration Form */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Имя
              </label>
              <div className="relative">
                <input
                  {...register('name', {
                    required: 'Введите ваше имя',
                    minLength: { value: 2, message: 'Минимум 2 символа' }
                  })}
                  type="text"
                  placeholder="Иван Иванов"
                  className="w-full pl-12 pr-4 py-3.5 bg-white/10 border-2 border-white/20 rounded-xl focus:border-primary-400 focus:bg-white/20 transition-all outline-none text-gray-800 placeholder-gray-500"
                />
                <svg className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              {errors.name && (
                <p className="text-danger-600 text-sm mt-1">{errors.name.message}</p>
              )}
            </div>

            {/* Email */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Email
              </label>
              <div className="relative">
                <input
                  {...register('email', {
                    required: 'Введите email',
                    pattern: {
                      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                      message: 'Некорректный email'
                    }
                  })}
                  type="email"
                  placeholder="email@example.com"
                  className="w-full pl-12 pr-4 py-3.5 bg-white/10 border-2 border-white/20 rounded-xl focus:border-primary-400 focus:bg-white/20 transition-all outline-none text-gray-800 placeholder-gray-500"
                />
                <svg className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              {errors.email && (
                <p className="text-danger-600 text-sm mt-1">{errors.email.message}</p>
              )}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Пароль
              </label>
              <div className="relative">
                <input
                  {...register('password', {
                    required: 'Введите пароль',
                    minLength: { value: 8, message: 'Минимум 8 символов' }
                  })}
                  type="password"
                  placeholder="••••••••"
                  className="w-full pl-12 pr-4 py-3.5 bg-white/10 border-2 border-white/20 rounded-xl focus:border-primary-400 focus:bg-white/20 transition-all outline-none text-gray-800 placeholder-gray-500"
                />
                <svg className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              {errors.password && (
                <p className="text-danger-600 text-sm mt-1">{errors.password.message}</p>
              )}
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Подтверждение пароля
              </label>
              <div className="relative">
                <input
                  {...register('confirmPassword', {
                    required: 'Подтвердите пароль',
                    validate: value => value === password || 'Пароли не совпадают'
                  })}
                  type="password"
                  placeholder="••••••••"
                  className="w-full pl-12 pr-4 py-3.5 bg-white/10 border-2 border-white/20 rounded-xl focus:border-primary-400 focus:bg-white/20 transition-all outline-none text-gray-800 placeholder-gray-500"
                />
                <svg className="absolute left-4 top-3.5 h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              {errors.confirmPassword && (
                <p className="text-danger-600 text-sm mt-1">{errors.confirmPassword.message}</p>
              )}
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              loading={isLoading}
              disabled={isLoading}
            >
              Зарегистрироваться
            </Button>
          </form>

          {/* Login Link */}
          <div className="mt-6 text-center">
            <p className="text-gray-600">
              Уже есть аккаунт?{' '}
              <button
                onClick={() => router.push('/login')}
                className="text-primary-600 hover:text-primary-700 font-semibold"
              >
                Войти
              </button>
            </p>
          </div>

          {/* Back to Home */}
          <div className="mt-4 text-center">
            <button
              onClick={() => router.push('/')}
              className="text-gray-500 hover:text-gray-700 text-sm"
            >
              ← На главную
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
