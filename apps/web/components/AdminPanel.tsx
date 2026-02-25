'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Eye,
  EyeOff,
  BarChart3,
  TrendingUp,
  Users,
  Clock,
  Activity,
  Zap,
  Globe,
  Server,
  Database,
  Download,
  RefreshCw,
  Github,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ExternalLink
} from 'lucide-react';
import SEOChart from './admin/SEOChart';
import ExportButton from './admin/ExportButton';
import NotificationBadge from './admin/NotificationBadge';
import IssueFilters from './admin/IssueFilters';
import { verifyPassword } from '@/lib/auth';

interface AdminPanelProps {
  password?: string; // Пароль для доступа (по умолчанию: "admin123")
}

export default function AdminPanel({ password = "admin123" }: AdminPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [inputPassword, setInputPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'seo' | 'technical' | 'github'>('seo');
  const [githubData, setGithubData] = useState<any>(null);
  const [isLoadingGithub, setIsLoadingGithub] = useState(false);
  const [analyticsData, setAnalyticsData] = useState<any>(null);
  const [isLoadingAnalytics, setIsLoadingAnalytics] = useState(false);
  const [filters, setFilters] = useState({
    priority: 'all',
    status: 'all',
    dateRange: 'all'
  });

    // Открытие через URL параметр ?admin=true
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      if (params.get('admin') === 'true') {
        setIsOpen(true)
      }
    }
  }, [])

  // Глобальный обработчик комбинации клавиш Ctrl+Shift+A (Windows/Linux) или Cmd+Shift+A (Mac)
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Поддержка Mac (Cmd) и Windows/Linux (Ctrl)
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'A') {
        e.preventDefault();
        setIsOpen(true);
      }
      // ESC для закрытия
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [isOpen]);

  // Загрузка GitHub данных при открытии вкладки
  useEffect(() => {
    if (isAuthenticated && activeTab === 'github' && !githubData) {
      loadGithubData();
    }
  }, [isAuthenticated, activeTab]);

  // Загрузка Analytics данных при открытии вкладки SEO
  useEffect(() => {
    if (isAuthenticated && activeTab === 'seo' && !analyticsData) {
      loadAnalyticsData();
    }
  }, [isAuthenticated, activeTab]);

  const loadGithubData = async () => {
    setIsLoadingGithub(true);
    try {
      const response = await fetch('/api/github/stats');
      const data = await response.json();
      setGithubData(data);
    } catch (error) {
      console.error('Failed to load GitHub data:', error);
    } finally {
      setIsLoadingGithub(false);
    }
  };

  const loadAnalyticsData = async () => {
    setIsLoadingAnalytics(true);
    try {
      const response = await fetch('/api/analytics/combined');
      const result = await response.json();
      setAnalyticsData(result);
    } catch (error) {
      console.error('Failed to load Analytics data:', error);
    } finally {
      setIsLoadingAnalytics(false);
    }
  };

  // Фильтрация задач
  const getFilteredTasks = () => {
    if (!githubData || !githubData.top_seo_tasks) return [];

    let filtered = [...githubData.top_seo_tasks];

    // Фильтр по приоритету
    if (filters.priority !== 'all') {
      filtered = filtered.filter((task: any) => task.priority === filters.priority);
    }

    // Фильтр по статусу уже применен в API (мы берем только открытые)
    // Но можно добавить дополнительную логику если нужно

    return filtered;
  };

  const handleClose = () => {
    setIsOpen(false);
    setInputPassword('');
    setError('');
    setShowPassword(false);
    // Не сбрасываем аутентификацию при закрытии
  };

  const handleAuth = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputPassword === password) {
      setIsAuthenticated(true);
      setError('');
      setInputPassword('');
    } else {
      setError('Неверный пароль');
      setInputPassword('');
    }
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setInputPassword('');
    setError('');
  };

  // Данные для SEO - используем реальные данные из Analytics API или fallback на mock
  const seoData = analyticsData?.data || {
    today: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: '0:00',
      conversions: 0
    },
    week: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: '0:00',
      conversions: 0
    },
    month: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: '0:00',
      conversions: 0
    },
    topPages: [],
    sources: [],
  };

  // Технические данные
  const technicalData = {
    performance: {
      lighthouse: 95,
      fcp: 1.2,
      lcp: 1.8,
      tti: 2.3,
      cls: 0.02,
      bundleSize: '187 KB',
      gzipped: '64 KB'
    },
    server: {
      uptime: '99.97%',
      responseTime: '245ms',
      requests: '45,234',
      errors: '0.02%'
    },
    deployment: {
      version: '1.2.4',
      lastDeploy: '2 часа назад',
      environment: 'Production',
      region: 'EU-Central'
    }
  };

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Overlay */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
              onClick={handleClose}
            />

            {/* Modal */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-4 md:inset-8 lg:inset-16 bg-slate-900 rounded-2xl shadow-2xl z-50 overflow-hidden border border-amber-500/20"
            >
              {/* Header */}
              <div className="bg-gradient-to-r from-slate-800 to-slate-900 border-b border-amber-500/20 px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  <h2 className="text-xl font-bold text-white">
                    Admin Panel
                  </h2>
                  {isAuthenticated && (
                    <span className="text-xs text-amber-400 bg-amber-500/10 px-2 py-1 rounded">
                      Авторизован
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {isAuthenticated && githubData && (
                    <>
                      <NotificationBadge githubData={githubData} />
                      <ExportButton data={githubData} filename="admin-panel-data" />
                    </>
                  )}
                  {isAuthenticated && (
                    <button
                      onClick={handleLogout}
                      className="text-sm text-slate-400 hover:text-white px-3 py-1 rounded-lg hover:bg-slate-800 transition-colors"
                    >
                      Выйти
                    </button>
                  )}
                  <button
                    onClick={handleClose}
                    className="text-slate-400 hover:text-white p-2 rounded-lg hover:bg-slate-800 transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="h-[calc(100%-72px)] overflow-y-auto">
                {!isAuthenticated ? (
                  /* Login Form */
                  <div className="flex items-center justify-center h-full">
                    <motion.div
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="w-full max-w-md p-8"
                    >
                      <div className="text-center mb-8">
                        <div className="w-16 h-16 bg-amber-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
                          <Server className="w-8 h-8 text-amber-400" />
                        </div>
                        <h3 className="text-2xl font-bold text-white mb-2">
                          Авторизация
                        </h3>
                        <p className="text-slate-400 text-sm">
                          Введите пароль для доступа к панели администратора
                        </p>
                      </div>

                      <form onSubmit={handleAuth} className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-slate-300 mb-2">
                            Пароль
                          </label>
                          <div className="relative">
                            <input
                              type={showPassword ? 'text' : 'password'}
                              value={inputPassword}
                              onChange={(e) => {
                                setInputPassword(e.target.value);
                                setError('');
                              }}
                              className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
                              placeholder="Введите пароль"
                              autoFocus
                            />
                            <button
                              type="button"
                              onClick={() => setShowPassword(!showPassword)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors"
                            >
                              {showPassword ? (
                                <EyeOff className="w-5 h-5" />
                              ) : (
                                <Eye className="w-5 h-5" />
                              )}
                            </button>
                          </div>
                          {error && (
                            <motion.p
                              initial={{ opacity: 0, y: -10 }}
                              animate={{ opacity: 1, y: 0 }}
                              className="text-red-400 text-sm mt-2"
                            >
                              {error}
                            </motion.p>
                          )}
                        </div>

                        <button
                          type="submit"
                          className="w-full bg-gradient-to-r from-amber-600 to-amber-700 text-white py-3 rounded-lg font-medium hover:from-amber-700 hover:to-amber-800 transition-all hover:scale-105 shadow-lg shadow-amber-500/20"
                        >
                          Войти
                        </button>
                      </form>

                      <div className="mt-6 text-center text-xs text-slate-500">
                        Совет: Используйте <kbd className="px-2 py-1 bg-slate-800 rounded border border-slate-700">Ctrl</kbd> +
                        <kbd className="px-2 py-1 bg-slate-800 rounded border border-slate-700 mx-1">Shift</kbd> +
                        <kbd className="px-2 py-1 bg-slate-800 rounded border border-slate-700">A</kbd> для быстрого доступа
                      </div>
                    </motion.div>
                  </div>
                ) : (
                  /* Dashboard */
                  <div className="p-6">
                    {/* Tabs */}
                    <div className="flex gap-2 mb-6 border-b border-slate-800">
                      {[
                        { id: 'seo' as const, label: 'SEO & Аналитика', icon: BarChart3 },
                        { id: 'technical' as const, label: 'Технические данные', icon: Zap },
                        { id: 'github' as const, label: 'GitHub & SEO Reports', icon: Github }
                      ].map((tab) => (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={`flex items-center gap-2 px-4 py-3 rounded-t-lg transition-all ${
                            activeTab === tab.id
                              ? 'bg-slate-800 text-amber-400 border-b-2 border-amber-500'
                              : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                          }`}
                        >
                          <tab.icon className="w-4 h-4" />
                          <span className="font-medium">{tab.label}</span>
                        </button>
                      ))}
                    </div>

                    {/* SEO Tab */}
                    {activeTab === 'seo' && (
                      <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="space-y-6"
                      >
                        {/* Loading Indicator & Sources */}
                        {isLoadingAnalytics ? (
                          <div className="flex items-center justify-center py-12">
                            <div className="flex flex-col items-center gap-3">
                              <RefreshCw className="w-8 h-8 text-amber-400 animate-spin" />
                              <p className="text-slate-400">Загрузка данных аналитики...</p>
                            </div>
                          </div>
                        ) : analyticsData?.sources && analyticsData.sources.length > 0 ? (
                          <div className="bg-gradient-to-r from-amber-500/10 to-green-500/10 border border-amber-500/20 rounded-lg p-3">
                            <div className="flex items-center gap-2">
                              <Activity className="w-4 h-4 text-amber-400" />
                              <span className="text-sm text-slate-300">
                                Источники данных: <span className="text-amber-400 font-semibold">{analyticsData.sources.join(', ')}</span>
                              </span>
                            </div>
                          </div>
                        ) : (
                          <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
                            <div className="flex items-center gap-2">
                              <AlertCircle className="w-5 h-5 text-yellow-400" />
                              <div>
                                <p className="text-slate-300 text-sm">
                                  Аналитика не настроена. Настройте Google Analytics 4 или Yandex Metrika для получения реальных данных.
                                </p>
                                <p className="text-slate-500 text-xs mt-1">
                                  См. документацию: docs/ADMIN_PANEL.md
                                </p>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Period Stats */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {[
                            { period: 'Сегодня', data: seoData.today },
                            { period: 'Неделя', data: seoData.week },
                            { period: 'Месяц', data: seoData.month }
                          ].map((item, idx) => (
                            <div key={idx} className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                              <h3 className="text-amber-400 font-semibold mb-4">{item.period}</h3>
                              <div className="space-y-3">
                                <div className="flex justify-between items-center">
                                  <span className="text-slate-400 text-sm">Визиты</span>
                                  <span className="text-white font-bold">{item.data.visits.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-slate-400 text-sm">Просмотры</span>
                                  <span className="text-white font-bold">{item.data.pageviews.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-slate-400 text-sm">Уникальные</span>
                                  <span className="text-white font-bold">{item.data.uniqueVisitors.toLocaleString()}</span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-slate-400 text-sm">Bounce Rate</span>
                                  <span className="text-white font-bold">{item.data.bounceRate}%</span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-slate-400 text-sm">Ср. время</span>
                                  <span className="text-white font-bold">{item.data.avgDuration}</span>
                                </div>
                                <div className="flex justify-between items-center pt-2 border-t border-slate-700">
                                  <span className="text-slate-400 text-sm">Конверсии</span>
                                  <span className="text-green-400 font-bold">{item.data.conversions}</span>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Top Pages */}
                        <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                            <TrendingUp className="w-5 h-5 text-amber-400" />
                            Топ страниц
                          </h3>
                          <div className="space-y-3">
                            {seoData.topPages.map((page: any, idx: number) => (
                              <div key={idx} className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg">
                                <div className="flex items-center gap-3">
                                  <span className="text-amber-400 font-bold text-sm">#{idx + 1}</span>
                                  <code className="text-slate-300">{page.page}</code>
                                </div>
                                <div className="flex items-center gap-4 text-sm">
                                  <span className="text-slate-400">{page.visits.toLocaleString()} визитов</span>
                                  <span className="text-slate-400">{page.avgTime} ср. время</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Traffic Sources */}
                        <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                            <Globe className="w-5 h-5 text-amber-400" />
                            Источники трафика
                          </h3>
                          <div className="space-y-3">
                            {seoData.sources.map((source: any, idx: number) => (
                              <div key={idx}>
                                <div className="flex justify-between mb-1">
                                  <span className="text-slate-300">{source.name}</span>
                                  <span className="text-white font-semibold">{source.percentage}%</span>
                                </div>
                                <div className="w-full bg-slate-700 rounded-full h-2">
                                  <div
                                    className="bg-gradient-to-r from-amber-600 to-amber-400 h-2 rounded-full transition-all"
                                    style={{ width: `${source.percentage}%` }}
                                  />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </motion.div>
                    )}

                    {/* Technical Tab */}
                    {activeTab === 'technical' && (
                      <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="space-y-6"
                      >
                        {/* Performance Metrics */}
                        <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                            <Zap className="w-5 h-5 text-amber-400" />
                            Производительность
                          </h3>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">Lighthouse Score</div>
                              <div className="text-2xl font-bold text-green-400">{technicalData.performance.lighthouse}</div>
                            </div>
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">FCP</div>
                              <div className="text-2xl font-bold text-white">{technicalData.performance.fcp}s</div>
                            </div>
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">LCP</div>
                              <div className="text-2xl font-bold text-white">{technicalData.performance.lcp}s</div>
                            </div>
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">TTI</div>
                              <div className="text-2xl font-bold text-white">{technicalData.performance.tti}s</div>
                            </div>
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">CLS</div>
                              <div className="text-2xl font-bold text-green-400">{technicalData.performance.cls}</div>
                            </div>
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">Bundle Size</div>
                              <div className="text-xl font-bold text-white">{technicalData.performance.bundleSize}</div>
                            </div>
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">Gzipped</div>
                              <div className="text-xl font-bold text-white">{technicalData.performance.gzipped}</div>
                            </div>
                          </div>
                        </div>

                        {/* Server Stats */}
                        <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                            <Server className="w-5 h-5 text-amber-400" />
                            Серверные метрики
                          </h3>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">Uptime</div>
                              <div className="text-2xl font-bold text-green-400">{technicalData.server.uptime}</div>
                            </div>
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">Response Time</div>
                              <div className="text-2xl font-bold text-white">{technicalData.server.responseTime}</div>
                            </div>
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">Requests</div>
                              <div className="text-2xl font-bold text-white">{technicalData.server.requests}</div>
                            </div>
                            <div className="bg-slate-900/50 p-4 rounded-lg">
                              <div className="text-slate-400 text-sm mb-1">Error Rate</div>
                              <div className="text-2xl font-bold text-green-400">{technicalData.server.errors}</div>
                            </div>
                          </div>
                        </div>

                        {/* Deployment Info */}
                        <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                            <Database className="w-5 h-5 text-amber-400" />
                            Информация о деплое
                          </h3>
                          <div className="space-y-3">
                            <div className="flex justify-between items-center p-3 bg-slate-900/50 rounded-lg">
                              <span className="text-slate-400">Версия</span>
                              <span className="text-white font-mono">{technicalData.deployment.version}</span>
                            </div>
                            <div className="flex justify-between items-center p-3 bg-slate-900/50 rounded-lg">
                              <span className="text-slate-400">Последний деплой</span>
                              <span className="text-white">{technicalData.deployment.lastDeploy}</span>
                            </div>
                            <div className="flex justify-between items-center p-3 bg-slate-900/50 rounded-lg">
                              <span className="text-slate-400">Окружение</span>
                              <span className="text-green-400 font-semibold">{technicalData.deployment.environment}</span>
                            </div>
                            <div className="flex justify-between items-center p-3 bg-slate-900/50 rounded-lg">
                              <span className="text-slate-400">Регион</span>
                              <span className="text-white">{technicalData.deployment.region}</span>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    )}

                    {/* GitHub Tab */}
                    {activeTab === 'github' && (
                      <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="space-y-6"
                      >
                        {isLoadingGithub ? (
                          <div className="flex items-center justify-center h-64">
                            <RefreshCw className="w-8 h-8 text-amber-400 animate-spin" />
                          </div>
                        ) : githubData ? (
                          <>
                            {/* SEO Report Card */}
                            {githubData.seo_report && (
                              <div className="bg-gradient-to-br from-amber-500/10 to-orange-500/10 rounded-xl p-6 border border-amber-500/30">
                                <div className="flex items-center justify-between mb-4">
                                  <h3 className="text-white font-semibold text-lg flex items-center gap-2">
                                    <Activity className="w-5 h-5 text-amber-400" />
                                    Последний SEO Отчет
                                  </h3>
                                  {githubData.seo_report.report_url && (
                                    <a
                                      href={githubData.seo_report.report_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="flex items-center gap-1 text-amber-400 hover:text-amber-300 text-sm"
                                    >
                                      Открыть <ExternalLink className="w-3 h-3" />
                                    </a>
                                  )}
                                </div>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                  <div className="bg-slate-900/50 p-4 rounded-lg">
                                    <div className="text-slate-400 text-sm mb-1">SEO Score</div>
                                    <div className={`text-3xl font-bold ${
                                      (githubData.seo_report.score || 0) >= 80 ? 'text-green-400' :
                                      (githubData.seo_report.score || 0) >= 60 ? 'text-yellow-400' :
                                      'text-red-400'
                                    }`}>
                                      {githubData.seo_report.score || 'N/A'}<span className="text-lg">/100</span>
                                    </div>
                                  </div>
                                  <div className="bg-slate-900/50 p-4 rounded-lg">
                                    <div className="text-slate-400 text-sm mb-1">Predicted Position</div>
                                    <div className="text-3xl font-bold text-white">
                                      {githubData.seo_report.predicted_position?.toFixed(1) || 'N/A'}
                                    </div>
                                  </div>
                                  <div className="bg-slate-900/50 p-4 rounded-lg">
                                    <div className="text-slate-400 text-sm mb-1">Readability</div>
                                    <div className="text-2xl font-bold text-white">
                                      {githubData.seo_report.readability || 'N/A'}<span className="text-sm">/100</span>
                                    </div>
                                  </div>
                                  <div className="bg-slate-900/50 p-4 rounded-lg">
                                    <div className="text-slate-400 text-sm mb-1">E-E-A-T Score</div>
                                    <div className="text-2xl font-bold text-white">
                                      {githubData.seo_report.eeat_score || 'N/A'}<span className="text-sm">/100</span>
                                    </div>
                                  </div>
                                </div>
                                {githubData.seo_report.report_date && (
                                  <div className="mt-4 text-sm text-slate-400">
                                    Последнее обновление: {new Date(githubData.seo_report.report_date).toLocaleString('ru-RU')}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Issues Statistics */}
                            <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                              <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                                <AlertCircle className="w-5 h-5 text-amber-400" />
                                Статистика Issues
                              </h3>
                              <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
                                <div className="bg-slate-900/50 p-4 rounded-lg">
                                  <div className="text-slate-400 text-sm mb-1">Всего</div>
                                  <div className="text-2xl font-bold text-white">{githubData.issues?.total || 0}</div>
                                </div>
                                <div className="bg-slate-900/50 p-4 rounded-lg">
                                  <div className="text-slate-400 text-sm mb-1">Открыто</div>
                                  <div className="text-2xl font-bold text-green-400">{githubData.issues?.open || 0}</div>
                                </div>
                                <div className="bg-slate-900/50 p-4 rounded-lg">
                                  <div className="text-slate-400 text-sm mb-1">Закрыто</div>
                                  <div className="text-2xl font-bold text-slate-400">{githubData.issues?.closed || 0}</div>
                                </div>
                                <div className="bg-slate-900/50 p-4 rounded-lg">
                                  <div className="text-slate-400 text-sm mb-1">SEO Critical</div>
                                  <div className="text-2xl font-bold text-red-400">{githubData.issues?.seo_critical || 0}</div>
                                </div>
                                <div className="bg-slate-900/50 p-4 rounded-lg">
                                  <div className="text-slate-400 text-sm mb-1">SEO High</div>
                                  <div className="text-2xl font-bold text-orange-400">{githubData.issues?.seo_high || 0}</div>
                                </div>
                                <div className="bg-slate-900/50 p-4 rounded-lg">
                                  <div className="text-slate-400 text-sm mb-1">SEO Medium</div>
                                  <div className="text-2xl font-bold text-yellow-400">{githubData.issues?.seo_medium || 0}</div>
                                </div>
                              </div>
                            </div>

                            {/* SEO Score Chart */}
                            {githubData.seo_history && githubData.seo_history.length > 0 && (
                              <SEOChart data={githubData.seo_history} />
                            )}

                            {/* Top SEO Tasks */}
                            {githubData.top_seo_tasks && githubData.top_seo_tasks.length > 0 && (
                              <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                                <div className="flex items-center justify-between mb-4">
                                  <h3 className="text-white font-semibold flex items-center gap-2">
                                    <TrendingUp className="w-5 h-5 text-amber-400" />
                                    Приоритетные SEO задачи
                                  </h3>
                                  <IssueFilters onFilterChange={setFilters} />
                                </div>
                                <div className="space-y-3">
                                  {getFilteredTasks().map((task: any, idx: number) => (
                                    <div key={task.id} className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg hover:bg-slate-900 transition-colors">
                                      <div className="flex items-center gap-3 flex-1">
                                        <span className={`px-2 py-1 rounded text-xs font-semibold ${
                                          task.priority === 'critical' ? 'bg-red-500/20 text-red-400' :
                                          task.priority === 'high' ? 'bg-orange-500/20 text-orange-400' :
                                          'bg-yellow-500/20 text-yellow-400'
                                        }`}>
                                          {task.priority.toUpperCase()}
                                        </span>
                                        <span className="text-slate-300 flex-1">#{task.number} {task.title}</span>
                                      </div>
                                      <a
                                        href={task.html_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-amber-400 hover:text-amber-300"
                                      >
                                        <ExternalLink className="w-4 h-4" />
                                      </a>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Workflow Runs */}
                            {githubData.workflows && githubData.workflows.recent && githubData.workflows.recent.length > 0 && (
                              <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                                <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                                  <Activity className="w-5 h-5 text-amber-400" />
                                  Последние Workflow Runs
                                </h3>
                                <div className="space-y-3">
                                  {githubData.workflows.recent.map((run: any) => (
                                    <div key={run.id} className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg">
                                      <div className="flex items-center gap-3">
                                        {run.conclusion === 'success' ? (
                                          <CheckCircle2 className="w-5 h-5 text-green-400" />
                                        ) : run.conclusion === 'failure' ? (
                                          <XCircle className="w-5 h-5 text-red-400" />
                                        ) : (
                                          <Clock className="w-5 h-5 text-yellow-400" />
                                        )}
                                        <div>
                                          <div className="text-white font-medium">{run.name}</div>
                                          <div className="text-sm text-slate-400">
                                            Run #{run.run_number} • {new Date(run.created_at).toLocaleString('ru-RU')}
                                          </div>
                                        </div>
                                      </div>
                                      {run.html_url && (
                                        <a
                                          href={run.html_url}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-amber-400 hover:text-amber-300"
                                        >
                                          <ExternalLink className="w-4 h-4" />
                                        </a>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Refresh Button */}
                            <div className="flex justify-center">
                              <button
                                onClick={loadGithubData}
                                className="flex items-center gap-2 px-6 py-3 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors"
                              >
                                <RefreshCw className="w-4 h-4" />
                                Обновить данные
                              </button>
                            </div>
                          </>
                        ) : (
                          <div className="bg-slate-800/50 rounded-xl p-8 border border-slate-700/50 text-center">
                            <Github className="w-16 h-16 text-amber-400 mx-auto mb-4" />
                            <h3 className="text-white text-xl font-semibold mb-2">
                              GitHub интеграция
                            </h3>
                            <p className="text-slate-400 mb-6">
                              Нет данных для отображения
                            </p>
                            <button
                              onClick={loadGithubData}
                              className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors mx-auto"
                            >
                              <RefreshCw className="w-4 h-4" />
                              Загрузить данные
                            </button>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
