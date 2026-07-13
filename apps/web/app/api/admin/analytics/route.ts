import { NextRequest, NextResponse } from "next/server";

import { requireAdminSession } from "@/lib/admin-session";
import { loadGoogleAnalyticsPayload, type GA4MetricData } from "@/lib/analytics/google";
import { loadYandexAnalyticsPayload } from "@/lib/analytics/yandex";

export const runtime = "nodejs";

const CORE_API_URL = process.env.CORE_API_URL || process.env.NEXT_PUBLIC_CORE_API_URL || "http://localhost:8000";
const CORE_API_ADMIN_KEY = process.env.CORE_API_ADMIN_KEY || process.env.API_KEY_ADMIN || "";
const ARCHIVED_PUBLICATION_ERROR_PREFIXES = [
  "deleted_irrelevant",
  "expired_review_cleanup",
  "expired_editorial_cleanup",
  "expired_weekly_review_cleanup",
];

type RecommendationPriority = "critical" | "high" | "medium" | "low";

type Recommendation = {
  id: string;
  priority: RecommendationPriority;
  area: string;
  title: string;
  reason: string;
  action: string;
  metric?: string;
};

type CoreJsonResult = {
  ok: boolean;
  status: number;
  data: any;
  error?: string;
};

type LeadFunnelStage = {
  key: string;
  title: string;
  count: number;
  fromPreviousPct: number | null;
  fromStartPct: number | null;
};

const emptySiteAnalytics: GA4MetricData = {
  today: { visits: 0, pageviews: 0, uniqueVisitors: 0, bounceRate: 0, avgDuration: "0:00", conversions: 0 },
  week: { visits: 0, pageviews: 0, uniqueVisitors: 0, bounceRate: 0, avgDuration: "0:00", conversions: 0 },
  month: { visits: 0, pageviews: 0, uniqueVisitors: 0, bounceRate: 0, avgDuration: "0:00", conversions: 0 },
  topPages: [],
  sources: [],
};

function clampDays(raw: string | null): number {
  const parsed = Number(raw || "7");
  if (!Number.isFinite(parsed)) {
    return 7;
  }
  return Math.max(1, Math.min(90, Math.round(parsed)));
}

function numberValue(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function percent(numerator: number, denominator: number): number | null {
  if (denominator <= 0) {
    return null;
  }
  return Math.round((numerator / denominator) * 1000) / 10;
}

function periodSiteMetrics(site: GA4MetricData, days: number) {
  if (days <= 1) {
    return site.today;
  }
  if (days <= 7) {
    return site.week;
  }
  return site.month;
}

function isArchivedPublicationFailure(row: any): boolean {
  const lastError = String(row?.last_error || "").trim().toLowerCase();
  return ARCHIVED_PUBLICATION_ERROR_PREFIXES.some((prefix) => lastError.startsWith(prefix));
}

async function fetchCoreJson(path: string): Promise<CoreJsonResult> {
  const response = await fetch(`${CORE_API_URL.replace(/\/+$/, "")}${path}`, {
    headers: {
      "X-API-Key": CORE_API_ADMIN_KEY,
      "Content-Type": "application/json",
    },
    cache: "no-store",
    signal: AbortSignal.timeout(8_000),
  });
  const raw = await response.text();
  let data: any = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = raw ? { detail: raw } : {};
  }
  return { ok: response.ok, status: response.status, data };
}

async function safeCoreJson(path: string): Promise<CoreJsonResult> {
  try {
    return await fetchCoreJson(path);
  } catch (error: any) {
    return {
      ok: false,
      status: 0,
      data: null,
      error: error?.message || "Core API request failed",
    };
  }
}

async function loadSiteAnalytics() {
  const [ga4Response, yandexResponse] = await Promise.allSettled([
    loadGoogleAnalyticsPayload(),
    loadYandexAnalyticsPayload(),
  ]);
  const ga4 = ga4Response.status === "fulfilled" ? ga4Response.value : null;
  const yandex = yandexResponse.status === "fulfilled" ? yandexResponse.value : null;
  const sources: string[] = [];
  if (yandex?.configured && yandex.success) {
    sources.push("Yandex Metrika");
  }
  if (ga4?.configured && ga4.success) {
    sources.push("Google Analytics 4");
  }

  const primary = yandex?.configured && yandex.success ? yandex.data : ga4?.configured && ga4.success ? ga4.data : emptySiteAnalytics;
  return {
    configured: sources.length > 0,
    sources,
    data: primary || emptySiteAnalytics,
    raw: { ga4, yandex },
  };
}

function countBy(rows: any[], field: string): Array<{ name: string; count: number }> {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const value = String(row?.[field] || "не указано").trim() || "не указано";
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
    .slice(0, 12);
}

function buildFunnel(input: {
  siteVisits: number;
  miniappUsers: number;
  ctaUsers: number;
  leadIntentUsers: number;
  readerReferralLeads: number;
  totalLeads: number;
  qualifiedLeads: number;
  bookedLeads: number;
  wonLeads: number;
}): LeadFunnelStage[] {
  const raw: Array<{ key: string; title: string; count: number }> = [
    { key: "site_visits", title: "Посещения сайта", count: input.siteVisits },
    { key: "miniapp_active", title: "Mini App активные", count: input.miniappUsers },
    { key: "cta_click", title: "Нажали CTA", count: input.ctaUsers },
    { key: "lead_intent", title: "Показали лид-интент", count: input.leadIntentUsers },
    { key: "reader_referral", title: "Лиды из reader", count: input.readerReferralLeads },
    { key: "total_leads", title: "Все лиды в CRM", count: input.totalLeads },
    { key: "qualified", title: "Квалифицированы", count: input.qualifiedLeads },
    { key: "booked", title: "Встречи/заявки в работе", count: input.bookedLeads },
    { key: "won", title: "Выиграны", count: input.wonLeads },
  ];
  const firstPositive = raw.find((stage) => stage.count > 0)?.count || 0;
  return raw.map((stage, index) => {
    const previous = index > 0 ? raw[index - 1]?.count || 0 : 0;
    return {
      ...stage,
      fromPreviousPct: index === 0 ? null : percent(stage.count, previous),
      fromStartPct: percent(stage.count, firstPositive),
    };
  });
}

function addRecommendation(rows: Recommendation[], item: Recommendation): void {
  if (rows.some((row) => row.id === item.id)) {
    return;
  }
  rows.push(item);
}

function priorityRank(priority: RecommendationPriority): number {
  return { critical: 0, high: 1, medium: 2, low: 3 }[priority];
}

function buildRecommendations(analytics: any, model: string): Recommendation[] {
  const rows: Recommendation[] = [];
  const rates = analytics?.lead_funnel?.rates || {};
  const overview = analytics?.overview || {};
  const contracts = analytics?.contracts?.summary || {};
  const publications = analytics?.telegram?.publications || {};
  const readerSummary = analytics?.telegram?.reader_summary || {};
  const negativeReasons = Array.isArray(readerSummary?.top_negative_reasons) ? readerSummary.top_negative_reasons : [];

  if (!analytics?.site?.configured) {
    addRecommendation(rows, {
      id: "connect-web-analytics",
      priority: "high",
      area: "Сайт",
      title: "Подключить источник веб-аналитики",
      reason: "Воронка видит внутренние события, но не видит полноценный верхний слой трафика сайта.",
      action: "Настроить Yandex Metrika или Google Analytics 4 в окружении web-сервиса и проверить сбор top pages/source.",
      metric: "site analytics: не настроена",
    });
  }

  if (numberValue(rates.miniapp_to_cta) > 0 && numberValue(rates.miniapp_to_cta) < 12) {
    addRecommendation(rows, {
      id: "miniapp-cta-drop",
      priority: "high",
      area: "Mini App",
      title: "Усилить первый CTA в Mini App",
      reason: "Пользователи открывают Mini App, но редко доходят до целевого клика.",
      action: "Сделать главный CTA более конкретным: диагностика договора, консультация или чек-лист, и закрепить его в ключевых экранах.",
      metric: `Mini App -> CTA: ${rates.miniapp_to_cta}%`,
    });
  }

  if (numberValue(rates.cta_to_intent) > 0 && numberValue(rates.cta_to_intent) < 25) {
    addRecommendation(rows, {
      id: "cta-intent-drop",
      priority: "high",
      area: "Воронка",
      title: "Сократить шаг между CTA и заявкой",
      reason: "После клика часть пользователей не подтверждает намерение обратиться.",
      action: "Уменьшить количество полей, добавить предзаполнение из Telegram и показать понятное обещание результата.",
      metric: `CTA -> лид-интент: ${rates.cta_to_intent}%`,
    });
  }

  if (numberValue(publications.counts?.failed) > 0) {
    addRecommendation(rows, {
      id: "publication-failures",
      priority: "critical",
      area: "Telegram",
      title: "Разобрать ошибки публикаций",
      reason: "В очереди есть неуспешные публикации, это напрямую влияет на регулярность канала.",
      action: "Открыть System Monitor -> Публикации, проверить last_error и перезапустить только проблемные элементы после исправления причины.",
      metric: `Ошибки публикации: ${publications.counts.failed}`,
    });
  }

  if (numberValue(contracts.processing_stale_count) > 0 || numberValue(contracts.failed_retryable_count) > 0) {
    addRecommendation(rows, {
      id: "contract-ops-backlog",
      priority: "critical",
      area: "Contract AI",
      title: "Очистить очередь зависших договоров",
      reason: "Есть зависшие или повторяемые задания анализа договоров.",
      action: "Проверить worker, причину ошибок и выполнить retry только для retryable jobs.",
      metric: `stale: ${contracts.processing_stale_count || 0}, retryable failed: ${contracts.failed_retryable_count || 0}`,
    });
  }

  if (overview.total_leads > 0 && numberValue(overview.qualified_leads) / Math.max(numberValue(overview.total_leads), 1) < 0.15) {
    addRecommendation(rows, {
      id: "lead-qualification",
      priority: "medium",
      area: "Лиды",
      title: "Усилить квалификацию лидов",
      reason: "Доля квалифицированных лидов относительно всей базы выглядит низкой.",
      action: "Добавить в форме или боте 1-2 вопроса о типе задачи, сроке и бюджете, затем использовать это для приоритизации менеджера.",
      metric: `Квалифицированы: ${overview.qualified_leads}/${overview.total_leads}`,
    });
  }

  if (negativeReasons.length > 0) {
    const topReason = negativeReasons[0];
    addRecommendation(rows, {
      id: "reader-negative-feedback",
      priority: "medium",
      area: "Контент",
      title: "Использовать негативный feedback reader-бота",
      reason: "Читатели уже дают сигналы, почему материал не сработал.",
      action: "Собрать топ причин за период и скорректировать промпт генерации: меньше нерелевантных тем, больше практических выводов.",
      metric: `${topReason.reason}: ${topReason.count}`,
    });
  }

  if (rows.length === 0) {
    addRecommendation(rows, {
      id: "baseline-operating-rhythm",
      priority: "low",
      area: "Операционка",
      title: "Зафиксировать регулярный обзор метрик",
      reason: "Критичных провалов по текущим данным не видно.",
      action: "Раз в неделю смотреть вкладки Воронка, Источники и Telegram, чтобы поймать просадку до того, как она станет проблемой.",
      metric: "Состояние: без явных критичных сигналов",
    });
  }

  const limit = model === "deep" ? 10 : model === "compact" ? 4 : 7;
  return rows.sort((a, b) => priorityRank(a.priority) - priorityRank(b.priority)).slice(0, limit);
}

async function buildAnalyticsForDays(days: number) {
  const hours = days * 24;

  if (!CORE_API_ADMIN_KEY) {
    throw new Error("CORE_API_ADMIN_KEY или API_KEY_ADMIN не настроен на web-сервере");
  }

  const [
    site,
    leadsStats,
    leads,
    readerConversion,
    readerEvents,
    readerFunnel,
    readerSummary,
    contractSummary,
    reviewPosts,
    scheduledPosts,
    failedPosts,
    postedPosts,
  ] = await Promise.all([
    loadSiteAnalytics(),
    safeCoreJson("/api/v1/leads/stats/summary"),
    safeCoreJson("/api/v1/leads?limit=100"),
    safeCoreJson(`/api/v1/reader/conversion-funnel?hours=${hours}`),
    safeCoreJson(`/api/v1/reader/miniapp/events/summary?hours=${Math.min(hours, 168)}`),
    safeCoreJson(`/api/v1/scheduled-posts/feedback/reader-funnel?days=${days}`),
    safeCoreJson(`/api/v1/scheduled-posts/feedback/reader-summary?days=${days}`),
    safeCoreJson(`/api/v1/contract-jobs/summary?window_hours=${Math.min(hours, 168)}&stale_minutes=30`),
    safeCoreJson("/api/v1/scheduled-posts?status=review&limit=100&newest_first=true"),
    safeCoreJson("/api/v1/scheduled-posts?status=scheduled&limit=100"),
    safeCoreJson("/api/v1/scheduled-posts?status=failed&limit=100&newest_first=true"),
    safeCoreJson("/api/v1/scheduled-posts?status=posted&limit=30&newest_first=true"),
  ]);

  const leadRows = Array.isArray(leads.data) ? leads.data : [];
  const leadsStatsData = leadsStats.data || {};
  const readerConversionData = readerConversion.data || {};
  const readerFunnelData = readerFunnel.data || {};
  const contractSummaryData = contractSummary.data || {};
  const siteMetrics = periodSiteMetrics(site.data, days);
  const stageByKey = new Map<string, number>(
    Array.isArray(readerConversionData.stages)
      ? readerConversionData.stages.map((stage: any) => [String(stage.key), numberValue(stage.users)])
      : [],
  );

  const totalLeads = numberValue(leadsStatsData.total_leads);
  const qualifiedLeads = numberValue(leadsStatsData.qualified_leads);
  const bookedLeads =
    numberValue(leadsStatsData.booked_leads) +
    numberValue(leadsStatsData.proposal_leads) +
    numberValue(leadsStatsData.won_leads);
  const wonLeads = numberValue(leadsStatsData.won_leads);
  const readerReferralLeads = numberValue(readerFunnelData.leads?.reader_referral_created);

  const funnelStages = buildFunnel({
    siteVisits: numberValue(siteMetrics.visits),
    miniappUsers: stageByKey.get("miniapp_active") || numberValue(readerEvents.data?.unique_users),
    ctaUsers: stageByKey.get("cta_click") || 0,
    leadIntentUsers: stageByKey.get("lead_intent") || 0,
    readerReferralLeads,
    totalLeads,
    qualifiedLeads,
    bookedLeads,
    wonLeads,
  });

  const rates = Object.fromEntries(
    (Array.isArray(readerConversionData.rates) ? readerConversionData.rates : []).map((rate: any) => [
      String(rate.key),
      numberValue(rate.value),
    ]),
  );

  const failedRows = Array.isArray(failedPosts.data) ? failedPosts.data : [];
  const actionableFailedRows = failedRows.filter((row: any) => !isArchivedPublicationFailure(row));
  const archivedFailedRows = failedRows.filter(isArchivedPublicationFailure);
  const publicationRows = [
    ...(Array.isArray(reviewPosts.data) ? reviewPosts.data : []),
    ...(Array.isArray(scheduledPosts.data) ? scheduledPosts.data : []),
    ...actionableFailedRows,
    ...(Array.isArray(postedPosts.data) ? postedPosts.data : []),
  ];

  const payload = {
    generated_at: new Date().toISOString(),
    period: {
      days,
      hours,
      label: days === 1 ? "сегодня" : `${days} дней`,
    },
    source_health: {
      core_api: leadsStats.ok && readerConversion.ok,
      site_analytics: site.configured,
      errors: [
        leadsStats,
        leads,
        readerConversion,
        readerEvents,
        readerFunnel,
        readerSummary,
        contractSummary,
      ]
        .filter((item) => !item.ok)
        .map((item) => item.error || item.data?.detail || `HTTP ${item.status}`),
    },
    overview: {
      site_visits: numberValue(siteMetrics.visits),
      site_unique_users: numberValue(siteMetrics.uniqueVisitors),
      miniapp_users: stageByKey.get("miniapp_active") || numberValue(readerEvents.data?.unique_users),
      cta_users: stageByKey.get("cta_click") || 0,
      lead_intent_users: stageByKey.get("lead_intent") || 0,
      total_leads: totalLeads,
      qualified_leads: qualifiedLeads,
      booked_leads: bookedLeads,
      won_leads: wonLeads,
      contract_jobs_total: numberValue(contractSummaryData.total),
      contract_done_window: numberValue(contractSummaryData.done_last_hours_count),
      failed_publications: actionableFailedRows.length,
      archived_publication_cleanups: archivedFailedRows.length,
    },
    site: {
      configured: site.configured,
      sources: site.sources,
      metrics: site.data,
      period_metrics: siteMetrics,
      top_pages: site.data.topPages || [],
      traffic_sources: site.data.sources || [],
    },
    lead_funnel: {
      stages: funnelStages,
      rates,
      by_status: {
        new: numberValue(leadsStatsData.new_leads),
        qualified: qualifiedLeads,
        booked: numberValue(leadsStatsData.booked_leads),
        proposal: numberValue(leadsStatsData.proposal_leads),
        won: wonLeads,
        lost: numberValue(leadsStatsData.lost_leads),
      },
      by_temperature: {
        hot: numberValue(leadsStatsData.hot_leads),
        warm: numberValue(leadsStatsData.warm_leads),
        cold: numberValue(leadsStatsData.cold_leads),
      },
      by_stage: {
        discover: numberValue(leadsStatsData.stage_discover),
        diagnose: numberValue(leadsStatsData.stage_diagnose),
        qualify: numberValue(leadsStatsData.stage_qualify),
        propose: numberValue(leadsStatsData.stage_propose),
        handoff: numberValue(leadsStatsData.stage_handoff),
      },
      by_source: countBy(leadRows, "source"),
      recent_leads: leadRows.slice(0, 12),
    },
    contracts: {
      summary: contractSummaryData,
      source: contractSummary.ok ? "core-api" : "unavailable",
    },
    telegram: {
      reader_conversion: readerConversionData,
      reader_events: readerEvents.data || {},
      reader_funnel: readerFunnelData,
      reader_summary: readerSummary.data || {},
      publications: {
        counts: countBy(publicationRows, "status").reduce<Record<string, number>>((acc, item) => {
          acc[item.name] = item.count;
          return acc;
        }, {}),
        review: Array.isArray(reviewPosts.data) ? reviewPosts.data.slice(0, 8) : [],
        scheduled: Array.isArray(scheduledPosts.data) ? scheduledPosts.data.slice(0, 8) : [],
        failed: actionableFailedRows.slice(0, 8),
        archived_cleanup_count: archivedFailedRows.length,
        archived_cleanup: archivedFailedRows.slice(0, 8),
        posted: Array.isArray(postedPosts.data) ? postedPosts.data.slice(0, 8) : [],
      },
    },
    sources: {
      site_traffic: site.data.sources || [],
      miniapp_sources: readerConversionData.top_miniapp_sources || readerEvents.data?.top_sources || [],
      cta_sources: readerConversionData.top_cta_sources || [],
      intent_sources: readerConversionData.top_intent_sources || [],
      lead_sources: countBy(leadRows, "source"),
    },
    retention: {
      unique_users_total: numberValue(readerConversionData.unique_users_total),
      miniapp_unique_users: numberValue(readerEvents.data?.unique_users),
      total_events: numberValue(readerEvents.data?.total_events),
      top_actions: readerConversionData.top_actions || readerEvents.data?.top_actions || [],
      top_users: readerEvents.data?.top_users || [],
      recent_events: readerEvents.data?.recent_events || [],
    },
    raw: {
      leadsStats,
      readerConversion,
      readerEvents,
      readerFunnel,
      readerSummary,
      contractSummary,
      site: site.raw,
    },
  };

  return {
    ...payload,
    recommendations: buildRecommendations(payload, "balanced"),
  };
}

async function buildAnalyticsPayload(request: NextRequest) {
  return buildAnalyticsForDays(clampDays(request.nextUrl.searchParams.get("days")));
}

export async function GET(request: NextRequest) {
  const unauthorized = requireAdminSession(request);
  if (unauthorized) {
    return unauthorized;
  }
  try {
    const payload = await buildAnalyticsPayload(request);
    return NextResponse.json(payload);
  } catch (error: any) {
    return NextResponse.json(
      { detail: error?.message || "Не удалось загрузить аналитику" },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  const unauthorized = requireAdminSession(request);
  if (unauthorized) {
    return unauthorized;
  }
  try {
    const body = await request.json().catch(() => ({}));
    const model = String(body?.model || "balanced").trim();
    const days = String(body?.days || request.nextUrl.searchParams.get("days") || "7");
    const payload = await buildAnalyticsForDays(clampDays(days));
    return NextResponse.json({
      generated_at: new Date().toISOString(),
      model,
      period: payload.period,
      recommendations: buildRecommendations(payload, model),
    });
  } catch (error: any) {
    return NextResponse.json(
      { detail: error?.message || "Не удалось сформировать рекомендации" },
      { status: 500 },
    );
  }
}
