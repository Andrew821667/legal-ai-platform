'use client';

import { useState, useEffect } from 'react';
import { Bell, X, AlertTriangle, AlertCircle, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface Notification {
  id: string;
  type: 'critical' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: Date;
}

interface NotificationBadgeProps {
  githubData: any;
}

export default function NotificationBadge({ githubData }: NotificationBadgeProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  // Генерация уведомлений на основе данных
  useEffect(() => {
    if (!githubData) return;

    const newNotifications: Notification[] = [];

    // Критические SEO проблемы
    if (githubData.seo_report && githubData.seo_report.score < 60) {
      newNotifications.push({
        id: 'seo-score-low',
        type: 'critical',
        title: 'Критический SEO Score!',
        message: `SEO Score упал до ${githubData.seo_report.score}/100. Требуется срочная оптимизация.`,
        timestamp: new Date()
      });
    }

    // Critical issues
    if (githubData.issues && githubData.issues.seo_critical > 0) {
      newNotifications.push({
        id: 'critical-issues',
        type: 'critical',
        title: 'Критические задачи!',
        message: `Обнаружено ${githubData.issues.seo_critical} критических SEO задач, требующих немедленного внимания.`,
        timestamp: new Date()
      });
    }

    // Предупреждение о снижении позиции
    if (githubData.seo_report && githubData.seo_report.predicted_position > 10) {
      newNotifications.push({
        id: 'position-warning',
        type: 'warning',
        title: 'Прогнозируемая позиция низкая',
        message: `Прогнозируемая позиция в поиске: ${githubData.seo_report.predicted_position.toFixed(1)}. Рекомендуется улучшение контента.`,
        timestamp: new Date()
      });
    }

    // Failed workflows
    if (githubData.workflows && githubData.workflows.recent) {
      const failedRuns = githubData.workflows.recent.filter((run: any) => run.conclusion === 'failure');
      if (failedRuns.length > 0) {
        newNotifications.push({
          id: 'workflow-failed',
          type: 'warning',
          title: 'Ошибки в GitHub Actions',
          message: `Обнаружено ${failedRuns.length} неудачных запусков workflow. Проверьте логи.`,
          timestamp: new Date()
        });
      }
    }

    // Информация об открытых issues
    if (githubData.issues && githubData.issues.open > 10) {
      newNotifications.push({
        id: 'many-issues',
        type: 'info',
        title: 'Много открытых задач',
        message: `У вас ${githubData.issues.open} открытых задач. Рассмотрите возможность их закрытия.`,
        timestamp: new Date()
      });
    }

    setNotifications(newNotifications);
    setUnreadCount(newNotifications.length);
  }, [githubData]);

  const getIcon = (type: string) => {
    switch (type) {
      case 'critical':
        return <AlertTriangle className="w-5 h-5 text-red-400" />;
      case 'warning':
        return <AlertCircle className="w-5 h-5 text-yellow-400" />;
      default:
        return <Info className="w-5 h-5 text-blue-400" />;
    }
  };

  const getBgColor = (type: string) => {
    switch (type) {
      case 'critical':
        return 'bg-red-500/10 border-red-500/30';
      case 'warning':
        return 'bg-yellow-500/10 border-yellow-500/30';
      default:
        return 'bg-blue-500/10 border-blue-500/30';
    }
  };

  const dismissNotification = (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
    setUnreadCount(prev => Math.max(0, prev - 1));
  };

  return (
    <div className="relative">
      {/* Notification Bell */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg hover:bg-slate-800 transition-colors"
      >
        <Bell className="w-5 h-5 text-slate-400" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center animate-pulse">
            {unreadCount}
          </span>
        )}
      </button>

      {/* Notifications Panel */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
            />

            {/* Panel */}
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              className="absolute right-0 mt-2 w-96 max-h-[500px] bg-slate-800 border border-slate-700 rounded-lg shadow-2xl z-50 overflow-hidden"
            >
              {/* Header */}
              <div className="p-4 border-b border-slate-700 flex items-center justify-between">
                <h3 className="text-white font-semibold">
                  Уведомления {unreadCount > 0 && `(${unreadCount})`}
                </h3>
                <button
                  onClick={() => setIsOpen(false)}
                  className="text-slate-400 hover:text-white transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Notifications List */}
              <div className="max-h-[400px] overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="p-8 text-center">
                    <Bell className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                    <p className="text-slate-400">Нет уведомлений</p>
                  </div>
                ) : (
                  <div className="p-2">
                    {notifications.map((notification) => (
                      <motion.div
                        key={notification.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        className={`mb-2 p-4 rounded-lg border ${getBgColor(notification.type)}`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 mt-0.5">
                            {getIcon(notification.type)}
                          </div>
                          <div className="flex-1">
                            <h4 className="text-white font-semibold text-sm mb-1">
                              {notification.title}
                            </h4>
                            <p className="text-slate-300 text-xs mb-2">
                              {notification.message}
                            </p>
                            <p className="text-slate-500 text-xs">
                              {notification.timestamp.toLocaleTimeString('ru-RU')}
                            </p>
                          </div>
                          <button
                            onClick={() => dismissNotification(notification.id)}
                            className="flex-shrink-0 text-slate-400 hover:text-white transition-colors"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </div>

              {/* Footer */}
              {notifications.length > 0 && (
                <div className="p-3 border-t border-slate-700">
                  <button
                    onClick={() => {
                      setNotifications([]);
                      setUnreadCount(0);
                    }}
                    className="w-full text-center text-sm text-slate-400 hover:text-white transition-colors"
                  >
                    Очистить все
                  </button>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
