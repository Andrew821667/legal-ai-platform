import { NextResponse } from 'next/server';

/**
 * API endpoint для получения данных из Yandex Metrika
 *
 * Требуемые переменные окружения:
 * - YM_COUNTER_ID: ID счетчика Яндекс.Метрики (например: "12345678")
 * - YM_ACCESS_TOKEN: OAuth токен для доступа к API
 */

const YM_COUNTER_ID = process.env.YM_COUNTER_ID;
const YM_ACCESS_TOKEN = process.env.YM_ACCESS_TOKEN;
const YM_API_BASE = 'https://api-metrika.yandex.net/stat/v1/data';

interface YMMetricData {
  today: {
    visits: number;
    pageviews: number;
    uniqueVisitors: number;
    bounceRate: number;
    avgDuration: string;
    conversions: number;
  };
  week: {
    visits: number;
    pageviews: number;
    uniqueVisitors: number;
    bounceRate: number;
    avgDuration: string;
    conversions: number;
  };
  month: {
    visits: number;
    pageviews: number;
    uniqueVisitors: number;
    bounceRate: number;
    avgDuration: string;
    conversions: number;
  };
  topPages: Array<{
    page: string;
    visits: number;
    avgTime: string;
  }>;
  sources: Array<{
    name: string;
    percentage: number;
  }>;
}

/**
 * Форматирование секунд в формат MM:SS
 */
function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Получение даты в формате YYYY-MM-DD
 */
function getDate(daysAgo: number = 0): string {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString().split('T')[0];
}

/**
 * Запрос к Yandex Metrika API
 */
async function fetchYMData(
  metrics: string,
  dimensions?: string,
  date1?: string,
  date2?: string
): Promise<any> {
  if (!YM_COUNTER_ID || !YM_ACCESS_TOKEN) {
    throw new Error('YM credentials not configured');
  }

  const params = new URLSearchParams({
    ids: YM_COUNTER_ID,
    metrics: metrics,
    date1: date1 || getDate(30),
    date2: date2 || getDate(0),
    accuracy: '1',
    limit: '10',
  });

  if (dimensions) {
    params.append('dimensions', dimensions);
  }

  const url = `${YM_API_BASE}?${params.toString()}`;

  const response = await fetch(url, {
    headers: {
      'Authorization': `OAuth ${YM_ACCESS_TOKEN}`,
      'Content-Type': 'application/json',
    },
    next: { revalidate: 300 }, // Кэш на 5 минут
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`YM API error ${response.status}: ${error}`);
  }

  return response.json();
}

/**
 * Получение данных из Yandex Metrika
 */
async function fetchYandexMetrikaData(): Promise<YMMetricData | null> {
  if (!YM_COUNTER_ID || !YM_ACCESS_TOKEN) {
    console.warn('Yandex Metrika credentials not configured');
    return null;
  }

  try {
    const today = getDate(0);
    const yesterday = getDate(1);
    const week = getDate(7);
    const month = getDate(30);

    // Получаем основные метрики для разных периодов
    const [todayData, weekData, monthData, topPagesData, sourcesData] = await Promise.all([
      // Данные за сегодня
      fetchYMData(
        'ym:s:visits,ym:s:pageviews,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds',
        undefined,
        today,
        today
      ),
      // Данные за неделю
      fetchYMData(
        'ym:s:visits,ym:s:pageviews,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds',
        undefined,
        week,
        today
      ),
      // Данные за месяц
      fetchYMData(
        'ym:s:visits,ym:s:pageviews,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds',
        undefined,
        month,
        today
      ),
      // Топ страниц
      fetchYMData(
        'ym:s:pageviews,ym:s:avgVisitDurationSeconds',
        'ym:s:startURL',
        month,
        today
      ),
      // Источники трафика
      fetchYMData(
        'ym:s:visits',
        'ym:s:lastTrafficSource',
        month,
        today
      ),
    ]);

    return {
      today: parseMetrics(todayData),
      week: parseMetrics(weekData),
      month: parseMetrics(monthData),
      topPages: parseTopPages(topPagesData),
      sources: parseSources(sourcesData),
    };

  } catch (error) {
    console.error('Error fetching Yandex Metrika data:', error);
    return null;
  }
}

/**
 * Парсинг метрик из ответа Yandex Metrika
 */
function parseMetrics(data: any) {
  const totals = data.totals || [0, 0, 0, 0, 0];

  return {
    visits: Math.round(totals[0] || 0),
    pageviews: Math.round(totals[1] || 0),
    uniqueVisitors: Math.round(totals[2] || 0),
    bounceRate: Math.round((totals[3] || 0) * 10) / 10,
    avgDuration: formatDuration(totals[4] || 0),
    conversions: 0, // Нужна настройка целей в Метрике
  };
}

/**
 * Парсинг топ страниц
 */
function parseTopPages(data: any) {
  const rows = data.data || [];

  return rows.slice(0, 5).map((row: any) => {
    const dimensions = row.dimensions || [];
    const metrics = row.metrics || [];

    return {
      page: dimensions[0]?.name || '/',
      visits: Math.round(metrics[0] || 0),
      avgTime: formatDuration(metrics[1] || 0),
    };
  });
}

/**
 * Парсинг источников трафика
 */
function parseSources(data: any) {
  const rows = data.data || [];
  const total = data.totals?.[0] || 1;

  // Маппинг названий источников на русский
  const sourceNames: Record<string, string> = {
    'organic': 'Органический поиск',
    'direct': 'Прямые заходы',
    'social': 'Социальные сети',
    'referral': 'Переходы с сайтов',
    'ad': 'Реклама',
    'internal': 'Внутренние переходы',
  };

  return rows.slice(0, 4).map((row: any) => {
    const dimensions = row.dimensions || [];
    const metrics = row.metrics || [];
    const sourceName = dimensions[0]?.name || 'unknown';
    const visits = metrics[0] || 0;

    return {
      name: sourceNames[sourceName] || sourceName,
      percentage: Math.round((visits / total) * 100 * 10) / 10,
    };
  });
}

/**
 * Mock данные для демонстрации (когда Metrika не настроена)
 */
function getMockYMData(): YMMetricData {
  return {
    today: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: '0:00',
      conversions: 0,
    },
    week: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: '0:00',
      conversions: 0,
    },
    month: {
      visits: 0,
      pageviews: 0,
      uniqueVisitors: 0,
      bounceRate: 0,
      avgDuration: '0:00',
      conversions: 0,
    },
    topPages: [],
    sources: [],
  };
}

export async function GET() {
  try {
    const data = await fetchYandexMetrikaData();

    return NextResponse.json({
      success: !!data,
      source: 'yandex-metrika',
      configured: !!(YM_COUNTER_ID && YM_ACCESS_TOKEN),
      data: data || getMockYMData(),
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Yandex Metrika API Route Error:', error);
    return NextResponse.json(
      {
        success: false,
        source: 'yandex-metrika',
        configured: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        data: getMockYMData(),
      },
      { status: 500 }
    );
  }
}
