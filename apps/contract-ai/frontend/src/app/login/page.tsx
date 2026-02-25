'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { motion } from 'framer-motion'
import api from '@/services/api'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    console.log('🔥 FORM SUBMITTED!')
    console.log('Email:', email, 'Password:', password)

    setIsLoading(true)

    try {
      // Demo credentials with roles
      const demoCredentials = [
        { email: 'demo@example.com', password: 'demo123', name: 'Demo User', role: 'demo' },
        { email: 'admin@example.com', password: 'admin123', name: 'Admin User', role: 'admin' },
        { email: 'lawyer@example.com', password: 'lawyer123', name: 'Lawyer User', role: 'lawyer' },
        { email: 'junior@example.com', password: 'junior123', name: 'Junior Lawyer', role: 'junior_lawyer' },
      ]

      console.log('Looking for match...')
      const demoUser = demoCredentials.find(
        u => u.email === email && u.password === password
      )

      console.log('Match result:', demoUser)

      if (demoUser) {
        console.log('✅ DEMO USER FOUND! Setting localStorage...')
        // Demo mode - bypass API
        localStorage.setItem('access_token', 'demo_token_' + Date.now())
        localStorage.setItem('user', JSON.stringify({
          name: demoUser.name,
          email: demoUser.email,
          role: demoUser.role
        }))

        console.log('✅ LocalStorage set, showing toast...')
        toast.success(`Добро пожаловать, ${demoUser.name}!`, {
          icon: '🎉',
          style: {
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #0ea5e9, #d946ef)',
            color: '#fff',
          },
        })

        console.log('✅ Redirecting to dashboard in 100ms...')
        // Small delay to ensure localStorage is set before redirect
        setTimeout(() => {
          window.location.href = '/dashboard'
        }, 100)
        return
      }

      console.log('⚠️ No demo user found, trying API...')

      // Try real API
      const response = await api.login({
        username: email,
        password: password,
      })

      toast.success(`Добро пожаловать, ${response.user.name}!`, {
        icon: '🎉',
        style: {
          borderRadius: '12px',
          background: 'linear-gradient(135deg, #0ea5e9, #d946ef)',
          color: '#fff',
        },
      })
      router.push('/dashboard')
    } catch (error: any) {
      console.error('Login error:', error)
      toast.error(error.response?.data?.detail || 'Неверный email или пароль', {
        icon: '❌',
        style: {
          borderRadius: '12px',
        },
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Animated Background */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary-500 via-secondary-500 to-accent-500 opacity-90">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS1vcGFjaXR5PSIwLjEiIHN0cm9rZS13aWR0aD0iMSIvPjwvcGF0dGVybj48L2RlZnM+PHJlY3Qgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSIgZmlsbD0idXJsKCNncmlkKSIvPjwvc3ZnPg==')] opacity-20" />
      </div>

      {/* Floating shapes */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          className="absolute top-20 left-20 w-72 h-72 bg-white/10 rounded-full blur-3xl"
          animate={{
            y: [0, 30, 0],
            x: [0, 20, 0],
          }}
          transition={{
            duration: 8,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
        <motion.div
          className="absolute bottom-20 right-20 w-96 h-96 bg-secondary-400/20 rounded-full blur-3xl"
          animate={{
            y: [0, -40, 0],
            x: [0, -30, 0],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
        <motion.div
          className="absolute top-1/2 left-1/2 w-64 h-64 bg-accent-400/20 rounded-full blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            rotate: [0, 180, 360],
          }}
          transition={{
            duration: 15,
            repeat: Infinity,
            ease: "linear"
          }}
        />
      </div>

      {/* Main Content */}
      <div className="relative z-10 min-h-screen flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-md"
        >
          {/* Logo & Title */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.6 }}
            className="text-center mb-8"
          >
            <motion.div
              className="inline-block mb-4"
              whileHover={{ scale: 1.05, rotate: 5 }}
              transition={{ type: "spring", stiffness: 300 }}
            >
              <div className="w-20 h-20 mx-auto bg-white rounded-2xl shadow-2xl flex items-center justify-center transform rotate-3">
                <span className="text-4xl">📄</span>
              </div>
            </motion.div>

            <h1 className="text-5xl font-bold text-white mb-3">
              Contract AI
            </h1>
            <p className="text-xl text-white/90 font-medium">
              Умная работа с договорами
            </p>
          </motion.div>

          {/* Login Card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="glass backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-white/20"
          >
            <h2 className="text-2xl font-bold text-white mb-6 text-center">
              Вход в систему
            </h2>

            <form onSubmit={handleLogin} className="space-y-5">
              {/* Email Field */}
              <div>
                <label className="block text-sm font-semibold text-white mb-2">
                  Email
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg className="h-5 w-5 text-white/60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                    </svg>
                  </div>
                  <input
                    type="text"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-12 pr-4 py-3.5 bg-white/10 border-2 border-white/20 rounded-xl text-white placeholder-white/50 focus:border-white focus:ring-4 focus:ring-white/20 transition-all duration-300 outline-none backdrop-blur-sm"
                    placeholder="user@example.com"
                    required
                  />
                </div>
              </div>

              {/* Password Field */}
              <div>
                <label className="block text-sm font-semibold text-white mb-2">
                  Пароль
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <svg className="h-5 w-5 text-white/60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  </div>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-12 pr-4 py-3.5 bg-white/10 border-2 border-white/20 rounded-xl text-white placeholder-white/50 focus:border-white focus:ring-4 focus:ring-white/20 transition-all duration-300 outline-none backdrop-blur-sm"
                    placeholder="••••••••"
                    required
                  />
                </div>
              </div>

              {/* Submit Button */}
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                type="submit"
                disabled={isLoading}
                onClick={() => console.log('🖱️ BUTTON CLICKED!')}
                className="w-full py-4 bg-white text-primary-600 font-bold rounded-xl shadow-lg hover:shadow-2xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed relative overflow-hidden group"
              >
                <span className="relative z-10">
                  {isLoading ? (
                    <span className="flex items-center justify-center">
                      <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Вход...
                    </span>
                  ) : (
                    'Войти'
                  )}
                </span>
                <div className="absolute inset-0 bg-gradient-to-r from-primary-400 to-secondary-400 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              </motion.button>
            </form>

            {/* Demo Credentials */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
              className="mt-6 p-4 bg-white/10 rounded-xl border border-white/20 backdrop-blur-sm"
            >
              <p className="text-sm font-semibold text-white mb-2 flex items-center">
                <svg className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Демо-аккаунты:
              </p>
              <div className="space-y-1.5 text-xs text-white/80">
                <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                  <span className="font-semibold">Demo:</span>
                  <code className="bg-black/20 px-2 py-0.5 rounded">demo@example.com / demo123</code>
                </div>
                <div className="flex flex-col sm:flex-row sm:justify-between gap-1">
                  <span className="font-semibold">Admin:</span>
                  <code className="bg-black/20 px-2 py-0.5 rounded">admin@example.com / admin123</code>
                </div>
              </div>
            </motion.div>
          </motion.div>

          {/* Footer Links */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            className="mt-6 text-center space-y-2"
          >
            <p className="text-white/80 text-sm">
              Нет аккаунта?{' '}
              <button
                onClick={() => router.push('/register')}
                className="font-semibold text-white hover:underline"
              >
                Зарегистрироваться
              </button>
            </p>
            <p className="text-white/60 text-xs">
              © 2024 Contract AI System. Все права защищены.
            </p>
          </motion.div>
        </motion.div>
      </div>
    </div>
  )
}
