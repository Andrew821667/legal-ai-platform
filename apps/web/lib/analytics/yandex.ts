import type { GA4MetricData } from "@/lib/analytics/google";

const YM_COUNTER_ID = (process.env.YM_COUNTER_ID || "").trim();
const YM_ACCESS_TOKEN = (process.env.YM_ACCESS_TOKEN || "").trim();
const YM_API_BASE = "https://api-metrika.yandex.net/stat/v1/data";

type AnalyticsPayload = {
  success: boolean;
  source: "yandex-metrika";
  configured: boolean;
  data: GA4MetricData;
  timestamp: string;
  error?: string;
};

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function getDate(daysAgo: number = 0): string {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString().split("T")[0];
}

async function fetchYMData(
  metrics: string,
  dimensions?: string,
  date1?: string,
  date2?: string,
): Promise<any> {
  if (!YM_COUNTER_ID || !YM_ACCESS_TOKEN) {
    throw new Error("YM credentials not configured");
  }

  const params = new URLSearchParams({
    ids: YM_COUNTER_ID,
    metrics,
    date1: date1 || getDate(30),
    date2: date2 || getDate(0),
    accuracy: "1",
    limit: "10",
  });

  if (dimensions) {
    params.append("dimensions", dimensions);
  }

  const response = await fetch(`${YM_API_BASE}?${params.toString()}`, {
    headers: {
      Authorization: `OAuth ${YM_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`YM API error ${response.status}: ${error.slice(0, 200)}`);
  }

  return response.json();
}

function parseMetrics(data: any): GA4MetricData["today"] {
  const totals = data?.totals || [0, 0, 0, 0, 0];

  return {
    visits: Math.round(totals[0] || 0),
    pageviews: Math.round(totals[1] || 0),
    uniqueVisitors: Math.round(totals[2] || 0),
    bounceRate: Math.round((totals[3] || 0) * 10) / 10,
    avgDuration: formatDuration(totals[4] || 0),
    conversions: 0,
  };
}

function parseTopPages(data: any): GA4MetricData["topPages"] {
  const rows = data?.data || [];
  return rows.slice(0, 5).map((row: any) => {
    const dimensions = row?.dimensions || [];
    const metrics = row?.metrics || [];

    return {
      page: dimensions[0]?.name || "/",
      visits: Math.round(metrics[0] || 0),
      avgTime: formatDuration(metrics[1] || 0),
    };
  });
}

function parseSources(data: any): GA4MetricData["sources"] {
  const rows = data?.data || [];
  const total = data?.totals?.[0] || 1;

  const sourceNames: Record<string, string> = {
    organic: "Органический поиск",
    direct: "Прямые заходы",
    social: "Социальные сети",
    referral: "Переходы с сайтов",
    ad: "Реклама",
    internal: "Внутренние переходы",
  };

  return rows.slice(0, 4).map((row: any) => {
    const dimensions = row?.dimensions || [];
    const metrics = row?.metrics || [];
    const sourceName = dimensions[0]?.name || "unknown";
    const visits = metrics[0] || 0;

    return {
      name: sourceNames[sourceName] || sourceName,
      percentage: Math.round((visits / total) * 100 * 10) / 10,
    };
  });
}

function getMockYMData(): GA4MetricData {
  return {
    today: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: "0:00",
      conversions: 0,
    },
    week: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: "0:00",
      conversions: 0,
    },
    month: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: "0:00",
      conversions: 0,
    },
    topPages: [],
    sources: [],
  };
}

async function fetchYandexMetrikaData(): Promise<GA4MetricData | null> {
  if (!YM_COUNTER_ID || !YM_ACCESS_TOKEN) {
    return null;
  }

  const today = getDate(0);
  const week = getDate(7);
  const month = getDate(30);

  const [todayData, weekData, monthData, topPagesData, sourcesData] = await Promise.all([
    fetchYMData(
      "ym:s:visits,ym:s:pageviews,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds",
      undefined,
      today,
      today,
    ),
    fetchYMData(
      "ym:s:visits,ym:s:pageviews,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds",
      undefined,
      week,
      today,
    ),
    fetchYMData(
      "ym:s:visits,ym:s:pageviews,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds",
      undefined,
      month,
      today,
    ),
    fetchYMData("ym:s:pageviews,ym:s:avgVisitDurationSeconds", "ym:s:startURL", month, today),
    fetchYMData("ym:s:visits", "ym:s:lastTrafficSource", month, today),
  ]);

  return {
    today: parseMetrics(todayData),
    week: parseMetrics(weekData),
    month: parseMetrics(monthData),
    topPages: parseTopPages(topPagesData),
    sources: parseSources(sourcesData),
  };
}

export async function loadYandexAnalyticsPayload(): Promise<AnalyticsPayload> {
  const timestamp = new Date().toISOString();
  const configured = Boolean(YM_COUNTER_ID && YM_ACCESS_TOKEN);
  try {
    const data = await fetchYandexMetrikaData();
    return {
      success: Boolean(data),
      source: "yandex-metrika",
      configured,
      data: data || getMockYMData(),
      timestamp,
    };
  } catch (error) {
    return {
      success: false,
      source: "yandex-metrika",
      configured,
      data: getMockYMData(),
      timestamp,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}
