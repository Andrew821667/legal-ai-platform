'use client';

import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Activity,
  AlertCircle,
  Bot,
  CheckCircle2,
  Clock,
  Database,
  FileText,
  Globe,
  RefreshCw,
  Server,
  ShieldCheck,
  Smartphone,
  XCircle,
} from 'lucide-react';

type MonitorStatus = 'ok' | 'warn' | 'error' | 'unknown';

type EndpointCheck = {
  name: string;
  status: MonitorStatus;
  url?: string;
  statusCode?: number;
  latencyMs?: number;
  detail?: string;
};

type MonitorData = {
  generated_at: string;
  status: MonitorStatus;
  issues: string[];
  core: {
    base_url: string;
    health: { ok: boolean; status: number; latencyMs: number; data?: any; error?: string };
    detailed_health: { ok: boolean; status: number; latencyMs: number; data?: any; error?: string };
  };
  workers: {
    any_active?: boolean;
    workers?: Array<{
      worker_id: string;
      active: boolean;
      last_seen_at: string;
      info?: Record<string, any> | null;
    }>;
  };
  contracts: {
    summary?: Record<string, any> | null;
  };
  publications: {
    counts: Record<string, number>;
    due_count: number;
    stale_publishing_count: number;
    review: any[];
    scheduled: any[];
    failed: any[];
    recent_posted: any[];
  };
  reader: {
    funnel?: Record<string, any> | null;
    summary?: Record<string, any> | null;
  };
  endpoints: EndpointCheck[];
  raw: Record<string, any>;
};

type MonitorTab = 'overview' | 'bots' | 'publications' | 'site' | 'contracts' | 'raw';

const statusStyles: Record<MonitorStatus, string> = {
  ok: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
  warn: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  error: 'border-red-500/30 bg-red-500/10 text-red-300',
  unknown: 'border-slate-600 bg-slate-800 text-slate-300',
};

const workerLabels: Record<string, string> = {
  'news-generate': 'Генератор постов',
  'news-telegram-ingest': 'Сбор новостей',
  'news-publish': 'Публикатор канала',
  'news-reader-digest': 'Reader digest',
};

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

function relativeMinutes(value?: string | null): string {
  if (!value) {
    return 'нет heartbeat';
  }
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    return value;
  }
  const minutes = Math.max(0, Math.round((Date.now() - timestamp) / 60_000));
  if (minutes < 1) {
    return 'только что';
  }
  return `${minutes} мин назад`;
}

function statusIcon(status: MonitorStatus) {
  if (status === 'ok') {
    return <CheckCircle2 className="h-4 w-4" />;
  }
  if (status === 'error') {
    return <XCircle className="h-4 w-4" />;
  }
  return <AlertCircle className="h-4 w-4" />;
}

function StatusPill({ status, label }: { status: MonitorStatus; label?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold ${statusStyles[status]}`}>
      {statusIcon(status)}
      {label || status.toUpperCase()}
    </span>
  );
}

function MetricCard({
  label,
  value,
  detail,
  status = 'unknown',
}: {
  label: string;
  value: string | number;
  detail?: string;
  status?: MonitorStatus;
}) {
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-900/60 p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-sm text-slate-400">{label}</div>
        <StatusPill status={status} label={status === 'ok' ? 'OK' : status === 'warn' ? 'WARN' : status === 'error' ? 'FAIL' : 'INFO'} />
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {detail && <div className="mt-2 text-xs text-slate-500">{detail}</div>}
    </div>
  );
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

function PostList({ rows }: { rows: any[] }) {
  if (!rows?.length) {
    return <div className="rounded-lg bg-slate-900/60 p-4 text-sm text-slate-500">Нет записей</div>;
  }
  return (
    <div className="space-y-2">
      {rows.map((row) => (
        <div key={row.id} className="rounded-lg bg-slate-900/60 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0 flex-1 truncate text-sm font-medium text-slate-100">{row.title || 'Без заголовка'}</div>
            <StatusPill status={row.status === 'failed' ? 'error' : row.status === 'posted' ? 'ok' : 'unknown'} label={row.status || 'unknown'} />
          </div>
          <div className="mt-1 text-xs text-slate-500">Публикация: {formatDate(row.publish_at)}</div>
          {row.last_error && <div className="mt-2 line-clamp-2 text-xs text-red-300">{row.last_error}</div>}
        </div>
      ))}
    </div>
  );
}

export default function SystemMonitorPanel() {
  const [data, setData] = useState<MonitorData | null>(null);
  const [activeTab, setActiveTab] = useState<MonitorTab>('overview');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const loadData = async () => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetch('/api/admin/system-monitor', { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.detail || 'Не удалось загрузить мониторинг');
      }
      setData(payload);
    } catch (err: any) {
      setError(err?.message || 'Не удалось загрузить мониторинг');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
    const timer = window.setInterval(() => {
      void loadData();
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const workerRows = data?.workers?.workers || [];
  const activeWorkers = workerRows.filter((worker) => worker.active).length;
  const endpointErrors = data?.endpoints?.filter((endpoint) => endpoint.status === 'error').length || 0;
  const contractSummary = data?.contracts?.summary || {};
  const readerFunnel = data?.reader?.funnel || {};
  const tabs: Array<{ id: MonitorTab; label: string; icon: ReactNode }> = [
    { id: 'overview', label: 'Сводка', icon: <Activity className="h-4 w-4" /> },
    { id: 'bots', label: 'Боты и воркеры', icon: <Bot className="h-4 w-4" /> },
    { id: 'publications', label: 'Публикации', icon: <FileText className="h-4 w-4" /> },
    { id: 'site', label: 'Сайт и Mini App', icon: <Globe className="h-4 w-4" /> },
    { id: 'contracts', label: 'Contract AI', icon: <ShieldCheck className="h-4 w-4" /> },
    { id: 'raw', label: 'Raw', icon: <Database className="h-4 w-4" /> },
  ];

  const overallStatus = useMemo<MonitorStatus>(() => {
    if (!data) {
      return 'unknown';
    }
    return data.status || 'unknown';
  }, [data]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-700/60 bg-slate-800/50 p-4">
        <div>
          <div className="flex items-center gap-3">
            <StatusPill status={overallStatus} label={overallStatus === 'ok' ? 'Система OK' : overallStatus === 'warn' ? 'Есть предупреждения' : overallStatus === 'error' ? 'Есть сбои' : 'Нет данных'} />
            <span className="text-sm text-slate-400">
              Обновлено: {data ? formatDate(data.generated_at) : 'не загружено'}
            </span>
          </div>
          {data?.issues?.length ? (
            <div className="mt-2 text-sm text-amber-200">{data.issues.slice(0, 4).join(', ')}</div>
          ) : (
            <div className="mt-2 text-sm text-slate-500">Автообновление раз в 60 секунд</div>
          )}
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

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

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
          Загружаю состояние системы...
        </div>
      )}

      {data && activeTab === 'overview' && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Core API"
              value={data.core.health.ok ? 'доступен' : 'недоступен'}
              detail={`${data.core.health.status || 'нет HTTP'} | ${data.core.health.latencyMs || 0} ms`}
              status={data.core.health.ok ? 'ok' : 'error'}
            />
            <MetricCard
              label="News workers"
              value={`${activeWorkers}/${workerRows.length}`}
              detail="активные heartbeat-процессы"
              status={activeWorkers === workerRows.length && workerRows.length > 0 ? 'ok' : 'warn'}
            />
            <MetricCard
              label="Due publications"
              value={data.publications.due_count}
              detail={`scheduled: ${data.publications.counts.scheduled || 0}, review: ${data.publications.counts.review || 0}`}
              status={data.publications.due_count > 0 ? 'warn' : 'ok'}
            />
            <MetricCard
              label="Endpoint errors"
              value={endpointErrors}
              detail="сайт, miniapp, Telegram TLS, Contract AI"
              status={endpointErrors > 0 ? 'error' : 'ok'}
            />
          </div>

          <Section title="Проверки доступа" icon={<Globe className="h-5 w-5" />}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {data.endpoints.map((endpoint) => (
                <div key={endpoint.name} className="rounded-lg bg-slate-900/60 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-slate-100">{endpoint.name}</div>
                    <StatusPill status={endpoint.status} label={endpoint.status.toUpperCase()} />
                  </div>
                  <div className="mt-1 truncate text-xs text-slate-500">{endpoint.url}</div>
                  <div className="mt-2 text-xs text-slate-400">
                    {endpoint.statusCode ? `HTTP ${endpoint.statusCode}` : endpoint.detail || 'TLS'} | {endpoint.latencyMs || 0} ms
                  </div>
                </div>
              ))}
            </div>
          </Section>
        </div>
      )}

      {data && activeTab === 'bots' && (
        <Section title="Боты и фоновые сервисы" icon={<Bot className="h-5 w-5" />}>
          <div className="space-y-3">
            {workerRows.map((worker) => (
              <div key={worker.worker_id} className="rounded-lg bg-slate-900/60 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-semibold text-white">{workerLabels[worker.worker_id] || worker.worker_id}</div>
                    <div className="text-xs text-slate-500">{worker.worker_id}</div>
                  </div>
                  <StatusPill status={worker.active ? 'ok' : 'error'} label={worker.active ? 'active' : 'inactive'} />
                </div>
                <div className="mt-3 grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
                  <div className="text-slate-400">Last seen: <span className="text-slate-200">{relativeMinutes(worker.last_seen_at)}</span></div>
                  <div className="text-slate-400">Action: <span className="text-slate-200">{worker.info?.action || 'нет'}</span></div>
                  <div className="text-slate-400">Busy: <span className="text-slate-200">{String(worker.info?.busy ?? false)}</span></div>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {data && activeTab === 'publications' && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <Section title="На проверке" icon={<Clock className="h-5 w-5" />}>
            <PostList rows={data.publications.review} />
          </Section>
          <Section title="На публикацию" icon={<FileText className="h-5 w-5" />}>
            <PostList rows={data.publications.scheduled} />
          </Section>
          <Section title="Ошибки публикации" icon={<AlertCircle className="h-5 w-5" />}>
            <PostList rows={data.publications.failed} />
          </Section>
          <Section title="Недавно опубликовано" icon={<CheckCircle2 className="h-5 w-5" />}>
            <PostList rows={data.publications.recent_posted} />
          </Section>
        </div>
      )}

      {data && activeTab === 'site' && (
        <div className="space-y-5">
          <Section title="Сайт, Mini App и внешние переходы" icon={<Smartphone className="h-5 w-5" />}>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {data.endpoints.map((endpoint) => (
                <div key={endpoint.name} className="rounded-lg bg-slate-900/60 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-white">{endpoint.name}</div>
                    <StatusPill status={endpoint.status} />
                  </div>
                  <div className="mt-2 break-all text-xs text-slate-500">{endpoint.url}</div>
                  <div className="mt-3 text-sm text-slate-300">
                    {endpoint.statusCode ? `HTTP ${endpoint.statusCode}` : endpoint.detail || 'проверка TLS'} за {endpoint.latencyMs || 0} ms
                  </div>
                </div>
              ))}
            </div>
          </Section>

          <Section title="Reader funnel за 7 дней" icon={<Activity className="h-5 w-5" />}>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <MetricCard label="Открытия weekly" value={readerFunnel.feedback?.weekly_opened || 0} status="unknown" />
              <MetricCard label="Запросы идей" value={readerFunnel.feedback?.idea_requested || 0} status="unknown" />
              <MetricCard label="Намерение консультации" value={readerFunnel.feedback?.consultation_intent || 0} status="unknown" />
            </div>
          </Section>
        </div>
      )}

      {data && activeTab === 'contracts' && (
        <Section title="Contract AI queue" icon={<ShieldCheck className="h-5 w-5" />}>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="New retryable" value={contractSummary.new_retryable_count ?? contractSummary.by_status?.new ?? 0} status="unknown" />
            <MetricCard label="Processing stale" value={contractSummary.processing_stale_count || 0} status={contractSummary.processing_stale_count ? 'warn' : 'ok'} />
            <MetricCard label="Failed retryable" value={contractSummary.failed_retryable_count || 0} status={contractSummary.failed_retryable_count ? 'warn' : 'ok'} />
            <MetricCard label="Workers active" value={data.workers.any_active ? 'yes' : 'no'} status={data.workers.any_active ? 'ok' : 'warn'} />
          </div>
          <pre className="mt-5 max-h-96 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-300">
            {JSON.stringify(contractSummary, null, 2)}
          </pre>
        </Section>
      )}

      {data && activeTab === 'raw' && (
        <Section title="Raw payload" icon={<Server className="h-5 w-5" />}>
          <pre className="max-h-[560px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-300">
            {JSON.stringify(data, null, 2)}
          </pre>
        </Section>
      )}
    </div>
  );
}
