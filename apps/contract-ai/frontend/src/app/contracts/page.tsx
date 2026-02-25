'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Badge from '@/components/ui/Badge'

interface Contract {
  id: string
  name: string
  type: string
  status: 'analyzing' | 'completed' | 'error' | 'pending'
  partyA: string
  partyB: string
  uploadDate: string
  riskLevel?: 'low' | 'medium' | 'high' | 'critical'
  overallScore?: number
}

export default function ContractsListPage() {
  const router = useRouter()
  const [searchQuery, setSearchQuery] = useState('')
  const [filterType, setFilterType] = useState<string>('all')
  const [filterStatus, setFilterStatus] = useState<string>('all')

  // Mock data - будет заменен на реальные данные из API
  const [contracts] = useState<Contract[]>([
    {
      id: '1',
      name: 'Договор подряда №123',
      type: 'Договор подряда',
      status: 'completed',
      partyA: 'ООО Строймонтаж',
      partyB: 'ИП Петров П.П.',
      uploadDate: '2025-11-25',
      riskLevel: 'medium',
      overallScore: 7.5
    },
    {
      id: '2',
      name: 'Договор поставки №456',
      type: 'Договор поставки',
      status: 'completed',
      partyA: 'ООО ТоргСнаб',
      partyB: 'ООО МегаОпт',
      uploadDate: '2025-11-24',
      riskLevel: 'low',
      overallScore: 8.8
    },
    {
      id: '3',
      name: 'Трудовой договор',
      type: 'Трудовой договор',
      status: 'analyzing',
      partyA: 'ООО Компания',
      partyB: 'Иванов И.И.',
      uploadDate: '2025-11-26'
    },
    {
      id: '4',
      name: 'Договор аренды помещения',
      type: 'Договор аренды',
      status: 'completed',
      partyA: 'ООО Недвижимость Плюс',
      partyB: 'ИП Сидоров С.С.',
      uploadDate: '2025-11-23',
      riskLevel: 'high',
      overallScore: 5.2
    },
    {
      id: '5',
      name: 'Агентский договор №789',
      type: 'Агентский договор',
      status: 'error',
      partyA: 'ООО Агентство',
      partyB: 'ИП Васильев В.В.',
      uploadDate: '2025-11-22'
    }
  ])

  const contractTypes = ['all', 'Договор подряда', 'Договор поставки', 'Договор аренды', 'Трудовой договор', 'Агентский договор', 'Другое']
  const statuses = ['all', 'completed', 'analyzing', 'error', 'pending']

  const getStatusBadge = (status: string) => {
    const badges = {
      completed: { variant: 'success' as const, text: 'Завершён' },
      analyzing: { variant: 'info' as const, text: 'Анализируется...' },
      error: { variant: 'danger' as const, text: 'Ошибка' },
      pending: { variant: 'warning' as const, text: 'Ожидание' }
    }
    return badges[status as keyof typeof badges] || badges.pending
  }

  const getRiskBadge = (level: string) => {
    const badges = {
      low: { variant: 'success' as const, text: 'Низкий риск', icon: '🟢' },
      medium: { variant: 'warning' as const, text: 'Средний риск', icon: '🟡' },
      high: { variant: 'danger' as const, text: 'Высокий риск', icon: '🔴' },
      critical: { variant: 'danger' as const, text: 'Критический', icon: '⚠️' }
    }
    return badges[level as keyof typeof badges]
  }

  const getScoreColor = (score: number) => {
    if (score >= 8) return 'text-success-600'
    if (score >= 6) return 'text-warning-600'
    return 'text-danger-600'
  }

  const filteredContracts = contracts.filter(contract => {
    const matchesSearch = contract.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         contract.partyA.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         contract.partyB.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = filterType === 'all' || contract.type === filterType
    const matchesStatus = filterStatus === 'all' || contract.status === filterStatus
    return matchesSearch && matchesType && matchesStatus
  })

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
              onClick={() => router.push('/dashboard')}
            >
              <div className="w-10 h-10 bg-gradient-primary rounded-xl shadow-lg flex items-center justify-center">
                <span className="text-2xl">📄</span>
              </div>
              <span className="text-xl font-bold gradient-text">Contract AI</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center space-x-3"
            >
              <Button variant="outline" size="sm" onClick={() => router.push('/dashboard')}>
                ← Дашборд
              </Button>
              <Button variant="secondary" size="sm" onClick={() => router.push('/contracts/generate')}>
                ✨ Генератор
              </Button>
              <Button variant="primary" size="sm" onClick={() => router.push('/contracts/upload')}>
                + Загрузить
              </Button>
            </motion.div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Title & Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-5xl font-bold gradient-text mb-4">
            Мои договоры
          </h1>
          <div className="flex items-center space-x-6">
            <div className="flex items-center">
              <span className="text-3xl font-bold text-primary-600 mr-2">{contracts.length}</span>
              <span className="text-gray-600">всего договоров</span>
            </div>
            <div className="flex items-center">
              <span className="text-3xl font-bold text-success-600 mr-2">
                {contracts.filter(c => c.status === 'completed').length}
              </span>
              <span className="text-gray-600">проанализировано</span>
            </div>
          </div>
        </motion.div>

        {/* Filters & Search */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mb-8"
        >
          <Card>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Search */}
              <div className="md:col-span-1">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Поиск по названию или сторонам..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
                  />
                  <svg className="absolute left-3 top-3.5 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
              </div>

              {/* Type Filter */}
              <div>
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
                >
                  {contractTypes.map(type => (
                    <option key={type} value={type}>
                      {type === 'all' ? 'Все типы' : type}
                    </option>
                  ))}
                </select>
              </div>

              {/* Status Filter */}
              <div>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="w-full px-4 py-3 bg-white border-2 border-gray-200 rounded-xl focus:border-primary-400 focus:outline-none transition-colors"
                >
                  {statuses.map(status => (
                    <option key={status} value={status}>
                      {status === 'all' ? 'Все статусы' : getStatusBadge(status).text}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Contracts Grid */}
        {filteredContracts.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Card className="text-center py-12">
              <div className="text-6xl mb-4">📭</div>
              <h3 className="text-2xl font-bold text-gray-900 mb-2">
                Договоры не найдены
              </h3>
              <p className="text-gray-600 mb-6">
                {searchQuery || filterType !== 'all' || filterStatus !== 'all'
                  ? 'Попробуйте изменить фильтры поиска'
                  : 'Загрузите первый договор для анализа'}
              </p>
              <Button variant="primary" onClick={() => router.push('/contracts/upload')}>
                + Загрузить договор
              </Button>
            </Card>
          </motion.div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredContracts.map((contract, idx) => (
              <motion.div
                key={contract.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
              >
                <Card
                  hover
                  onClick={() => contract.status === 'completed' && router.push(`/contracts/${contract.id}`)}
                  className={contract.status !== 'completed' ? 'cursor-not-allowed opacity-75' : ''}
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-gray-900 mb-1 line-clamp-1">
                        {contract.name}
                      </h3>
                      <p className="text-sm text-gray-500">{contract.type}</p>
                    </div>
                    <Badge {...getStatusBadge(contract.status)} size="sm" />
                  </div>

                  {/* Parties */}
                  <div className="space-y-2 mb-4 pb-4 border-b border-gray-100">
                    <div className="flex items-start">
                      <span className="text-xs font-semibold text-gray-500 w-16 flex-shrink-0">
                        Сторона А:
                      </span>
                      <span className="text-sm text-gray-900 line-clamp-1">{contract.partyA}</span>
                    </div>
                    <div className="flex items-start">
                      <span className="text-xs font-semibold text-gray-500 w-16 flex-shrink-0">
                        Сторона Б:
                      </span>
                      <span className="text-sm text-gray-900 line-clamp-1">{contract.partyB}</span>
                    </div>
                  </div>

                  {/* Risk & Score */}
                  {contract.status === 'completed' && contract.riskLevel && (
                    <div className="space-y-3 mb-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-gray-700">Уровень риска:</span>
                        <Badge {...getRiskBadge(contract.riskLevel)!} size="sm">
                          {getRiskBadge(contract.riskLevel)!.icon} {getRiskBadge(contract.riskLevel)!.text}
                        </Badge>
                      </div>
                      {contract.overallScore && (
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-gray-700">Общая оценка:</span>
                          <span className={`text-2xl font-bold ${getScoreColor(contract.overallScore)}`}>
                            {contract.overallScore}/10
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Footer */}
                  <div className="flex items-center justify-between text-xs text-gray-500 mt-4 pt-4 border-t border-gray-100">
                    <div className="flex items-center">
                      <svg className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      {new Date(contract.uploadDate).toLocaleDateString('ru-RU', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric'
                      })}
                    </div>
                    {contract.status === 'completed' && (
                      <span className="text-primary-600 font-semibold hover:text-primary-700">
                        Открыть →
                      </span>
                    )}
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
