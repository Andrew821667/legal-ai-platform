export type UserRole = 'admin' | 'senior_lawyer' | 'lawyer' | 'junior_lawyer' | 'demo'

export interface RolePermissions {
  canAnalyze: boolean
  canGenerate: boolean
  canCompare: boolean
  canExport: boolean
  canManageUsers: boolean
  canViewAnalytics: boolean
  canEditTemplates: boolean
  maxContractsPerDay: number
  maxLLMRequestsPerDay: number
  exportFormats: string[]
  features: string[]
}

export const rolePermissions: Record<UserRole, RolePermissions> = {
  admin: {
    canAnalyze: true,
    canGenerate: true,
    canCompare: true,
    canExport: true,
    canManageUsers: true,
    canViewAnalytics: true,
    canEditTemplates: true,
    maxContractsPerDay: -1, // unlimited
    maxLLMRequestsPerDay: -1,
    exportFormats: ['docx', 'pdf', 'json'],
    features: [
      'Анализ договоров (безлимит)',
      'Генерация договоров',
      'Сравнение версий',
      'Протоколы разногласий',
      'Управление пользователями',
      'Аналитика и метрики',
      'Редактирование шаблонов',
      'Экспорт в DOCX/PDF/JSON',
      'Audit logs',
    ]
  },
  senior_lawyer: {
    canAnalyze: true,
    canGenerate: true,
    canCompare: true,
    canExport: true,
    canManageUsers: false,
    canViewAnalytics: true,
    canEditTemplates: true,
    maxContractsPerDay: 100,
    maxLLMRequestsPerDay: 200000, // ~$2.00 worth
    exportFormats: ['docx', 'pdf', 'json'],
    features: [
      'Анализ договоров (100/день)',
      'Генерация договоров',
      'Сравнение версий',
      'Протоколы разногласий',
      'Расширенная аналитика',
      'Редактирование шаблонов',
      'Экспорт в DOCX/PDF/JSON',
      'История версий',
    ]
  },
  lawyer: {
    canAnalyze: true,
    canGenerate: true,
    canCompare: true,
    canExport: true,
    canManageUsers: false,
    canViewAnalytics: false,
    canEditTemplates: false,
    maxContractsPerDay: 50,
    maxLLMRequestsPerDay: 50000, // ~$0.50 worth
    exportFormats: ['docx', 'pdf'],
    features: [
      'Анализ договоров (50/день)',
      'Генерация из шаблонов',
      'Сравнение версий (10/день)',
      'Базовая аналитика',
      'Экспорт в DOCX/PDF',
      'Просмотр истории',
    ]
  },
  junior_lawyer: {
    canAnalyze: true,
    canGenerate: false,
    canCompare: false,
    canExport: true,
    canManageUsers: false,
    canViewAnalytics: false,
    canEditTemplates: false,
    maxContractsPerDay: 10,
    maxLLMRequestsPerDay: 10000, // ~$0.10 worth
    exportFormats: ['pdf'],
    features: [
      'Анализ договоров (10/день)',
      'Просмотр результатов',
      'Экспорт в PDF',
      'Базовая информация',
    ]
  },
  demo: {
    canAnalyze: true,
    canGenerate: false,
    canCompare: false,
    canExport: false,
    canManageUsers: false,
    canViewAnalytics: false,
    canEditTemplates: false,
    maxContractsPerDay: 3,
    maxLLMRequestsPerDay: 1000,
    exportFormats: [],
    features: [
      'Анализ договоров (3/день)',
      'Просмотр демо-функций',
      'Ограниченный функционал',
    ]
  }
}

export const roleColors: Record<UserRole, { gradient: string; bg: string; text: string; badge: string }> = {
  admin: {
    gradient: 'from-red-500 to-orange-600',
    bg: 'bg-gradient-to-r from-red-50 to-orange-50',
    text: 'text-orange-600',
    badge: 'bg-gradient-to-r from-red-500 to-orange-600 text-white'
  },
  senior_lawyer: {
    gradient: 'from-purple-500 to-pink-600',
    bg: 'bg-gradient-to-r from-purple-50 to-pink-50',
    text: 'text-purple-600',
    badge: 'bg-gradient-to-r from-purple-500 to-pink-600 text-white'
  },
  lawyer: {
    gradient: 'from-blue-500 to-cyan-600',
    bg: 'bg-gradient-to-r from-blue-50 to-cyan-50',
    text: 'text-blue-600',
    badge: 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white'
  },
  junior_lawyer: {
    gradient: 'from-green-500 to-emerald-600',
    bg: 'bg-gradient-to-r from-green-50 to-emerald-50',
    text: 'text-green-600',
    badge: 'bg-gradient-to-r from-green-500 to-emerald-600 text-white'
  },
  demo: {
    gradient: 'from-cyan-500 to-teal-600',
    bg: 'bg-gradient-to-r from-cyan-50 to-teal-50',
    text: 'text-cyan-600',
    badge: 'bg-gradient-to-r from-cyan-500 to-teal-600 text-white'
  }
}

export const roleLabels: Record<UserRole, string> = {
  admin: 'Администратор',
  senior_lawyer: 'Старший юрист',
  lawyer: 'Юрист',
  junior_lawyer: 'Младший юрист',
  demo: 'Демо'
}

export function getUserRole(): UserRole | null {
  if (typeof window === 'undefined') return null

  const userStr = localStorage.getItem('user')
  if (!userStr) return null

  try {
    const user = JSON.parse(userStr)
    return user.role || 'demo'
  } catch {
    return null
  }
}

export function hasPermission(permission: keyof RolePermissions): boolean {
  const role = getUserRole()
  if (!role) return false

  return rolePermissions[role][permission] as boolean
}

export function getRolePermissions(role?: UserRole | null): RolePermissions {
  const userRole = role || getUserRole() || 'demo'
  return rolePermissions[userRole]
}

export function getRoleColor(role?: UserRole | null) {
  const userRole = role || getUserRole() || 'demo'
  return roleColors[userRole]
}

export function getRoleLabel(role?: UserRole | null) {
  const userRole = role || getUserRole() || 'demo'
  return roleLabels[userRole]
}
