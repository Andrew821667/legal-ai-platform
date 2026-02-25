'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'

interface ChangePasswordModalProps {
  isOpen: boolean
  onClose: () => void
  userEmail: string
}

interface PasswordFormData {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

export default function ChangePasswordModal({ isOpen, onClose, userEmail }: ChangePasswordModalProps) {
  const [isLoading, setIsLoading] = useState(false)
  const { register, handleSubmit, watch, formState: { errors }, reset } = useForm<PasswordFormData>()

  const newPassword = watch('newPassword')

  const onSubmit = async (data: PasswordFormData) => {
    setIsLoading(true)

    try {
      // TODO: Replace with actual API call
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Mark password as changed
      localStorage.setItem('passwordChanged', 'true')

      toast.success('Пароль успешно изменён!', {
        icon: '✅',
        style: {
          borderRadius: '12px',
          background: 'linear-gradient(135deg, #10b981, #059669)',
          color: '#fff',
        },
      })

      reset()
      onClose()
    } catch (error) {
      toast.error('Ошибка при смене пароля', {
        icon: '❌',
        style: { borderRadius: '12px' },
      })
    } finally {
      setIsLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0, y: 20 }}
        transition={{ type: 'spring', damping: 25 }}
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-8"
      >
        {/* Header */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-amber-500 to-orange-600 mb-4">
            <span className="text-3xl">🔐</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-800 mb-2">
            Смена пароля
          </h2>
          <p className="text-slate-600">
            Для безопасности, пожалуйста, смените пароль по умолчанию
          </p>
        </div>

        {/* Warning */}
        <div className="mb-6 p-4 bg-amber-50 border-l-4 border-amber-500 rounded-r-lg">
          <div className="flex items-start gap-3">
            <span className="text-amber-600 text-xl">⚠️</span>
            <div>
              <p className="font-semibold text-amber-900 mb-1">
                Вы используете пароль по умолчанию
              </p>
              <p className="text-sm text-amber-700">
                Смените его сейчас для защиты вашего аккаунта
              </p>
            </div>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* Current Password */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Текущий пароль
            </label>
            <input
              type="password"
              {...register('currentPassword', {
                required: 'Введите текущий пароль',
              })}
              className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Введите текущий пароль"
            />
            {errors.currentPassword && (
              <p className="mt-1 text-sm text-red-600">{errors.currentPassword.message}</p>
            )}
          </div>

          {/* New Password */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Новый пароль
            </label>
            <input
              type="password"
              {...register('newPassword', {
                required: 'Введите новый пароль',
                minLength: {
                  value: 8,
                  message: 'Минимум 8 символов',
                },
                pattern: {
                  value: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/,
                  message: 'Должен содержать буквы разного регистра и цифры',
                },
              })}
              className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Минимум 8 символов"
            />
            {errors.newPassword && (
              <p className="mt-1 text-sm text-red-600">{errors.newPassword.message}</p>
            )}
            {/* Password strength indicator */}
            {newPassword && newPassword.length > 0 && (
              <div className="mt-2">
                <div className="flex gap-1">
                  <div className={`h-1 flex-1 rounded ${newPassword.length >= 8 ? 'bg-green-500' : 'bg-slate-200'}`} />
                  <div className={`h-1 flex-1 rounded ${/[A-Z]/.test(newPassword) ? 'bg-green-500' : 'bg-slate-200'}`} />
                  <div className={`h-1 flex-1 rounded ${/[a-z]/.test(newPassword) ? 'bg-green-500' : 'bg-slate-200'}`} />
                  <div className={`h-1 flex-1 rounded ${/\d/.test(newPassword) ? 'bg-green-500' : 'bg-slate-200'}`} />
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Сложность пароля
                </p>
              </div>
            )}
          </div>

          {/* Confirm Password */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Повторите новый пароль
            </label>
            <input
              type="password"
              {...register('confirmPassword', {
                required: 'Повторите пароль',
                validate: (value) =>
                  value === newPassword || 'Пароли не совпадают',
              })}
              className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Повторите новый пароль"
            />
            {errors.confirmPassword && (
              <p className="mt-1 text-sm text-red-600">{errors.confirmPassword.message}</p>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-3 border border-slate-300 text-slate-700 font-semibold rounded-lg hover:bg-slate-50 transition-all"
            >
              Позже
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 px-4 py-3 bg-gradient-to-r from-primary-500 to-secondary-500 text-white font-semibold rounded-lg hover:shadow-lg transition-all disabled:opacity-50"
            >
              {isLoading ? 'Сохранение...' : 'Сменить пароль'}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  )
}
