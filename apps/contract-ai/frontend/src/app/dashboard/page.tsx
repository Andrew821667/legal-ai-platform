'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import api from '@/services/api'
import toast from 'react-hot-toast'
import { getUserRole, getRolePermissions, getRoleColor, getRoleLabel } from '@/utils/roles'
import ChangePasswordModal from '@/components/ChangePasswordModal'

interface User {
  id: string
  name: string
  email: string
  role: string
  subscription_tier: string
  contracts_today: number
  llm_requests_today: number
  max_contracts_per_day: number
  max_llm_requests_per_day: number
}

interface Contract {
  id: string
  file_name: string
  status: string
  contract_type: string
  created_at: string
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 }
}

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [showWelcome, setShowWelcome] = useState(false)
  const [showPasswordChange, setShowPasswordChange] = useState(false)
  const userRole = getUserRole()
  const permissions = getRolePermissions(userRole)
  const roleColor = getRoleColor(userRole)
  const roleLabel = getRoleLabel(userRole)

  // Check authentication and default password
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    console.log('🔍 Dashboard checking token:', token)
    if (!token) {
      console.log('❌ No token found, redirecting to login')
      router.push('/login')
    } else {
      console.log('✅ Token found, user authenticated')
      // Check if using default password
      const passwordChanged = localStorage.getItem('passwordChanged')
      const userStr = localStorage.getItem('user')

      if (!passwordChanged && userStr) {
        try {
          const userData = JSON.parse(userStr)
          // Check if using demo credentials (default passwords)
          const defaultEmails = ['demo@example.com', 'admin@example.com', 'lawyer@example.com', 'junior@example.com']
          if (defaultEmails.includes(userData.email)) {
            // Show password change dialog after welcome
            setTimeout(() => {
              setShowPasswordChange(true)
            }, 2000)
          }
        } catch (e) {
          console.error('Error parsing user data:', e)
        }
      }

      // Show welcome message on first visit
      const hasSeenWelcome = sessionStorage.getItem('hasSeenWelcome')
      if (!hasSeenWelcome) {
        setShowWelcome(true)
        sessionStorage.setItem('hasSeenWelcome', 'true')
      }
    }
  }, [router])

  // Fetch current user
  const { data: userData, isLoading: userLoading } = useQuery({
    queryKey: ['currentUser'],
    queryFn: async () => {
      const response = await api.getCurrentUser()
      setUser(response.data)
      return response.data
    }
  })

  // Fetch recent contracts
  const { data: contractsData, isLoading: contractsLoading } = useQuery({
    queryKey: ['contracts', 'recent'],
    queryFn: async () => {
      const response = await api.listContracts({ page: 1, page_size: 5 })
      return response.data
    }
  })

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    toast.success('Вы вышли из системы', {
      icon: '👋',
      style: { borderRadius: '12px' }
    })
    router.push('/login')
  }

  if (userLoading) {
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

  const contractsUsagePercent = ((user?.contracts_today || 0) / (user?.max_contracts_per_day || 1)) * 100
  const llmUsagePercent = ((user?.llm_requests_today || 0) / (user?.max_llm_requests_per_day || 1)) * 100

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Modern Header with Gradient */}
      <header className="bg-white/80 backdrop-blur-lg shadow-lg border-b border-white/20 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-4"
            >
              <div className="w-12 h-12 bg-gradient-primary rounded-xl shadow-glow flex items-center justify-center">
                <span className="text-2xl">📄</span>
              </div>
              <div>
                <h1 className="text-2xl font-bold gradient-text">Contract AI System</h1>
                <p className="text-sm text-gray-600">Привет, {user?.name}! 👋</p>
              </div>
            </motion.div>

            <div className="flex items-center space-x-4">
              <motion.div
                whileHover={{ scale: 1.05 }}
                className="px-4 py-2 bg-gradient-primary text-white rounded-xl shadow-lg font-semibold text-sm"
              >
                {user?.subscription_tier.toUpperCase()}
              </motion.div>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleLogout}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-xl transition-all duration-300"
              >
                Выход
              </motion.button>
            </div>
          </div>
        </div>
      </header>

      {/* Welcome Modal */}
      {showWelcome && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowWelcome(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-3xl shadow-2xl max-w-2xl w-full p-8 max-h-[90vh] overflow-y-auto"
          >
            <div className="text-center mb-6">
              <div className={`inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br ${roleColor.gradient} mb-4`}>
                <span className="text-4xl">👋</span>
              </div>
              <h2 className="text-3xl font-bold gradient-text mb-2">
                Добро пожаловать, {user?.name || 'Пользователь'}!
              </h2>
              <p className={`text-lg font-semibold ${roleColor.text}`}>
                Ваша роль: {roleLabel}
              </p>
            </div>

            <div className={`p-6 rounded-2xl ${roleColor.bg} mb-6`}>
              <h3 className="text-xl font-bold text-slate-800 mb-4">
                Ваши возможности:
              </h3>
              <ul className="space-y-3">
                {permissions.features.map((feature, idx) => (
                  <motion.li
                    key={idx}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.3 + idx * 0.05 }}
                    className="flex items-center gap-3"
                  >
                    <span className="text-green-500 text-xl">✓</span>
                    <span className="text-slate-700">{feature}</span>
                  </motion.li>
                ))}
              </ul>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="p-4 bg-slate-50 rounded-xl text-center">
                <p className="text-sm text-slate-600 mb-1">Лимит договоров</p>
                <p className="text-2xl font-bold text-slate-800">
                  {permissions.maxContractsPerDay === -1 ? '∞' : permissions.maxContractsPerDay}
                </p>
                <p className="text-xs text-slate-500">в день</p>
              </div>
              <div className="p-4 bg-slate-50 rounded-xl text-center">
                <p className="text-sm text-slate-600 mb-1">Форматы экспорта</p>
                <p className="text-lg font-bold text-slate-800">
                  {permissions.exportFormats.join(', ').toUpperCase() || 'Нет'}
                </p>
              </div>
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setShowWelcome(false)}
              className={`w-full py-4 rounded-xl font-semibold text-white shadow-lg bg-gradient-to-r ${roleColor.gradient}`}
            >
              Начать работу
            </motion.button>
          </motion.div>
        </motion.div>
      )}

      {/* Change Password Modal */}
      <ChangePasswordModal
        isOpen={showPasswordChange}
        onClose={() => setShowPasswordChange(false)}
        userEmail={user?.email || ''}
      />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards with Gradients */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8"
        >
          {/* Contracts Card */}
          <motion.div variants={itemVariants} whileHover={{ y: -4 }} className="relative">
            <div className="card-modern overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-400/20 to-blue-600/20 rounded-full blur-2xl" />
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm font-semibold text-gray-600 mb-1">Контракты сегодня</p>
                    <p className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent">
                      {user?.contracts_today || 0}
                      <span className="text-lg text-gray-400 font-normal"> / {user?.max_contracts_per_day}</span>
                    </p>
                  </div>
                  <motion.div
                    whileHover={{ rotate: 360 }}
                    transition={{ duration: 0.5 }}
                    className="p-4 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-2xl shadow-lg"
                  >
                    <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </motion.div>
                </div>

                {/* Progress Bar */}
                <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${contractsUsagePercent}%` }}
                    transition={{ duration: 1, delay: 0.5 }}
                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500 to-cyan-600 rounded-full shadow-lg"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-2">Использовано {contractsUsagePercent.toFixed(0)}%</p>
              </div>
            </div>
          </motion.div>

          {/* LLM Requests Card */}
          <motion.div variants={itemVariants} whileHover={{ y: -4 }} className="relative">
            <div className="card-modern overflow-hidden">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-purple-400/20 to-pink-600/20 rounded-full blur-2xl" />
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm font-semibold text-gray-600 mb-1">LLM запросы</p>
                    <p className="text-4xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                      {user?.llm_requests_today || 0}
                      <span className="text-lg text-gray-400 font-normal"> / {user?.max_llm_requests_per_day}</span>
                    </p>
                  </div>
                  <motion.div
                    whileHover={{ scale: 1.1 }}
                    transition={{ type: "spring", stiffness: 300 }}
                    className="p-4 bg-gradient-to-br from-purple-500 to-pink-600 rounded-2xl shadow-lg"
                  >
                    <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </motion.div>
                </div>

                {/* Progress Bar */}
                <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${llmUsagePercent}%` }}
                    transition={{ duration: 1, delay: 0.7 }}
                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-purple-500 to-pink-600 rounded-full shadow-lg"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-2">Использовано {llmUsagePercent.toFixed(0)}%</p>
              </div>
            </div>
          </motion.div>

          {/* Subscription Card */}
          <motion.div variants={itemVariants} whileHover={{ y: -4 }} className="relative">
            <div className="card-modern overflow-hidden bg-gradient-to-br from-amber-50 to-orange-50">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-orange-400/20 to-amber-600/20 rounded-full blur-2xl" />
              <div className="relative z-10">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm font-semibold text-gray-600 mb-1">Тарифный план</p>
                    <p className="text-3xl font-bold bg-gradient-to-r from-orange-600 to-amber-600 bg-clip-text text-transparent capitalize">
                      {user?.subscription_tier}
                    </p>
                  </div>
                  <motion.div
                    whileHover={{ rotate: 180 }}
                    transition={{ duration: 0.5 }}
                    className="p-4 bg-gradient-to-br from-orange-500 to-amber-600 rounded-2xl shadow-lg"
                  >
                    <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </motion.div>
                </div>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => router.push('/pricing')}
                  className="w-full mt-2 py-2 bg-gradient-to-r from-orange-500 to-amber-600 text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300"
                >
                  Улучшить тариф
                </motion.button>
              </div>
            </div>
          </motion.div>
        </motion.div>

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="card-modern mb-8"
        >
          <h2 className="text-2xl font-bold gradient-text mb-6">Быстрые действия</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { icon: '📤', label: 'Загрузить договор', route: '/contracts/upload', gradient: 'from-blue-500 to-cyan-600', permission: 'canAnalyze' },
              { icon: '✨', label: 'Генерировать', route: '/contracts/generate', gradient: 'from-purple-500 to-pink-600', permission: 'canGenerate' },
              { icon: '📋', label: 'Все договоры', route: '/contracts', gradient: 'from-green-500 to-emerald-600', permission: null },
              { icon: '💎', label: 'Тарифы', route: '/pricing', gradient: 'from-orange-500 to-amber-600', permission: null }
            ]
            .filter(action => !action.permission || permissions[action.permission as keyof typeof permissions])
            .map((action, idx) => (
              <motion.button
                key={idx}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.4 + idx * 0.1 }}
                whileHover={{ y: -4, scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => router.push(action.route)}
                className="relative group overflow-hidden rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300"
              >
                <div className={`absolute inset-0 bg-gradient-to-br ${action.gradient} opacity-90 group-hover:opacity-100 transition-opacity`} />
                <div className="relative z-10 p-6 text-white text-center">
                  <div className="text-4xl mb-3">{action.icon}</div>
                  <div className="text-base font-semibold">{action.label}</div>
                </div>
              </motion.button>
            ))}
          </div>
        </motion.div>

        {/* Recent Contracts */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="card-modern"
        >
          <h2 className="text-2xl font-bold gradient-text mb-6">Последние договоры</h2>

          {contractsLoading ? (
            <div className="flex justify-center py-12">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full"
              />
            </div>
          ) : contractsData && contractsData.contracts?.length > 0 ? (
            <div className="space-y-3">
              {contractsData.contracts.map((contract: Contract, idx: number) => (
                <motion.div
                  key={contract.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.6 + idx * 0.1 }}
                  whileHover={{ x: 4 }}
                  onClick={() => router.push(`/contracts/${contract.id}`)}
                  className="p-5 bg-gradient-to-r from-white to-gray-50 rounded-xl border border-gray-100 hover:border-primary-300 cursor-pointer transition-all duration-300 hover:shadow-lg"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4 flex-1">
                      <div className="w-12 h-12 bg-gradient-primary rounded-xl flex items-center justify-center shadow-lg">
                        <span className="text-2xl">📄</span>
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 mb-1">{contract.file_name}</h3>
                        <div className="flex items-center space-x-3 text-sm text-gray-600">
                          <span className="flex items-center">
                            <svg className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                            </svg>
                            {contract.contract_type}
                          </span>
                          <span className="flex items-center">
                            <svg className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            {new Date(contract.created_at).toLocaleDateString('ru-RU')}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      <span className={`px-4 py-2 rounded-full text-sm font-semibold shadow-sm
                        ${contract.status === 'completed' ? 'badge-success' : ''}
                        ${contract.status === 'analyzing' ? 'badge-warning' : ''}
                        ${contract.status === 'uploaded' ? 'bg-gradient-to-r from-blue-400 to-blue-600 text-white' : ''}
                        ${contract.status === 'error' ? 'badge-danger' : ''}
                      `}>
                        {contract.status}
                      </span>
                      <svg className="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              className="text-center py-16"
            >
              <motion.div
                animate={{ y: [0, -10, 0] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="inline-block mb-6"
              >
                <div className="w-24 h-24 bg-gradient-primary rounded-3xl shadow-2xl flex items-center justify-center">
                  <span className="text-5xl">📄</span>
                </div>
              </motion.div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">Нет договоров</h3>
              <p className="text-gray-600 mb-6">Начните с загрузки вашего первого договора</p>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => router.push('/contracts/upload')}
                className="inline-flex items-center px-6 py-3 bg-gradient-primary text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300"
              >
                <svg className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Загрузить договор
              </motion.button>
            </motion.div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
