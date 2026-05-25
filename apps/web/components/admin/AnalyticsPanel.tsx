'use client';

import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  AlertCircle,
  BarChart3,
  Brain,
  CheckCircle2,
  ClipboardList,
  FileText,
  Filter,
  Gauge,
  GitBranch,
  Globe,
  RefreshCw,
  Send,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

type AnalyticsTab = 'overview' | 'funnel' | 'contracts' | 'telegram' | 'sources' | 'retention' | 'recommendations';
type Priority = 'critical' | 'high' | 'medium' | 'low';

type FunnelStage = {
  key: string;
  title: string;
  count: number;
  fromPreviousPct: number | null;
  fromStartPct: number | null;
};

type Recommendation = {
  id: string;
  priority: Priority;
  area: string;
  title: string;
  reason: string;
  action: string;
  metric?: string;
};

type AnalyticsData = {
  generated_at: string;
  period: { days: number; hours: number; label: string };
  source_health: { core_api: boolean; site_analytics: boolean; errors: string[] };
  overview: Record<string, number>;
  site: {
    configured: boolean;
    sources: string[];
    period_metrics: Record<string, any>;
    top_pages: Array<{ page: string; visits: number; avgTime?: string }>;
    traffic_sources: Array<{ name: string; percentage: number }>;
  };
  lead_funnel: {
    stages: FunnelStage[];
    rates: Record<string, number>;
    by_status: Record<string, number>;
    by_temperature: Record<string, number>;
    by_stage: Record<string, number>;
    by_source: Array<{ name: string; count: number }>;
    recent_leads: any[];
  };
  contracts: { summary: Record<string, any>; source: string };
  telegram: {
    reader_conversion: Record<string, any>;
    reader_events: Record<string, any>;
    reader_funnel: Record<string, any>;
    reader_summary: Record<string, any>;
    publications: {
      counts: Record<string, number>;
      review: any[];
      scheduled: any[];
      failed: any[];
      archived_cleanup_count?: number;
      archived_cleanup?: any[];
      posted: any[];
    };
  };
  sources: {
    site_traffic: Array<{ name: string; percentage: number }>;
    miniapp_sources: Array<{ label: string; count: number }>;
    cta_sources: Array<{ label: string; count: number }>;
    intent_sources: Array<{ label: string; count: number }>;
    lead_sources: Array<{ name: string; count: number }>;
  };
  retention: {
    unique_users_total: number;
    miniapp_unique_users: number;
    total_events: number;
    top_actions: Array<{ label: string; count: number }>;
    top_users: Array<{ telegram_user_id: number; count: number }>;
    recent_events: any[];
  };
  recommendations: Recommendation[];
};

const tabs: Array<{ id: AnalyticsTab; label: string; icon: ReactNode }> = [
  { id: 'overview', label: 'Сводка', icon: <Gauge className="h-4 w-4" /> },
  { id: 'funnel', label: 'Воронка', icon: <GitBranch className="h-4 w-4" /> },
  { id: 'contracts', label: 'Договоры', icon: <ShieldCheck className="h-4 w-4" /> },
  { id: 'telegram', label: 'Telegram', icon: <Send className="h-4 w-4" /> },
  { id: 'sources', label: 'Источники', icon: <Globe className="h-4 w-4" /> },
  { id: 'retention', label: 'Возвраты', icon: <Users className="h-4 w-4" /> },
  { id: 'recommendations', label: 'AI-рекомендации', icon: <Brain className="h-4 w-4" /> },
];

const periodOptions = [
  { value: 1, label: 'Сегодня' },
  { value: 7, label: '7 дней' },
  { value: 30, label: '30 дней' },
  { value: 90, label: '90 дней' },
];

const modelOptions = [
  { value: 'compact', label: 'Быстро' },
  { value: 'balanced', label: 'Баланс' },
  { value: 'deep', label: 'Глубоко' },
];

const chartColors = ['#f59e0b', '#22c55e', '#38bdf8', '#f97316', '#a78bfa', '#ef4444'];

const priorityStyles: Record<Priority, string> = {
  critical: 'border-red-500/30 bg-red-500/10 text-red-200',
  high: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
  medium: 'border-sky-500/30 bg-sky-500/10 text-sky-200',
  low: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
};

const priorityLabels: Record<Priority, string> = {
  critical: 'Критично',
  high: 'Высоко',
  medium: 'Средне',
  low: 'Низко',
};

function formatNumber(value: unknown): string {
  const parsed = Number(value ?? 0);
  if (!Number.isFinite(parsed)) {
    return '0';
  }
  return parsed.toLocaleString('ru-RU');
}

function formatDate(value?: string | null): string {
  if (!value) {
    return 'нет данных';
  }
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    return value;
  }
  return new Date(timestamp).toLocaleString('ru-RU');
}

function rateLabel(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return 'нет базы';
  }
  return `${Number(value).toLocaleString('ru-RU')}%`;
}

function Section({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-700/60 bg-slate-800/50 p-5">
      <h3 className="mb-4 flex items-center gap-2 text-base font-semibold text-white">
        <span className="text-amber-400">{icon}</span>
        {title}
      </h3>
      {children}
    </section>
  );
}

function MetricCard({
  label,
  value,
  detail,
  tone = 'neutral',
}: {
  label: string;
  value: string | number;
  detail?: string;
  tone?: 'neutral' | 'good' | 'warn' | 'bad';
}) {
  const toneClass = {
    neutral: 'text-white',
    good: 'text-emerald-300',
    warn: 'text-amber-300',
    bad: 'text-red-300',
  }[tone];
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/60 p-4">
      <div className="text-sm text-slate-400">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${toneClass}`}>{value}</div>
      {detail && <div className="mt-2 text-xs text-slate-500">{detail}</div>}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-lg bg-slate-800/60 p-4 text-sm text-slate-500">{text}</div>;
}

function SmallList({ rows, labelKey = 'label' }: { rows: any[]; labelKey?: string }) {
  if (!rows?.length) {
    return <EmptyState text="Нет данных за выбранный период" />;
  }
  return (
    <div className="space-y-2">
      {rows.slice(0, 8).map((row, index) => (
        <div key={`${row[labelKey] || row.name || index}`} className="flex items-center justify-between gap-3 rounded-lg bg-slate-800/60 p-3 text-sm">
          <span className="min-w-0 truncate text-slate-200">{row[labelKey] || row.name || 'не указано'}</span>
          <span className="font-semibold text-amber-300">{formatNumber(row.count ?? row.percentage)}</span>
        </div>
      ))}
    </div>
  );
}

function RecentPosts({ rows }: { rows: any[] }) {
  if (!rows?.length) {
    return <EmptyState text="Нет публикаций в этом статусе" />;
  }
  return (
    <div className="space-y-2">
      {rows.slice(0, 6).map((row) => (
        <div key={row.id} className="rounded-lg bg-slate-800/60 p-3">
          <div className="truncate text-sm font-medium text-slate-100">{row.title || 'Без заголовка'}</div>
          <div className="mt-1 text-xs text-slate-500">{formatDate(row.publish_at || row.posted_at)}</div>
          {row.last_error && <div className="mt-2 text-xs text-red-300">{String(row.last_error).slice(0, 180)}</div>}
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPanel() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('overview');
  const [periodDays, setPeriodDays] = useState(7);
  const [model, setModel] = useState('balanced');
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');

  const loadData = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetch(`/api/admin/analytics?days=${periodDays}`, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || 'Не удалось загрузить аналитику');
      }
      setData(payload);
      setRecommendations(payload.recommendations || []);
    } catch (err: any) {
      setError(err?.message || 'Не удалось загрузить аналитику');
    } finally {
      setIsLoading(false);
    }
  };

  const generateRecommendations = async () => {
    setIsGenerating(true);
    setError('');
    try {
      const response = await fetch('/api/admin/analytics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days: periodDays, model }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || 'Не удалось сформировать рекомендации');
      }
      setRecommendations(payload.recommendations || []);
    } catch (err: any) {
      setError(err?.message || 'Не удалось сформировать рекомендации');
    } finally {
      setIsGenerating(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [periodDays]);

  const funnelChartData = useMemo(() => {
    return (data?.lead_funnel.stages || []).map((stage) => ({
      name: stage.title,
      value: stage.count,
      fromStart: stage.fromStartPct || 0,
    }));
  }, [data]);

  const statusRows = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.lead_funnel.by_status).map(([name, count]) => ({ name, count }));
  }, [data]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-700/60 bg-slate-800/50 p-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-xs font-semibold text-amber-200">
              <BarChart3 className="h-4 w-4" />
              Аналитика системы
            </span>
            <span className="text-sm text-slate-400">
              Обновлено: {data ? formatDate(data.generated_at) : 'не загружено'}
            </span>
          </div>
          <div className="mt-2 text-sm text-slate-500">
            Данные берутся из Core API, miniapp events, публикаций, договоров и веб-счетчиков.
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2">
            <Filter className="h-4 w-4 text-slate-400" />
            <select
              value={periodDays}
              onChange={(event) => setPeriodDays(Number(event.target.value))}
              className="bg-transparent text-sm text-slate-200 outline-none"
            >
              {periodOptions.map((option) => (
                <option key={option.value} value={option.value} className="bg-slate-800">
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={loadData}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {data?.source_health.errors?.length ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          Часть источников недоступна: {data.source_health.errors.slice(0, 3).join('; ')}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2 border-b border-slate-800">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`inline-flex items-center gap-2 rounded-t-lg px-4 py-3 text-sm transition-colors ${
              activeTab === tab.id
                ? 'border-b-2 border-amber-500 bg-slate-800 text-amber-300'
                : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {!data && isLoading && (
        <div className="flex items-center justify-center py-16 text-slate-400">
          <RefreshCw className="mr-3 h-6 w-6 animate-spin text-amber-400" />
          Загружаю аналитику...
        </div>
      )}

      {data && activeTab === 'overview' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Посещения сайта" value={formatNumber(data.overview.site_visits)} detail={data.site.configured ? data.site.sources.join(', ') : 'веб-счетчик не настроен'} />
            <MetricCard label="Mini App пользователи" value={formatNumber(data.overview.miniapp_users)} detail={`за ${data.period.label}`} tone="good" />
            <MetricCard label="Лид-интенты" value={formatNumber(data.overview.lead_intent_users)} detail={`CTA: ${formatNumber(data.overview.cta_users)}`} tone="warn" />
            <MetricCard label="Выигранные лиды" value={formatNumber(data.overview.won_leads)} detail={`всего лидов: ${formatNumber(data.overview.total_leads)}`} tone="good" />
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
            <Section title="Главная воронка" icon={<GitBranch className="h-5 w-5" />}>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={funnelChartData} layout="vertical" margin={{ left: 24, right: 24 }}>
                    <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
                    <XAxis type="number" stroke="#94a3b8" />
                    <YAxis type="category" dataKey="name" stroke="#94a3b8" width={140} tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }} />
                    <Bar dataKey="value" fill="#f59e0b" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Section>

            <Section title="Статусы лидов" icon={<Target className="h-5 w-5" />}>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={statusRows} dataKey="count" nameKey="name" innerRadius={48} outerRadius={94} paddingAngle={3}>
                      {statusRows.map((_, index) => (
                        <Cell key={index} fill={chartColors[index % chartColors.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Section>

            <Section title="Что требует внимания" icon={<AlertCircle className="h-5 w-5" />}>
              <div className="space-y-3">
                {recommendations.slice(0, 4).map((item) => (
                  <div key={item.id} className={`rounded-lg border p-3 ${priorityStyles[item.priority]}`}>
                    <div className="text-sm font-semibold">{item.title}</div>
                    {item.metric && <div className="mt-1 text-xs opacity-80">{item.metric}</div>}
                  </div>
                ))}
              </div>
            </Section>
          </div>
        </div>
      )}

      {data && activeTab === 'funnel' && (
        <div className="space-y-5">
          <Section title="Этапы воронки" icon={<GitBranch className="h-5 w-5" />}>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="text-left text-slate-400">
                  <tr>
                    <th className="px-3 py-2">Этап</th>
                    <th className="px-3 py-2">Количество</th>
                    <th className="px-3 py-2">От предыдущего</th>
                    <th className="px-3 py-2">От начала</th>
                  </tr>
                </thead>
                <tbody>
                  {data.lead_funnel.stages.map((stage) => (
                    <tr key={stage.key} className="border-t border-slate-800">
                      <td className="px-3 py-3 text-slate-100">{stage.title}</td>
                      <td className="px-3 py-3 font-semibold text-white">{formatNumber(stage.count)}</td>
                      <td className="px-3 py-3 text-slate-300">{rateLabel(stage.fromPreviousPct)}</td>
                      <td className="px-3 py-3 text-slate-300">{rateLabel(stage.fromStartPct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
            <Section title="Температура" icon={<TrendingUp className="h-5 w-5" />}>
              <SmallList rows={Object.entries(data.lead_funnel.by_temperature).map(([name, count]) => ({ name, count }))} labelKey="name" />
            </Section>
            <Section title="Стадии диалога" icon={<Activity className="h-5 w-5" />}>
              <SmallList rows={Object.entries(data.lead_funnel.by_stage).map(([name, count]) => ({ name, count }))} labelKey="name" />
            </Section>
            <Section title="Последние лиды" icon={<ClipboardList className="h-5 w-5" />}>
              <div className="space-y-2">
                {data.lead_funnel.recent_leads.slice(0, 6).map((lead) => (
                  <div key={lead.id} className="rounded-lg bg-slate-800/60 p-3 text-sm">
                    <div className="truncate font-medium text-slate-100">{lead.name || lead.contact || 'Без имени'}</div>
                    <div className="mt-1 text-xs text-slate-500">{lead.source || 'источник не указан'} · {lead.status || 'new'}</div>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        </div>
      )}

      {data && activeTab === 'contracts' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Всего заданий" value={formatNumber(data.contracts.summary.total)} />
            <MetricCard label="Готово за период" value={formatNumber(data.contracts.summary.done_last_hours_count)} tone="good" />
            <MetricCard label="Зависли в обработке" value={formatNumber(data.contracts.summary.processing_stale_count)} tone={data.contracts.summary.processing_stale_count ? 'bad' : 'good'} />
            <MetricCard label="Ошибки с retry" value={formatNumber(data.contracts.summary.failed_retryable_count)} tone={data.contracts.summary.failed_retryable_count ? 'warn' : 'good'} />
          </div>
          <Section title="Статусы Contract AI" icon={<ShieldCheck className="h-5 w-5" />}>
            <SmallList rows={Object.entries(data.contracts.summary.by_status || {}).map(([name, count]) => ({ name, count }))} labelKey="name" />
          </Section>
        </div>
      )}

      {data && activeTab === 'telegram' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Reader signals" value={formatNumber(data.telegram.reader_summary?.stats?.signals_total)} />
            <MetricCard label="Идеи запрошены" value={formatNumber(data.telegram.reader_summary?.stats?.idea_requested)} tone="good" />
            <MetricCard label="Намерение консультации" value={formatNumber(data.telegram.reader_summary?.stats?.consultation_intent)} tone="warn" />
            <MetricCard label="Ошибки публикаций" value={formatNumber(data.telegram.publications.counts.failed)} tone={data.telegram.publications.counts.failed ? 'bad' : 'good'} />
            <MetricCard label="Архив cleanup" value={formatNumber(data.telegram.publications.archived_cleanup_count || 0)} />
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <Section title="Очередь публикаций" icon={<FileText className="h-5 w-5" />}>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <RecentPosts rows={data.telegram.publications.review} />
                <RecentPosts rows={data.telegram.publications.failed} />
              </div>
            </Section>
            <Section title="A/B варианты CTA" icon={<Target className="h-5 w-5" />}>
              <SmallList rows={data.telegram.reader_conversion?.variants || []} labelKey="cta_variant" />
            </Section>
          </div>
        </div>
      )}

      {data && activeTab === 'sources' && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <Section title="Трафик сайта" icon={<Globe className="h-5 w-5" />}>
            <SmallList rows={data.sources.site_traffic.map((row) => ({ name: row.name, count: `${row.percentage}%` }))} labelKey="name" />
          </Section>
          <Section title="Источники лидов" icon={<Users className="h-5 w-5" />}>
            <SmallList rows={data.sources.lead_sources} labelKey="name" />
          </Section>
          <Section title="Источники Mini App" icon={<Activity className="h-5 w-5" />}>
            <SmallList rows={data.sources.miniapp_sources} />
          </Section>
          <Section title="Источники лид-интента" icon={<TrendingDown className="h-5 w-5" />}>
            <SmallList rows={data.sources.intent_sources} />
          </Section>
        </div>
      )}

      {data && activeTab === 'retention' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <MetricCard label="Уникальные пользователи" value={formatNumber(data.retention.unique_users_total)} />
            <MetricCard label="События Mini App" value={formatNumber(data.retention.total_events)} />
            <MetricCard label="Пользователи Mini App" value={formatNumber(data.retention.miniapp_unique_users)} />
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <Section title="Топ действий" icon={<Activity className="h-5 w-5" />}>
              <SmallList rows={data.retention.top_actions} />
            </Section>
            <Section title="Активные пользователи" icon={<Users className="h-5 w-5" />}>
              <SmallList rows={data.retention.top_users.map((row) => ({ label: String(row.telegram_user_id), count: row.count }))} />
            </Section>
          </div>
        </div>
      )}

      {data && activeTab === 'recommendations' && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-700/60 bg-slate-800/50 p-4">
            <div>
              <div className="text-base font-semibold text-white">AI-рекомендации по улучшению</div>
              <div className="mt-1 text-sm text-slate-500">Рекомендации строятся на текущих метриках, без ручного ввода.</div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={model}
                onChange={(event) => setModel(event.target.value)}
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none"
              >
                {modelOptions.map((option) => (
                  <option key={option.value} value={option.value} className="bg-slate-800">
                    {option.label}
                  </option>
                ))}
              </select>
              <button
                onClick={generateRecommendations}
                disabled={isGenerating}
                className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Brain className={`h-4 w-4 ${isGenerating ? 'animate-pulse' : ''}`} />
                Сформировать
              </button>
            </div>
          </div>

          <div className="space-y-3">
            {recommendations.map((item) => (
              <div key={item.id} className={`rounded-lg border p-4 ${priorityStyles[item.priority]}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="font-semibold">{item.title}</div>
                  <span className="rounded-md border border-current/30 px-2 py-1 text-xs">{priorityLabels[item.priority]} · {item.area}</span>
                </div>
                <div className="mt-3 text-sm opacity-90">{item.reason}</div>
                <div className="mt-2 text-sm font-medium">{item.action}</div>
                {item.metric && <div className="mt-2 text-xs opacity-75">{item.metric}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
